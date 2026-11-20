#!/usr/bin/env python3
"""
¿Alguna estrategia mira el futuro? Revisión a mano (solo lectura) con la misma prueba que usan el guardado de
estrategias y la revisión diaria (`backtesting/lookahead.py`): configs activas de Paper y estrategias sin config activa.

Uso (desde python-engine/):
  venv/bin/python tools/analysis/lookahead_probe.py [--last 150] [--warmup 300] [--control <archivo de código>]
`--control`: un código que SÍ mira el futuro (p. ej. tests/Forensic/fixtures/vwap_tendencia_19nov.py); debe detectarse.
Código de salida: 0 = ninguna mira el futuro · 1 = alguna mira el futuro (o el control no se detectó) · 2 = error.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())


async def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='¿Las estrategias miran el futuro?')
    ap.add_argument('--last', type=int, default=150, help='velas revisadas por config (las más recientes)')
    ap.add_argument('--warmup', type=int, default=300, help='velas previas para los indicadores')
    ap.add_argument('--control', help='código que SÍ mira el futuro: debe detectarse (prueba de la prueba)')
    a = ap.parse_args(argv)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.getcwd(), '.env'))
    import asyncpg
    from db import DB_DSN
    from backtesting import lookahead as la
    conn = await asyncpg.connect(DB_DSN, server_settings={'default_transaction_read_only': 'on'})
    slot = asyncio.Semaphore(1)
    bad = 0
    try:
        if a.control:
            units = await la.load_units(conn)
            ref = next((u for u in units if 'vwap' in u['code'].lower()), units[0] if units else None)
            if ref:
                df = await la.load_bars(conn, ref['symbol'], ref['interval'], a.warmup + a.last)
                r = await la._check(slot, open(a.control, encoding='utf-8').read(), ref['params'], df, a.last)
                ok = la.looks_ahead(r)
                bad += 0 if ok else 1
                print(f"  CONTROL (con {ref['label']}): {la.verdict(r)} → "
                      f"{'la prueba SÍ detecta la trampa' if ok else 'FALLA: la prueba NO detectó la trampa'}")
        out = await la.audit(conn, slot, a.warmup, a.last)
        print(f"{out['checked']} revisadas · {a.last} velas cada una (+{a.warmup} de calentamiento)")
        for x in out['results']:
            print(f"  {x['label']}: {x['verdict']}")
        bad += len(out['bad']) + len(out['errors'])
    finally:
        await conn.close()
    print("RESULTADO:", "ninguna estrategia mira el futuro" if not bad else f"{bad} con problemas (ver arriba)")
    return 1 if bad else 0


if __name__ == '__main__':
    try:
        sys.exit(asyncio.run(main()))
    except SystemExit:
        raise
    except Exception as e:   # noqa: BLE001
        print(f"ERROR: {type(e).__name__}: {e}")
        sys.exit(2)
