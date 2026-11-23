"""
MEJ-004 (p89): libro de ejecuciones de Bybit por operación Real. Cada parte (fill) con que Bybit llenó la orden de
apertura y la(s) de cierre: precio, cantidad, comisión, maker/taker y hora. Solo LEE de Bybit (/v5/execution/list).

Controles en cada operación (van al historial `audit_log`, acción `executions_recorded`):
  - cantidad llenada = tamaño registrado (apertura y cierre): cubre R-10 sin tocar la apertura (D-16);
  - precio promedio de las partes = precio de entrada / salida registrado;
  - neto registrado = closedPnl de Bybit de las órdenes de cierre.
También completa `close_order_id` cuando falta (R-23: los cierres hechos por Bybit no lo guardaban).

R-24 (p90): con las dos patas y el neto de Bybit, separa los costos como Paper: `commission` = comisiones exactas de
las partes y `funding` = bruto − neto − comisiones (positivo = pagado). El neto y el saldo no cambian. Si el neto
registrado no es el de Bybit, no se separa: queda como control en el historial (acción `costs_split`).

Estados (`real_trades.executions_status`): NULL pendiente (lo toma el tick) · 'open_ok' apertura registrada y
cuadrada · 'ok' apertura y cierre cuadrados · 'mismatch' 24 h después del cierre Bybit sigue dando cantidad, precio o
comisión que no cuadran (aviso `executions_mismatch`; no se separan los costos) · 'missing' Bybit no dio una de las
patas 24 h después del cierre · 'historical' anterior a p89 (lo toma el comando `real:executions-backfill`).

C5-01 (p99): «ok» solo con todo verificado. Una pata guardada que no cuadra (faltan partes o comisiones) se vuelve a
pedir; un error o una respuesta incompleta de Bybit es «no sé» (se reintenta cada RETRY_EVERY), nunca «no hay»; una
comisión que Bybit no informa es desconocida, no 0.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from trading.broker_events import emit_event

logger = logging.getLogger(__name__)

QTY_TOL = 1e-3        # relativa: 0,1 % (la cantidad es múltiplo del paso; esto solo absorbe el redondeo de texto)
PRICE_TOL = 1e-4      # relativa: 0,01 % (Bybit redondea el avgPrice al paso de precio)
WINDOW_MS = 3_600_000  # ± 1 h alrededor de la hora conocida de la orden
GIVE_UP = timedelta(hours=24)
PENDING_PER_TICK = 2
NET_TOL = 0.01      # USDT: el neto se guarda con 4 decimales
RETRY_EVERY = timedelta(minutes=10)   # una operación sin verificar no se vuelve a pedir antes (no acapara el tick)
TRADE_COLS = ('id, broker_account_id, symbol, side, status, size, original_size, entry_price, exit_price, entry_time, '
              'exit_time, order_id, close_order_id, executions_status, pnl, net_pnl, commission, funding')
_RETRY_AT: dict[int, datetime] = {}   # id → no antes de (en memoria: el motor es un solo proceso)


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ms(t: datetime) -> int:
    return int((t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t).timestamp() * 1000)


def parse_execution(e: dict, leg: str) -> dict | None:
    """Fila de real_trade_executions desde un elemento de /v5/execution/list (None si le falta lo esencial)."""
    price, qty, ms = _f(e.get('execPrice')), _f(e.get('execQty')), _f(e.get('execTime'))
    if not e.get('execId') or not e.get('orderId') or price is None or qty is None or ms is None:
        return None
    maker = e.get('isMaker')
    return dict(leg=leg, exec_id=str(e['execId']), order_id=str(e['orderId']), symbol=e.get('symbol') or '',
                side=e.get('side') or '', exec_price=price, exec_qty=qty, exec_value=_f(e.get('execValue')),
                exec_fee=_f(e.get('execFee')), fee_rate=_f(e.get('feeRate')),
                is_maker=(maker is True or str(maker).lower() == 'true'), exec_type=e.get('execType'),
                stop_order_type=e.get('stopOrderType') or None,
                exec_time=datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(tzinfo=None))


def _dec(v) -> Decimal | None:
    """Número para la base tal como lo escribió Bybit (repr del float: 15.91, no 15.9100000000000001421…)."""
    return None if v is None else Decimal(repr(float(v)))


def leg_summary(rows: list[dict]) -> dict | None:
    """Partes, cantidad, precio promedio ponderado, comisión y cuántas como maker. None sin partes.
    fee = None si alguna parte no trae comisión (desconocida, no 0: C5-01); fee_unknown = cuántas."""
    trades = [r for r in rows if (r.get('exec_type') or 'Trade') == 'Trade']
    qty = sum(r['exec_qty'] for r in trades)
    if qty <= 0:
        return None
    unknown = sum(1 for r in trades if r['exec_fee'] is None)
    return dict(parts=len(trades), qty=round(qty, 10), vwap=sum(r['exec_price'] * r['exec_qty'] for r in trades) / qty,
                fee=None if unknown else round(sum(r['exec_fee'] for r in trades), 10), fee_unknown=unknown,
                maker=sum(1 for r in trades if r['is_maker']), orders=sorted({r['order_id'] for r in trades}))


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b) if b else abs(a - b)


def leg_checks(trade: dict, open_s: dict | None, close_s: dict | None) -> list[str]:
    """Diferencias entre lo que llenó Bybit y lo registrado (vacía = todo coincide)."""
    out = []
    size = _f(trade.get('original_size')) or _f(trade.get('size'))
    for name, s, price_key in (('apertura', open_s, 'entry_price'), ('cierre', close_s, 'exit_price')):
        if not s:
            continue
        if size and _rel(s['qty'], size) > QTY_TOL:
            out.append(f"{name}: Bybit llenó {s['qty']:g} y la operación registra {size:g}")
        price = _f(trade.get(price_key))
        if price and _rel(s['vwap'], price) > PRICE_TOL:
            out.append(f"{name}: precio promedio de Bybit {s['vwap']:.8g} y registrado {price:.8g}")
        if s.get('fee_unknown'):
            out.append(f"{name}: Bybit no informó la comisión de {s['fee_unknown']} parte(s)")
    return out


def leg_ok(trade: dict, s: dict | None) -> bool:
    """La pata ya guardada está completa: cantidad = tamaño y todas las comisiones conocidas (si no, se vuelve a pedir)."""
    if not s or s['fee'] is None:
        return False
    size = _f(trade.get('original_size')) or _f(trade.get('size'))
    return not (size and _rel(s['qty'], size) > QTY_TOL)


def split_costs(pnl, net_pnl, fees, bybit_net) -> tuple[dict | None, str | None]:
    """R-24: ({commission, funding}, None) o (None, motivo por el que no se separa)."""
    pnl, net_pnl, fees, bybit_net = _f(pnl), _f(net_pnl), _f(fees), _f(bybit_net)
    if pnl is None or net_pnl is None or fees is None:
        return None, 'sin bruto, neto o comisiones'
    if bybit_net is None:
        return None, 'Bybit no dio el closed-pnl del cierre'
    if abs(net_pnl - bybit_net) > NET_TOL:
        return None, f'neto registrado {net_pnl:g} y de Bybit {bybit_net:g}'
    return {'commission': round(fees, 8), 'funding': round(pnl - net_pnl - fees, 8)}, None


async def bybit_close_net(client, trade: dict, order_ids: list[str]) -> float | None | bool:
    """closedPnl de Bybit de las órdenes de cierre del trade (suma de tramos). None si no aparece ninguno; False si
    Bybit falló o la respuesta quedó incompleta (C5-01: «no sé», se reintenta)."""
    exit_ms = _ms(trade['exit_time']) + 60_000
    history = await client.get_closed_pnl_history(trade['symbol'], float(trade['entry_price']), _ms(trade['entry_time']),
                                                  limit=100, end_time_ms=exit_ms, strict=True)
    if history is None:
        return False
    got = [_f(h.get('closedPnl')) for h in history
           if str(h.get('orderId')) in set(order_ids) and int(_f(h.get('createdTime')) or 0) <= exit_ms]
    got = [g for g in got if g is not None]
    return round(sum(got), 8) if got else None


async def close_orders(client, trade: dict) -> list[tuple[str, int]] | None:
    """Órdenes de cierre y su hora (ms). Con close_order_id (cierre del bot) es esa; si no, las de cada tramo del
    closed-pnl (cierres de Bybit: SL/TP/trailing). [] si el trade no tiene hora de cierre; None si Bybit falló o la
    respuesta quedó incompleta (C5-01: «no sé», no «no hay cierres»)."""
    if not trade.get('exit_time'):
        return []
    exit_ms = _ms(trade['exit_time'])
    if trade.get('close_order_id'):
        return [(str(trade['close_order_id']), exit_ms)]
    end_ms = exit_ms + 60_000
    history = await client.get_closed_pnl_history(trade['symbol'], float(trade['entry_price']), _ms(trade['entry_time']),
                                                  limit=100, end_time_ms=end_ms, strict=True)
    if history is None:
        return None
    seen = {}
    for h in history:
        t = int(_f(h.get('createdTime')) or 0)
        if h.get('orderId') and t <= end_ms:
            seen[str(h['orderId'])] = max(t, seen.get(str(h['orderId']), 0))
    return sorted(seen.items(), key=lambda x: x[1])


async def _fetch(client, symbol: str, orders: list[tuple[str, int]], leg: str) -> list[dict] | None:
    rows = []
    for oid, t in orders:
        got = await client.get_executions(symbol, oid, t - WINDOW_MS, t + WINDOW_MS)
        if got is None:
            return None
        rows += [r for r in (parse_execution(e, leg) for e in got) if r]
    return rows


async def record_trade(pool, trader, client, trade: dict, apply: bool = True, now: datetime | None = None) -> dict:
    """Registra las partes que falten de un trade y lo da por verificado solo si todo cuadra (C5-01). Devuelve el
    resumen (también sin apply, sin escribir nada)."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    async with pool.acquire() as conn:
        old = [dict(r) for r in await conn.fetch(
            """SELECT leg, exec_id, order_id, exec_price, exec_qty, exec_fee, is_maker, exec_type
               FROM real_trade_executions WHERE real_trade_id = $1""", trade['id'])]
    for r in old:
        for k in ('exec_price', 'exec_qty', 'exec_fee'):
            r[k] = _f(r[k])
    res = dict(trade_id=trade['id'], symbol=trade['symbol'], open=None, close=None, checks=[], status=None,
               close_order_id=None, error=None, split=None, split_note=None)
    stored = {leg: leg_summary([r for r in old if r['leg'] == leg]) for leg in ('open', 'close')}
    new_rows = []
    if trade.get('order_id') and not leg_ok(trade, stored['open']):   # falta o no cuadra: se vuelve a pedir
        rows = await _fetch(client, trade['symbol'], [(str(trade['order_id']), _ms(trade['entry_time']))], 'open')
        if rows is None:
            res['error'] = 'Bybit no respondió (apertura)'
            return res
        new_rows += rows
    closed = trade.get('status') == 'closed'
    tranches = None
    if closed and not leg_ok(trade, stored['close']):
        tranches = await close_orders(client, trade)
        if tranches is None:
            res['error'] = 'Bybit no respondió (órdenes de cierre)'
            return res
        if tranches:
            rows = await _fetch(client, trade['symbol'], tranches, 'close')
            if rows is None:
                res['error'] = 'Bybit no respondió (cierre)'
                return res
            new_rows += rows
    by_id = {r['exec_id']: r for r in old}
    fresh, filled = [], []   # partes nuevas · partes guardadas sin comisión que Bybit ya informa
    for r in new_rows:
        o = by_id.get(r['exec_id'])
        if o is None:
            by_id[r['exec_id']] = r
            fresh.append(r)
        elif o['exec_fee'] is None and r['exec_fee'] is not None:
            o['exec_fee'] = r['exec_fee']
            filled.append(r)
    allrows = list(by_id.values())
    open_s = leg_summary([r for r in allrows if r['leg'] == 'open'])
    close_s = leg_summary([r for r in allrows if r['leg'] == 'close'])
    res.update(open=open_s, close=close_s, checks=leg_checks(trade, open_s, close_s))
    if not trade.get('close_order_id') and tranches:
        res['close_order_id'] = tranches[-1][0]   # R-23: el último tramo, como last_close_order_id
    exit_t = trade.get('exit_time')
    late = bool(closed and exit_t and now - exit_t > GIVE_UP)
    if closed and open_s and close_s and not res['checks']:
        res['status'] = 'ok'
    elif late:
        res['status'] = 'mismatch' if open_s and close_s else 'missing'
    elif not closed and open_s and not leg_checks(trade, open_s, None):
        res['status'] = 'open_ok'
    if res['status'] == 'ok' and trade.get('funding') is None and 'pnl' in trade:
        net_b = await bybit_close_net(client, trade, close_s['orders'])
        if net_b is False:   # «no sé»: no se da por verificado todavía
            res['status'], res['error'] = None, 'Bybit no respondió (closed-pnl del cierre)'
        else:
            split, note = split_costs(trade.get('pnl'), trade.get('net_pnl'), open_s['fee'] + close_s['fee'], net_b)
            if split:
                res['split'] = dict(split, commission_before=_f(trade.get('commission')))
            else:
                res['split_note'] = note
    if not apply:
        return res
    async with pool.acquire() as conn:
        async with conn.transaction():
            for r in fresh:
                await conn.execute(
                    """INSERT INTO real_trade_executions (real_trade_id, leg, exec_id, order_id, symbol, side, exec_price,
                       exec_qty, exec_value, exec_fee, fee_rate, is_maker, exec_type, stop_order_type, exec_time)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15) ON CONFLICT (exec_id) DO NOTHING""",
                    trade['id'], r['leg'], r['exec_id'], r['order_id'], r['symbol'], r['side'], _dec(r['exec_price']),
                    _dec(r['exec_qty']), _dec(r['exec_value']), _dec(r['exec_fee']), _dec(r['fee_rate']), r['is_maker'],
                    r['exec_type'], r['stop_order_type'], r['exec_time'])
            for r in filled:
                await conn.execute("""UPDATE real_trade_executions SET exec_fee = $1, fee_rate = coalesce(fee_rate, $2)
                                      WHERE exec_id = $3 AND exec_fee IS NULL""", _dec(r['exec_fee']), _dec(r['fee_rate']),
                                   r['exec_id'])
            if res['close_order_id']:
                await conn.execute("UPDATE real_trades SET close_order_id = $1 WHERE id = $2 AND close_order_id IS NULL",
                                   res['close_order_id'], trade['id'])
            if res['status']:
                await conn.execute("UPDATE real_trades SET executions_status = $1 WHERE id = $2", res['status'], trade['id'])
            if res['split']:
                await conn.execute("UPDATE real_trades SET commission = $1, funding = $2 WHERE id = $3 AND funding IS NULL",
                                   res['split']['commission'], res['split']['funding'], trade['id'])
    if res['split'] or res['split_note']:
        await trader.log_audit(trade['id'], 'costs_split', {**(res['split'] or {}), 'note': res['split_note']})
    if res['status'] and (fresh or filled or res['status'] != trade.get('executions_status')):
        action = {'missing': 'executions_missing', 'mismatch': 'executions_mismatch'}.get(res['status'], 'executions_recorded')
        await trader.log_audit(trade['id'], action, {
            'open': open_s, 'close': close_s, 'checks': res['checks'], 'close_order_id_filled': res['close_order_id']})
        if res['status'] == 'mismatch' and trade.get('broker_account_id'):   # una vez: solo al pasar a 'mismatch'
            await emit_event(pool, trade['broker_account_id'], 'executions_mismatch', trade['id'], symbol=trade['symbol'],
                             checks=res['checks'])
    if res['checks']:
        logger.warning(f"[REAL] #{trade['id']} {trade['symbol']} ejecuciones de Bybit: {'; '.join(res['checks'])}")
    return res


async def process_pending(pool, trader, client, account_id: int, limit: int = PENDING_PER_TICK) -> list[dict]:
    """Del tick: hasta `limit` operaciones de la cuenta con partes por registrar (no las 'historical'). Una que quedó
    sin verificar (Bybit falló o no cuadra todavía) espera RETRY_EVERY antes de volver a pedirse (C5-01)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT {TRADE_COLS}
               FROM real_trades
               WHERE broker_account_id = $1 AND order_id IS NOT NULL
                 AND ((executions_status IS NULL AND status IN ('open', 'closed'))
                      OR (executions_status = 'open_ok' AND status = 'closed'))
                 AND (status <> 'closed' OR exit_time < timezone('UTC', now()) - interval '1 minute')
               ORDER BY id LIMIT $2""", account_id, limit * 10)
    out = []
    for r in [r for r in rows if _RETRY_AT.get(r['id'], now) <= now][:limit]:
        try:
            res = await record_trade(pool, trader, client, dict(r))
            out.append(res)
            unresolved = bool(res.get('error')) or not res.get('status')
        except Exception as e:   # noqa: BLE001 (el libro nunca frena la gestión de posiciones)
            logger.warning(f"[REAL] #{r['id']} libro de ejecuciones: {type(e).__name__}: {e}")
            unresolved = True
        if unresolved:
            _RETRY_AT[r['id']] = now + RETRY_EVERY
        else:
            _RETRY_AT.pop(r['id'], None)
    return out
