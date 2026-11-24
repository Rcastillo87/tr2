"""
Pruebas de aceptación del ciclo 5 en Bybit DEMO TRADING (dinero ficticio, precios reales), parte Bybit (sin base).

Usa el código real del bot (BybitClient y RealTrader._risk_size) contra api-demo.bybit.com. Los fallos que no se pueden
provocar a voluntad (respuesta perdida, Bybit sin responder, cuenta en Hedge) se simulan alrededor de la llamada real.
  DEMO-02  respuesta perdida tras enviar la apertura: no duplica y la recupera por orderLinkId
  DEMO-01  la cantidad ejecutada de la orden real (cumExecQty) se lee bien; una «Cancelled» con parte ejecutada cuenta
           como ejecutada y la posición está en Bybit con ese tamaño (la adopción con base: real_unresolved_test)
  DEMO-03  SL/TP: aceptado y confirmado en la posición; repetido (34040) confirmado leyendo la posición; niveles
           distintos NO se confirman; un SL inválido lo rechaza Bybit y la posición conserva el anterior
  DEMO-05  «reinicio»: un cliente nuevo (sin cachés) encuentra la posición y confirma sus niveles
  DEMO-06  Bybit sin responder: posición, orden, closed-pnl, ejecuciones y saldo devuelven «no sé», nunca «no hay»
  DEMO-09  tamaño con el saldo y el precio reales de Demo, y recalculado si el precio se mueve > 0,5 %
  DEMO-10  cuenta en Hedge (simulado: la orden lleva positionIdx=1 en una cuenta One-Way): Bybit la rechaza, el bot no
           reenvía otra y no queda posición
Las partes con base de datos (DEMO-04, 07, 08, 11, 12 y la adopción de 01/05) las cubren real_unresolved_test,
risk_limits_test, real_recovery_test y real_reconcile_visibility_test.

Seguridad: SOLO api-demo.bybit.com; cantidad mínima; aborta si ya hay posición o órdenes en el símbolo; cierra siempre
(también si algo falla); NO se conecta a ninguna base (bloqueado en el arranque). Las claves llegan por variables de
entorno (TR2_K / TR2_S) y nunca se imprimen ni se guardan. Evidencia (respuestas de Bybit y resultados, sin claves ni
firmas) en un JSON fuera del proyecto.

Uso (desde python-engine/):
  read -rs TR2_K; read -rs TR2_S; export TR2_K TR2_S
  venv/bin/python ../tests/Forensic/demo_c5_bybit.py [SIMBOLO=ADAUSDT]
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.getcwd())

import asyncpg  # noqa: E402


def _no_db(*_a, **_k):
    raise RuntimeError('demo_c5_bybit: prohibido conectarse a una base')


asyncpg.connect = _no_db          # ninguna parte de esta prueba puede tocar una base (D-56)
asyncpg.create_pool = _no_db

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv('.env')

from trading.real_trader import (BYBIT_DEMO_URL, BybitAPIError, BybitClient, RealTrader,  # noqa: E402
                                 executed_qty)

fails = 0
evidence = {'inicio_utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()), 'pruebas': [], 'bybit': []}


def check(test, name, ok, detail=None):
    global fails
    fails += not ok
    evidence['pruebas'].append({'prueba': test, 'comprobacion': name, 'ok': bool(ok), 'detalle': detail})
    d = '' if detail is None else '  -> ' + json.dumps(detail, ensure_ascii=False, default=str)[:300]
    print(f"{'PASS' if ok else 'FAIL'}  {test}: {name}{d}")


def record(client: BybitClient):
    """Guarda cada llamada firmada (ruta, parámetros y respuesta), nunca encabezados ni firmas."""
    real_get, real_post = client._signed_get, client._signed_post

    async def get(path, params, timeout=10):
        r = await real_get(path, params, timeout)
        _keep('GET', path, params, r)
        return r

    async def post(path, body, timeout=15):
        r = await real_post(path, body, timeout)
        _keep('POST', path, body, r)
        return r

    client._signed_get, client._signed_post = get, post


def _keep(method, path, payload, r):
    try:
        data = r.json()
    except Exception:  # noqa: BLE001
        data = {'texto': (r.text or '')[:200]}
    evidence['bybit'].append({'t': time.strftime('%H:%M:%S', time.gmtime()), 'metodo': method, 'ruta': path,
                              'envio': payload, 'retCode': data.get('retCode'), 'retMsg': data.get('retMsg'),
                              'result': data.get('result')})


async def size_of(c, symbol):
    pos = await c.get_open_position(symbol)
    return float(pos['size']) if pos else 0.0


async def wait_size(c, symbol, want, secs=15):
    size = None
    for _ in range(secs):
        size = await size_of(c, symbol)
        if abs(size - want) < 1e-12:
            return size
        await asyncio.sleep(1)
    return size


async def open_orders(c, symbol):
    data = (await c._signed_get('/v5/order/realtime', {'category': 'linear', 'symbol': symbol})).json()
    return (data.get('result') or {}).get('list') or []


async def main() -> int:
    symbol = (sys.argv[1] if len(sys.argv) > 1 else 'ADAUSDT').upper()
    key, secret = os.getenv('TR2_K'), os.getenv('TR2_S')
    if not key or not secret:
        sys.exit('Faltan TR2_K / TR2_S (exportarlas con read -rs; no se imprimen)')
    c = BybitClient(key, secret, account_type='demo')
    if c.base_url != BYBIT_DEMO_URL or 'api-demo.bybit.com' not in c.base_url:
        sys.exit('ABORTADO: el cliente no apunta a api-demo.bybit.com')
    record(c)
    evidence.update({'simbolo': symbol, 'url': c.base_url})

    if await size_of(c, symbol):
        sys.exit(f'ABORTADO: ya hay una posición abierta en {symbol}; no se toca')
    if await open_orders(c, symbol):
        sys.exit(f'ABORTADO: hay órdenes abiertas en {symbol}; no se toca')
    qty, step = await c.get_min_qty(symbol)
    print(f'{symbol}: cantidad mínima {qty} (paso {step}) en {c.base_url}\n')

    try:
        # ── DEMO-02: la respuesta de la apertura se pierde (Bybit sí la recibió) ──
        real_post, lost = c._signed_post, {'n': 0}

        async def post_lost(path, body, timeout=15):
            r = await real_post(path, body, timeout)          # la orden llega a Bybit…
            if path == '/v5/order/create' and lost['n'] == 0:
                lost['n'] += 1
                raise httpx.ReadTimeout('respuesta perdida (simulado)')   # …pero la respuesta no llega al bot
            return r

        c._signed_post = post_lost
        res = await c.place_market_order(symbol, 'Buy', qty)
        c._signed_post = real_post
        size = await wait_size(c, symbol, qty)
        check('DEMO-02', 'respuesta perdida: el bot recupera la orden por su orderLinkId',
              bool(res and res.get('orderId') and not res.get('unconfirmed')), res)
        check('DEMO-02', 'la posición NO se duplicó (una sola orden llenada)', abs(size - qty) < 1e-12, size)
        if not res or not res.get('orderId'):
            return 1
        link = res['orderLinkId']

        # ── DEMO-01: cantidad ejecutada ──
        order = await c.get_order(symbol, link_id=link)
        check('DEMO-01', 'la orden real está llenada y su cantidad ejecutada (cumExecQty) es la pedida',
              bool(order) and order.get('orderStatus') == 'Filled' and abs(executed_qty(order) - qty) < 1e-12,
              {'estado': (order or {}).get('orderStatus'), 'cumExecQty': (order or {}).get('cumExecQty')})
        partial = dict(order or {}, orderStatus='Cancelled')
        check('DEMO-01', '«Cancelled» con parte ejecutada cuenta como ejecutada (nunca «fallida»)',
              executed_qty(partial) > 0, executed_qty(partial))
        pos = await c.get_open_position(symbol)
        check('DEMO-01', 'la posición está en Bybit con el tamaño ejecutado (lo que se adopta)',
              bool(pos) and abs(float(pos['size']) - executed_qty(order)) < 1e-12, (pos or {}).get('size'))

        # ── DEMO-03: SL/TP confirmados ──
        entry = float(pos['avgPrice'])
        tick = await c.get_tick_size(symbol) or 0.0001
        rnd = (lambda p: round(round(p / tick) * tick, 8))
        sl, tp = rnd(entry * 0.985), rnd(entry * 1.03)
        ok1 = await c.set_trading_stop(symbol, sl, tp, side='long')
        check('DEMO-03', 'SL/TP de la estrategia aceptado', ok1, {'sl': sl, 'tp': tp})
        check('DEMO-03', 'y confirmado leyendo la posición', await c.confirm_levels(symbol, sl, tp))
        ok2 = await c.set_trading_stop(symbol, sl, tp, side='long')
        check('DEMO-03', 'pedido repetido (34040 «sin cambios»): se confirma leyendo la posición', ok2)
        check('DEMO-03', 'niveles distintos de los de la posición: NO se confirman',
              not await c.confirm_levels(symbol, rnd(sl * 0.99), tp))
        bad = await c.set_trading_stop(symbol, rnd(entry * 1.05), tp, side='long')   # SL de un long sobre el precio
        check('DEMO-03', 'SL inválido: Bybit lo rechaza y el bot NO lo da por puesto', bad is False)
        check('DEMO-03', 'la posición conserva la protección anterior', await c.confirm_levels(symbol, sl, tp))

        # ── DEMO-05: «reinicio» del motor: cliente nuevo, sin cachés ──
        c2 = BybitClient(key, secret, account_type='demo')
        record(c2)
        pos2 = await c2.get_open_position(symbol)
        check('DEMO-05', 'tras el reinicio la posición se encuentra en Bybit', bool(pos2) and float(pos2['size']) == qty,
              (pos2 or {}).get('size'))
        check('DEMO-05', 'y sus niveles de protección se verifican', await c2.confirm_levels(symbol, sl, tp))

        # ── DEMO-06: Bybit sin responder ──
        c3 = BybitClient(key, secret, account_type='demo')

        async def down(*_a, **_k):
            raise httpx.ConnectError('Bybit sin respuesta (simulado)')

        c3._signed_get = c3._signed_post = down
        try:
            await c3.get_open_position(symbol)
            r_pos = 'devolvió un valor'
        except BybitAPIError:
            r_pos = 'no sé (error)'
        check('DEMO-06', 'posición: «no sé», nunca «no hay posición»', r_pos == 'no sé (error)', r_pos)
        try:
            await c3.get_order_by_link_id(symbol, link)
            r_ord = 'devolvió un valor'
        except BybitAPIError:
            r_ord = 'no sé (error)'
        check('DEMO-06', 'orden por orderLinkId: «no sé», nunca «no existe»', r_ord == 'no sé (error)', r_ord)
        now_ms = int(time.time() * 1000)
        cp = await c3.get_closed_pnl_history(symbol, entry, now_ms - 3_600_000, strict=True)
        check('DEMO-06', 'closed-pnl: «no sé» (None), nunca «no hay cierres» ([])', cp is None, cp)
        ex = await c3.get_executions(symbol, res['orderId'], now_ms - 3_600_000, now_ms)
        check('DEMO-06', 'ejecuciones: «no sé» (None), nunca «no hay»', ex is None, ex)
        bal = await c3.get_balance()
        check('DEMO-06', 'saldo: «no sé» (None), nunca 0', bal is None, bal)
        check('DEMO-06', 'y la posición sigue abierta en Bybit (nada se marcó cerrado)', await size_of(c, symbol) == qty)

        # ── DEMO-09: tamaño con datos vigentes ──
        balance = await c.get_balance()
        price = await c.get_market_price(symbol)
        lot = await c.get_lot_size(symbol)
        check('DEMO-09', 'saldo, precio y lote reales de Demo disponibles', bool(balance and price and lot),
              {'saldo': balance, 'precio': price, 'lote': lot})
        if balance and price and lot:
            min_q, q_step = lot
            sl_p = price * 0.985
            s1 = RealTrader._risk_size(balance, 1.0, price, sl_p, 3.0, min_q, q_step)
            moved = price * 1.01                              # el precio se movió 1 % antes de abrir
            s2 = RealTrader._risk_size(balance, 1.0, moved, moved * 0.985, 3.0, min_q, q_step)
            risk1 = s1 * (price - sl_p) / balance * 100 if s1 else None
            risk2 = s2 * (moved - moved * 0.985) / balance * 100 if s2 else None
            check('DEMO-09', 'el tamaño arriesga a lo sumo el 1 % del saldo real', bool(s1) and risk1 <= 1.0 + 1e-9,
                  {'tamano': s1, 'riesgo_pct': risk1})
            check('DEMO-09', 'con el precio movido 1 % se recalcula (otro tamaño, mismo riesgo máx.)',
                  bool(s2) and s2 != s1 and risk2 <= 1.0 + 1e-9, {'tamano': s2, 'riesgo_pct': risk2})
            check('DEMO-09', 'los tamaños respetan el paso de Bybit',
                  all(abs(round(x / q_step) * q_step - x) < 1e-9 for x in (s1, s2) if x), {'paso': q_step})

        # ── DEMO-10: cuenta en Hedge (simulado con positionIdx=1 en una cuenta One-Way) ──
        before = await size_of(c, symbol)
        real_post2, sent = c._signed_post, {'n': 0}

        async def post_hedge(path, body, timeout=15):
            if path == '/v5/order/create':
                sent['n'] += 1
                body = dict(body, positionIdx=1)
            return await real_post2(path, body, timeout)

        c._signed_post = post_hedge
        rej = await c.place_market_order(symbol, 'Buy', qty)
        c._signed_post = real_post2
        await asyncio.sleep(2)
        after = await size_of(c, symbol)
        check('DEMO-10', 'Bybit rechaza la apertura y el bot la da por rechazada (None)', rej is None,
              {'respuesta': rej, 'motivo': c.last_order_error})
        check('DEMO-10', 'el motivo de Bybit queda para el aviso open_rejected', bool(c.last_order_error),
              c.last_order_error)
        check('DEMO-10', 'no quedó ninguna posición nueva (el tamaño no cambió)', after == before, {'antes': before, 'despues': after})
    finally:
        size = await size_of(c, symbol)
        if size:
            await c.place_market_order(symbol, 'Sell', size, reduce_only=True)
        final = await wait_size(c, symbol, 0.0)
        check('CIERRE', 'posición de prueba cerrada', final == 0.0, final)

    evidence['fin_utc'] = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
    out = os.getenv('TR2_DEMO_OUT') or f"/tmp/tr2_demo_c5_{time.strftime('%Y%m%d_%H%M%S', time.gmtime())}.json"
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(evidence, f, ensure_ascii=False, indent=1, default=str)
    print(f"\nEvidencia: {out} ({len(evidence['bybit'])} llamadas a Bybit)")
    print(f"RESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
