"""
REAL-06: capital base de Real = saldo REALIZADO de la cuenta UNIFIED (misma base que el backtest), nunca el saldo libre
ni un campo de margen. Sin red: respuestas de Bybit simuladas con los campos que devuelve hoy.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/real_balance_test.py
Antes del parche debe FALLAR (colateral en otra moneda devuelve un campo de margen); después, todo PASS.
"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.getcwd())  # python-engine/
logging.disable(logging.CRITICAL)

import trading.real_trader as rt  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


class Resp:
    def __init__(self, data, status=200, text='x'):
        self.data, self.status_code, self.text = data, status, text

    def json(self):
        return self.data


def wallet(coin=None, **account):
    return {'retCode': 0, 'result': {'list': [{**account, 'coin': [coin] if coin else []}]}}


def usdt(**kw):
    return {'coin': 'USDT', 'availableToWithdraw': '', **kw}


async def balance(resp):
    c = rt.BybitClient('k', 's', 'demo')

    async def _get(path, params, timeout=10):
        return resp
    c._signed_get = _get
    return await c.get_balance()


async def main():
    # B1. Cuenta unificada hoy, sin posiciones (availableToWithdraw vacío, como devuelve Bybit desde 2025)
    b = await balance(Resp(wallet(usdt(walletBalance='1000', equity='1000', totalOrderIM='0'),
                                  totalEquity='1000', totalAvailableBalance='1000', totalWalletBalance='1000')))
    check('B1 sin posiciones: saldo realizado de USDT (1000)', b == 1000.0, b)

    # B2. Con posiciones abiertas: margen usado y PnL flotante NO cambian la base (igual que el backtest)
    b = await balance(Resp(wallet(usdt(walletBalance='1000', equity='950', totalOrderIM='0', totalPositionIM='600'),
                                  totalEquity='950', totalAvailableBalance='350', totalWalletBalance='1000')))
    check('B2 con posiciones: sigue siendo el saldo realizado (1000), no el libre (350) ni el patrimonio (950)',
          b == 1000.0, b)

    # B3. Colateral en otra moneda (USDT en 0): saldo total realizado de la cuenta, nunca un campo de margen
    b = await balance(Resp(wallet(usdt(walletBalance='0', equity='0', totalOrderIM='5'),
                                  totalEquity='1000', totalAvailableBalance='1000', totalWalletBalance='1000')))
    check('B3 colateral en USDC: totalWalletBalance (1000), no totalOrderIM (5)', b == 1000.0, b)

    # B4. availableToWithdraw con valor (cuentas no unificadas antiguas): no se usa; manda walletBalance
    b = await balance(Resp(wallet({'coin': 'USDT', 'availableToWithdraw': '300', 'walletBalance': '1000'},
                                  totalWalletBalance='1000')))
    check('B4 availableToWithdraw con valor: se ignora (manda walletBalance)', b == 1000.0, b)

    # B5. Sin USDT en la lista y con saldo total: totalWalletBalance
    b = await balance(Resp(wallet(None, totalWalletBalance='750', totalEquity='760')))
    check('B5 sin entrada USDT: totalWalletBalance (750)', b == 750.0, b)

    # B6. Cuenta vacía: 0.0 (no abre), distinto de "no se pudo saber"
    b = await balance(Resp(wallet(usdt(walletBalance='0', equity='0', totalOrderIM='0'), totalWalletBalance='0')))
    check('B6 cuenta sin saldo: 0.0', b == 0.0, b)

    # B7-B10. No se pudo saber: None (nunca un número inventado)
    for label, resp in (('error de Bybit (retCode≠0)', Resp({'retCode': 10002, 'retMsg': 'timestamp'})),
                        ('lista vacía', Resp({'retCode': 0, 'result': {'list': []}})),
                        ('HTTP 401', Resp({}, status=401)),
                        ('respuesta vacía', Resp({}, text=''))):
        b = await balance(resp)
        check(f'B7 {label}: None', b is None, b)

    # B11. Valores no numéricos o negativos no se toman como saldo
    b = await balance(Resp(wallet(usdt(walletBalance='abc'), totalWalletBalance='-5')))
    check('B11 valores no numéricos/negativos: 0.0', b == 0.0, b)

    print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    asyncio.run(main())
