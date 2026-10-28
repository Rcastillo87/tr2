"""
Bybit DEMO TRADING (dinero ficticio, precios reales): confirma que la posición trae liqPrice y leverage, los
campos que usa el chequeo de liquidación de la apertura, y evalúa el chequeo con un SL del 1,5 %.

Seguridad: SOLO contra api-demo.bybit.com; cantidad mínima; aborta si ya hay posición en el símbolo; cierra
siempre (reduceOnly). Las claves llegan por variables de entorno y nunca se imprimen.
Uso (desde python-engine/, con TR2_K / TR2_S exportadas):
  venv/bin/python ../tests/Forensic/real_liq_demo.py [SIMBOLO]
"""
import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv  # noqa: E402

load_dotenv('.env')

from trading.real_trader import BYBIT_DEMO_URL, BybitClient, RealTrader  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  -> ' + str(detail) if detail != '' else ''}")


async def main():
    symbol = (sys.argv[1] if len(sys.argv) > 1 else 'BTCUSDT').upper()
    key, secret = os.getenv('TR2_K'), os.getenv('TR2_S')
    if not key or not secret:
        sys.exit("ABORTADO: faltan TR2_K / TR2_S")
    c = BybitClient(key, secret, 'demo')
    if c.base_url != BYBIT_DEMO_URL or 'api-demo.bybit.com' not in c.base_url:
        sys.exit(f"ABORTADO: la URL no es Bybit Demo ({c.base_url})")
    if await c.get_open_position(symbol):
        sys.exit(f"ABORTADO: ya hay una posición abierta en {symbol}; no se toca")
    qty, _ = await c.get_min_qty(symbol)
    opened = False
    try:
        res = await c.place_market_order(symbol, 'Buy', qty)
        check('apertura aceptada', bool(res and res.get('orderId')), res)
        if not res or not res.get('orderId'):
            return 1
        opened = True
        pos = None
        for _ in range(10):
            pos = await c.get_open_position(symbol)
            if pos:
                break
            await asyncio.sleep(1)
        check('posición abierta', bool(pos))
        if not pos:
            return 1
        avg = float(pos.get('avgPrice') or 0)
        liq = float(pos.get('liqPrice') or 0)
        lev = pos.get('leverage')
        print(f"     avgPrice={avg} liqPrice={pos.get('liqPrice')!r} leverage={lev!r} tradeMode={pos.get('tradeMode')!r}")
        check('Bybit devuelve el campo liqPrice', 'liqPrice' in pos, sorted(pos.keys()))
        check('Bybit devuelve el campo leverage', 'leverage' in pos)
        sl = round(avg * 0.985, 2)
        risk = RealTrader._sl_beyond_liquidation('long', sl, liq)
        print(f"     SL 1,5 % = {sl} · ¿más allá de la liquidación? {'SÍ (se cerraría al abrir)' if risk else 'no'}")
    finally:
        if opened:
            pos = await c.get_open_position(symbol)
            if pos:
                cl = await c.place_market_order(symbol, 'Sell', float(pos['size']), reduce_only=True)
                check('cierre reduceOnly', bool(cl and cl.get('orderId')), cl)
            await asyncio.sleep(2)
            check('sin posición al terminar', not await c.get_open_position(symbol))
    print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
