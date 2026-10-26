"""
Prueba de ida y vuelta en Bybit DEMO TRADING (dinero ficticio, precios reales).

Abre la cantidad MÍNIMA de un símbolo a mercado, fija SL/TP con trading-stop (como Real), espera unos segundos,
cierra a mercado (reduceOnly) y compara lo que cobró/pagó Bybit con lo que calcula TR2:
  - comisión por lado y tasa (0.055% taker que usa el backtest)
  - slippage real de entrada y salida contra el último precio justo antes de cada orden
  - closedPnl de Bybit = bruto − comisiones (fórmula del motor)
  - SL/TP quedan exactamente en el nivel pedido
Seguridad: SOLO corre contra api-demo.bybit.com; aborta si ya hay una posición en el símbolo; cierra siempre
(también si algo falla a mitad). Las claves llegan por variables de entorno y nunca se imprimen.

Uso (desde python-engine/, con TR2_K / TR2_S exportadas):
  venv/bin/python ../tests/Forensic/real_demo_roundtrip.py [SIMBOLO] [segundos_abierta]
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.getcwd())

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv('.env')

from trading.real_trader import BYBIT_DEMO_URL, BybitClient  # noqa: E402

TAKER_TR2 = 0.055 / 100   # comisión por lado que usa el backtest
SL_PCT, TP_PCT = 1.5, 3.0
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  -> ' + detail if detail else ''}")


async def get(c: BybitClient, path: str, params: dict) -> dict:
    query = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))  # el mismo string que se firma
    async with httpx.AsyncClient(timeout=10) as h:
        r = await h.get(f"{c.base_url}{path}?{query}", headers=c._sign(params))
    return r.json()


async def post(c: BybitClient, path: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=10) as h:
        r = await h.post(f"{c.base_url}{path}", content=json.dumps(body, separators=(',', ':')).encode(),
                         headers=c._sign_body(body))
    return r.json()


async def last_price(c, symbol):
    d = await get(c, '/v5/market/tickers', {'category': 'linear', 'symbol': symbol})
    return float(d['result']['list'][0]['lastPrice'])


async def wait_position(c, symbol, want_open: bool, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        pos = await c.get_open_position(symbol)
        if bool(pos) == want_open:
            return pos
        await asyncio.sleep(0.5)
    raise RuntimeError(f"la posición no quedó {'abierta' if want_open else 'cerrada'} en {timeout}s")


async def fill_info(c, symbol, order_id):
    """
    (precio medio, cantidad, comisión, tasa, fuente) de una orden ejecutada.
    1º ejecuciones (/v5/execution/list: precio y comisión por llenado); si Demo Trading aún no las devuelve,
    historial de la orden (/v5/order/history: avgPrice, cumExecQty, cumExecFee).
    """
    for _ in range(10):
        d = await get(c, '/v5/execution/list', {'category': 'linear', 'symbol': symbol, 'orderId': order_id})
        rows = [r for r in d.get('result', {}).get('list', []) if float(r.get('execQty') or 0) > 0]
        if rows:
            q = sum(float(r['execQty']) for r in rows)
            px = sum(float(r['execPrice']) * float(r['execQty']) for r in rows) / q
            fee = sum(float(r['execFee']) for r in rows)
            return px, q, fee, float(rows[0]['feeRate']), f"ejecuciones ({len(rows)})"
        await asyncio.sleep(0.5)
    for _ in range(10):
        d = await get(c, '/v5/order/history', {'category': 'linear', 'symbol': symbol, 'orderId': order_id})
        rows = d.get('result', {}).get('list', [])
        if rows and float(rows[0].get('cumExecQty') or 0) > 0:
            o = rows[0]
            px, q, fee = float(o['avgPrice']), float(o['cumExecQty']), float(o['cumExecFee'])
            return px, q, fee, fee / (px * q), "historial de la orden"
        await asyncio.sleep(0.5)
    raise RuntimeError(f"Bybit no devolvió el llenado de la orden {order_id} (ejecuciones ni historial)")


async def close_market(c, symbol, qty):
    return await post(c, '/v5/order/create', {'category': 'linear', 'symbol': symbol, 'side': 'Sell',
                                              'orderType': 'Market', 'qty': str(qty), 'reduceOnly': True})


async def main() -> int:
    args = [a for a in sys.argv[1:] if a != '--cerrar']
    symbol = args[0] if args else 'BTCUSDT'
    hold = int(args[1]) if len(args) > 1 else 10
    only_close = '--cerrar' in sys.argv
    if not os.getenv('TR2_K'):
        sys.exit("Faltan las claves (TR2_K / TR2_S)")
    c = BybitClient(os.environ['TR2_K'], os.environ['TR2_S'], 'demo')
    if c.base_url != BYBIT_DEMO_URL or 'api-demo' not in c.base_url:
        sys.exit(f"ABORTADO: la URL no es la de Demo Trading ({c.base_url})")

    if only_close:  # cerrar una posición de prueba que haya quedado abierta
        pos = await c.get_open_position(symbol)
        if not pos:
            print(f"No hay posición abierta en {symbol}.")
            return 0
        side = 'Sell' if pos.get('side') == 'Buy' else 'Buy'
        d = await post(c, '/v5/order/create', {'category': 'linear', 'symbol': symbol, 'side': side, 'orderType': 'Market',
                                               'qty': pos.get('size'), 'reduceOnly': True})
        print(f"Cierre enviado ({side} {pos.get('size')}): retCode={d.get('retCode')} {d.get('retMsg')}")
        await wait_position(c, symbol, False)
        print("Posición cerrada.")
        return 0

    bal0 = await c.get_balance()
    print(f"Cuenta Demo Trading · {c.base_url} · saldo USDT={bal0}")
    if not bal0:
        sys.exit("ABORTADO: no se pudo leer el saldo (clave inválida o sin permisos)")
    prev = await c.get_open_position(symbol)
    if prev:
        sys.exit(f"ABORTADO: ya hay una posición abierta en {symbol} (lado {prev.get('side')}, tamaño {prev.get('size')}); no se toca. "
                 f"Para cerrarla: volver a correr con el argumento --cerrar")
    min_qty, step = await c.get_min_qty(symbol)
    qty = min_qty
    print(f"{symbol}: cantidad mínima {min_qty} (paso {step}) → se opera {qty}\n")

    opened = False
    try:
        # ── 1) Apertura a mercado (mismo método que usa Real) ──────────────────
        ref_in = await last_price(c, symbol)
        t_send = time.time()
        res = await c.place_market_order(symbol, 'Buy', qty)
        if not res:
            sys.exit("ABORTADO: Bybit rechazó la orden de apertura (ver log)")
        opened = True
        pos = await wait_position(c, symbol, True)
        lat_in = time.time() - t_send
        entry, q_in, fee_in, rate_in, src_in = await fill_info(c, symbol, res['orderId'])
        print(f"[1] Apertura: ref {ref_in} → llenado {entry} ({src_in}, {lat_in:.2f}s) · comisión {fee_in}")

        # ── 2) SL/TP definitivos con trading-stop (como Real) ─────────────────
        sl, tp = round(entry * (1 - SL_PCT / 100), 1), round(entry * (1 + TP_PCT / 100), 1)
        ok = await c.set_trading_stop(symbol, sl, tp, side='long')
        pos = await c.get_open_position(symbol)
        print(f"[2] SL/TP pedidos {sl} / {tp} → en Bybit {pos.get('stopLoss')} / {pos.get('takeProfit')}")
        check('trading-stop aceptado por Bybit', ok)
        check('SL en Bybit = SL pedido', abs(float(pos.get('stopLoss') or 0) - sl) < 1e-6, str(pos.get('stopLoss')))
        check('TP en Bybit = TP pedido', abs(float(pos.get('takeProfit') or 0) - tp) < 1e-6, str(pos.get('takeProfit')))

        await asyncio.sleep(hold)

        # ── 3) Cierre a mercado reduceOnly ────────────────────────────────────
        ref_out = await last_price(c, symbol)
        t_send = time.time()
        d = await close_market(c, symbol, qty)
        if d.get('retCode') != 0:
            raise RuntimeError(f"cierre rechazado: {d.get('retMsg')}")
        await wait_position(c, symbol, False)
        opened = False
        lat_out = time.time() - t_send
        exit_, q_out, fee_out, rate_out, src_out = await fill_info(c, symbol, d['result']['orderId'])
        print(f"[3] Cierre: ref {ref_out} → llenado {exit_} ({src_out}, {lat_out:.2f}s) · comisión {fee_out}")
    finally:
        if opened:  # pase lo que pase, no dejar la posición abierta
            print("!! cerrando la posición por seguridad")
            await close_market(c, symbol, qty)

    # ── 4) Comparación con el modelo de TR2 ───────────────────────────────────
    await asyncio.sleep(2)
    since_ms = int((time.time() - 600) * 1000)
    cp = await c.get_closed_pnl_history(symbol, entry, since_ms, limit=20)
    closed = float(cp[0]['closedPnl']) if cp else None
    gross = (exit_ - entry) * qty
    fees_model = (entry + exit_) * qty * TAKER_TR2
    slip_in = (entry - ref_in) / ref_in * 100
    slip_out = (ref_out - exit_) / ref_out * 100
    print(f"\n[4] Bruto {gross:.6f} · comisiones Bybit {fee_in + fee_out:.6f} vs modelo TR2 {fees_model:.6f} · closedPnl Bybit {closed}")
    print(f"    Slippage real (en contra = positivo): entrada {slip_in:+.4f}% · salida {slip_out:+.4f}% (backtest supone 0.05% por lado)")
    check('cantidad llenada = pedida (entrada y salida)', abs(q_in - qty) < 1e-12 and abs(q_out - qty) < 1e-12)
    check('tasa de comisión = 0.055% taker (la del backtest)', abs(rate_in - TAKER_TR2) < 1e-6 and abs(rate_out - TAKER_TR2) < 1e-6,
          f"entrada {rate_in * 100:.4f}% · salida {rate_out * 100:.4f}%")
    check('comisión Bybit = (entrada + salida) × qty × 0.055% (fórmula del motor)',
          abs((fee_in + fee_out) - fees_model) <= max(1e-6, fees_model * 0.01), f"{fee_in + fee_out:.8f} vs {fees_model:.8f}")
    check('closedPnl de Bybit = bruto − comisiones (lo que guarda Real)', closed is not None and abs(closed - (gross - fee_in - fee_out)) <= 1e-4,
          f"{closed} vs {gross - fee_in - fee_out:.6f}")
    check('slippage por lado dentro del 0.05% supuesto', max(slip_in, slip_out) <= 0.05,
          f"entrada {slip_in:+.4f}% · salida {slip_out:+.4f}%")
    bal1 = await c.get_balance()
    print(f"\nSaldo USDT: {bal0} → {bal1} (Δ {bal1 - bal0:+.6f})")
    print(f"RESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
