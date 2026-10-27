"""
Validación en Bybit DEMO TRADING (dinero ficticio, precios reales) de las órdenes idempotentes.

  1) Apertura con place_market_order: Bybit acepta el orderLinkId y devuelve el mismo id.
  2) get_order por orderLinkId encuentra la orden llenada.
  3) Reenvío con el MISMO orderLinkId: Bybit lo rechaza y la posición NO se duplica.
  4) Cierre con place_market_order(reduce_only=True): la posición queda en cero.
  5) Segundo cierre reduceOnly con la posición ya cerrada: Bybit lo rechaza y NO abre posición contraria.

Seguridad: SOLO corre contra api-demo.bybit.com; opera la cantidad mínima; aborta si ya hay posición en el símbolo;
cierra siempre (también si algo falla a mitad). Las claves llegan por variables de entorno y nunca se imprimen.

Uso (desde python-engine/, con TR2_K / TR2_S exportadas):
  venv/bin/python ../tests/Forensic/bybit_order_idempotency_demo.py [SIMBOLO]
"""
import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv  # noqa: E402

load_dotenv('.env')

from trading.real_trader import BYBIT_DEMO_URL, BybitClient  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  -> ' + str(detail) if detail != '' else ''}")


async def position_size(c, symbol) -> float:
    pos = await c.get_open_position(symbol)
    return float(pos.get('size', 0) or 0) if pos else 0.0


async def wait_size(c, symbol, target, tries=10) -> float:
    size = None
    for _ in range(tries):
        size = await position_size(c, symbol)
        if abs(size - target) < 1e-12:
            break
        await asyncio.sleep(1)
    return size


async def main():
    symbol = (sys.argv[1] if len(sys.argv) > 1 else 'BTCUSDT').upper()
    key, secret = os.getenv('TR2_K'), os.getenv('TR2_S')
    if not key or not secret:
        sys.exit("ABORTADO: faltan TR2_K / TR2_S")
    c = BybitClient(key, secret, 'demo')
    if c.base_url != BYBIT_DEMO_URL or 'api-demo.bybit.com' not in c.base_url:
        sys.exit(f"ABORTADO: la URL no es Bybit Demo ({c.base_url})")
    if await position_size(c, symbol):
        sys.exit(f"ABORTADO: ya hay una posición abierta en {symbol}; no se toca")
    qty, _step = await c.get_min_qty(symbol)
    print(f"{symbol}: se opera la cantidad mínima {qty} en {c.base_url}\n")

    opened = False
    try:
        # 1) Apertura
        res = await c.place_market_order(symbol, 'Buy', qty)
        check('apertura aceptada con orderLinkId propio',
              bool(res and res.get('orderId') and str(res.get('orderLinkId', '')).startswith('tr2-')), res)
        if not res or not res.get('orderId'):
            return 1
        opened = True
        size = await wait_size(c, symbol, qty)
        check('posición abierta con la cantidad pedida', abs(size - qty) < 1e-12, size)

        # 2) Consulta por orderLinkId
        order = await c.get_order(symbol, link_id=res['orderLinkId'])
        check('get_order por orderLinkId la encuentra llenada',
              bool(order) and order.get('orderId') == res['orderId'] and order.get('orderStatus') == 'Filled',
              (order or {}).get('orderStatus'))

        # 3) Reenvío con el mismo orderLinkId -> no debe duplicar
        dup = await c.place_market_order(symbol, 'Buy', qty, link_id=res['orderLinkId'])
        await asyncio.sleep(2)
        size = await position_size(c, symbol)
        check('reenvío con el mismo orderLinkId: la posición NO se duplica', abs(size - qty) < 1e-12, size)
        check('reenvío con el mismo orderLinkId: devuelve la orden original, no una nueva',
              dup is None or dup.get('orderId') in (None, res['orderId']), dup)

        # 4) Cierre reduceOnly
        cl = await c.place_market_order(symbol, 'Sell', qty, reduce_only=True)
        check('cierre reduceOnly aceptado', bool(cl and cl.get('orderId')), cl)
        size = await wait_size(c, symbol, 0.0)
        check('posición en cero tras el cierre', size == 0.0, size)
        opened = size > 0

        # 5) Segundo cierre con la posición ya cerrada -> no debe abrir posición contraria
        cl2 = await c.place_market_order(symbol, 'Sell', qty, reduce_only=True)
        await asyncio.sleep(2)
        size = await position_size(c, symbol)
        check('segundo cierre reduceOnly rechazado por Bybit', cl2 is None, cl2)
        check('sin posición contraria abierta', size == 0.0, size)
        opened = size > 0
    finally:
        if opened or await position_size(c, symbol):
            print("!! cerrando por seguridad")
            pos = await c.get_open_position(symbol)
            if pos:
                side = 'Sell' if pos.get('side') == 'Buy' else 'Buy'
                await c.place_market_order(symbol, side, float(pos['size']), reduce_only=True)

    print(f"\nRESULTADO: {'TODO OK' if fails == 0 else f'{fails} FALLO(S)'}")
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
