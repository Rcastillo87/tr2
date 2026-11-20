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

Estados (`real_trades.executions_status`): NULL pendiente (lo toma el tick) · 'open_ok' apertura registrada ·
'ok' apertura y cierre · 'missing' Bybit no las dio 24 h después del cierre · 'historical' anterior a p89 (lo toma
el comando `real:executions-backfill`).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

QTY_TOL = 1e-3        # relativa: 0,1 % (la cantidad es múltiplo del paso; esto solo absorbe el redondeo de texto)
PRICE_TOL = 1e-4      # relativa: 0,01 % (Bybit redondea el avgPrice al paso de precio)
WINDOW_MS = 3_600_000  # ± 1 h alrededor de la hora conocida de la orden
GIVE_UP = timedelta(hours=24)
PENDING_PER_TICK = 2
NET_TOL = 0.01      # USDT: el neto se guarda con 4 decimales
TRADE_COLS = ('id, symbol, side, status, size, original_size, entry_price, exit_price, entry_time, exit_time, '
              'order_id, close_order_id, executions_status, pnl, net_pnl, commission, funding')


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


def leg_summary(rows: list[dict]) -> dict | None:
    """Partes, cantidad, precio promedio ponderado, comisión y cuántas como maker. None sin partes."""
    trades = [r for r in rows if (r.get('exec_type') or 'Trade') == 'Trade']
    qty = sum(r['exec_qty'] for r in trades)
    if qty <= 0:
        return None
    return dict(parts=len(trades), qty=round(qty, 10), vwap=sum(r['exec_price'] * r['exec_qty'] for r in trades) / qty,
                fee=round(sum(r['exec_fee'] or 0 for r in trades), 10), maker=sum(1 for r in trades if r['is_maker']),
                orders=sorted({r['order_id'] for r in trades}))


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
    return out


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


async def bybit_close_net(client, trade: dict, order_ids: list[str]) -> float | None:
    """closedPnl de Bybit de las órdenes de cierre del trade (suma de tramos). None si no aparece ninguno."""
    exit_ms = _ms(trade['exit_time']) + 60_000
    history = await client.get_closed_pnl_history(trade['symbol'], float(trade['entry_price']), _ms(trade['entry_time']),
                                                  limit=50, end_time_ms=exit_ms)
    got = [_f(h.get('closedPnl')) for h in history
           if str(h.get('orderId')) in set(order_ids) and int(_f(h.get('createdTime')) or 0) <= exit_ms]
    got = [g for g in got if g is not None]
    return round(sum(got), 8) if got else None


async def close_orders(client, trade: dict) -> list[tuple[str, int]] | None:
    """Órdenes de cierre y su hora (ms). Con close_order_id (cierre del bot) es esa; si no, las de cada tramo del
    closed-pnl (cierres de Bybit: SL/TP/trailing). None si el trade no tiene hora de cierre."""
    if not trade.get('exit_time'):
        return None
    exit_ms = _ms(trade['exit_time'])
    if trade.get('close_order_id'):
        return [(str(trade['close_order_id']), exit_ms)]
    end_ms = exit_ms + 60_000
    history = await client.get_closed_pnl_history(trade['symbol'], float(trade['entry_price']), _ms(trade['entry_time']),
                                                  limit=50, end_time_ms=end_ms)
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
    """Registra las partes que falten de un trade. Devuelve el resumen (también sin apply, sin escribir nada)."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    async with pool.acquire() as conn:
        have = {r['leg']: r['n'] for r in await conn.fetch(
            "SELECT leg, count(*) AS n FROM real_trade_executions WHERE real_trade_id = $1 GROUP BY leg", trade['id'])}
    res = dict(trade_id=trade['id'], symbol=trade['symbol'], open=None, close=None, checks=[], status=None,
               close_order_id=None, error=None, split=None, split_note=None)
    new_rows = []
    if not have.get('open') and trade.get('order_id'):
        rows = await _fetch(client, trade['symbol'], [(str(trade['order_id']), _ms(trade['entry_time']))], 'open')
        if rows is None:
            res['error'] = 'Bybit no respondió (apertura)'
            return res
        new_rows += rows
    closed = trade.get('status') == 'closed'
    tranches = None
    if closed and not have.get('close'):
        tranches = await close_orders(client, trade)
        if tranches:
            rows = await _fetch(client, trade['symbol'], tranches, 'close')
            if rows is None:
                res['error'] = 'Bybit no respondió (cierre)'
                return res
            new_rows += rows
    async with pool.acquire() as conn:
        old = [dict(r) for r in await conn.fetch(
            """SELECT leg, exec_id, order_id, exec_price, exec_qty, exec_fee, is_maker, exec_type
               FROM real_trade_executions WHERE real_trade_id = $1""", trade['id'])]
    for r in old:
        for k in ('exec_price', 'exec_qty', 'exec_fee'):
            r[k] = _f(r[k])
    known = {r['exec_id'] for r in old}
    allrows = old + [r for r in new_rows if r['exec_id'] not in known]
    open_s = leg_summary([r for r in allrows if r['leg'] == 'open'])
    close_s = leg_summary([r for r in allrows if r['leg'] == 'close'])
    res.update(open=open_s, close=close_s, checks=leg_checks(trade, open_s, close_s))
    if not trade.get('close_order_id') and tranches:
        res['close_order_id'] = tranches[-1][0]   # R-23: el último tramo, como last_close_order_id
    exit_t = trade.get('exit_time')
    if closed and open_s and close_s:
        res['status'] = 'ok'
    elif closed and exit_t and now - exit_t > GIVE_UP:
        res['status'] = 'missing'
    elif not closed and open_s:
        res['status'] = 'open_ok'
    if res['status'] == 'ok' and trade.get('funding') is None and 'pnl' in trade:
        net_b = await bybit_close_net(client, trade, close_s['orders'])
        split, note = split_costs(trade.get('pnl'), trade.get('net_pnl'), open_s['fee'] + close_s['fee'], net_b)
        if split:
            res['split'] = dict(split, commission_before=_f(trade.get('commission')))
        else:
            res['split_note'] = note
    if not apply:
        return res
    fresh = [r for r in new_rows if r['exec_id'] not in known]
    async with pool.acquire() as conn:
        async with conn.transaction():
            for r in fresh:
                await conn.execute(
                    """INSERT INTO real_trade_executions (real_trade_id, leg, exec_id, order_id, symbol, side, exec_price,
                       exec_qty, exec_value, exec_fee, fee_rate, is_maker, exec_type, stop_order_type, exec_time)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15) ON CONFLICT (exec_id) DO NOTHING""",
                    trade['id'], r['leg'], r['exec_id'], r['order_id'], r['symbol'], r['side'], r['exec_price'],
                    r['exec_qty'], r['exec_value'], r['exec_fee'], r['fee_rate'], r['is_maker'], r['exec_type'],
                    r['stop_order_type'], r['exec_time'])
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
    if res['status'] and (fresh or res['status'] != trade.get('executions_status')):
        await trader.log_audit(trade['id'], 'executions_recorded' if res['status'] != 'missing' else 'executions_missing', {
            'open': open_s, 'close': close_s, 'checks': res['checks'], 'close_order_id_filled': res['close_order_id']})
        if res['checks']:
            logger.warning(f"[REAL] #{trade['id']} {trade['symbol']} ejecuciones de Bybit: {'; '.join(res['checks'])}")
    return res


async def process_pending(pool, trader, client, account_id: int, limit: int = PENDING_PER_TICK) -> list[dict]:
    """Del tick: hasta `limit` operaciones de la cuenta con partes por registrar (no las 'historical')."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT {TRADE_COLS}
               FROM real_trades
               WHERE broker_account_id = $1 AND order_id IS NOT NULL
                 AND ((executions_status IS NULL AND status IN ('open', 'closed'))
                      OR (executions_status = 'open_ok' AND status = 'closed'))
                 AND (status <> 'closed' OR exit_time < timezone('UTC', now()) - interval '1 minute')
               ORDER BY id LIMIT $2""", account_id, limit)
    out = []
    for r in rows:
        try:
            out.append(await record_trade(pool, trader, client, dict(r)))
        except Exception as e:   # noqa: BLE001 (el libro nunca frena la gestión de posiciones)
            logger.warning(f"[REAL] #{r['id']} libro de ejecuciones: {type(e).__name__}: {e}")
    return out
