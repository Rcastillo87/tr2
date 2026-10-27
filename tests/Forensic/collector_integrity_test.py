"""
Prueba forense del collector (solo lectura): ¿lo que hay en ohlcv_data es EXACTAMENTE lo que publica Bybit?

Para cada serie activa de Bybit en collector_configs:
  1. Frescura: la última vela guardada debe ser la vela en curso o la anterior (atraso ≤ 1 intervalo + 2 min).
  2. Integridad: descarga de Bybit las últimas N velas CERRADAS y las compara una a una con la base
     (faltantes, sobrantes, y diferencias en open/high/low/close/volume).
  3. Alineación: todas las velas guardadas en ese tramo caen en múltiplos exactos del intervalo.
No escribe nada. Corre con la misma URL de Bybit que el collector.

Uso (desde python-engine/): venv/bin/python ../tests/Forensic/collector_integrity_test.py [N=300] [--solo BTCUSDT,ETHUSDT]
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())

import asyncpg  # noqa: E402
import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv('.env')

from collectors.broker_resolver import interval_delta  # noqa: E402
from collectors.ohlcv_collector import BYBIT_BASE_URL, DB_DSN  # noqa: E402

FIELDS = ('open', 'high', 'low', 'close', 'volume')
REL_TOL = 1e-9


def closed_until(now: datetime, step: timedelta) -> datetime:
    """Inicio de la última vela CERRADA (la anterior a la que está en formación)."""
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    current = epoch + ((now - epoch) // step) * step
    return current - step


async def bybit_closed(client, symbol, interval, n, last_closed):
    end_ms = int(last_closed.timestamp() * 1000)
    r = await client.get(f'{BYBIT_BASE_URL}/v5/market/kline', params={
        'category': 'linear', 'symbol': symbol, 'interval': interval, 'limit': min(n, 1000), 'end': end_ms})
    r.raise_for_status()
    data = r.json()
    if data.get('retCode') != 0:
        raise RuntimeError(f"Bybit retCode={data.get('retCode')} {data.get('retMsg')}")
    out = {}
    for b in data['result']['list']:
        t = datetime.fromtimestamp(int(b[0]) / 1000, tz=timezone.utc)
        if t <= last_closed:
            out[t] = dict(zip(FIELDS, map(float, b[1:6])))
    return out


def differs(a: float, b: float) -> bool:
    return abs(a - b) > REL_TOL * max(1.0, abs(a), abs(b))


async def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    n = int(args[0]) if args else 300
    only = None
    if '--solo' in sys.argv:
        only = set(sys.argv[sys.argv.index('--solo') + 1].split(','))
    now = datetime.now(timezone.utc)
    conn = await asyncpg.connect(DB_DSN)
    series = [(r['symbol'], r['interval']) for r in await conn.fetch(
        "SELECT symbol, interval FROM collector_configs WHERE broker = 'bybit' AND active ORDER BY symbol, interval")
        if not only or r['symbol'] in only]
    print(f"Collector vs Bybit · {len(series)} series · últimas {n} velas cerradas · {now:%Y-%m-%d %H:%M} UTC\n")
    print(f"{'serie':16} {'última en DB':17} {'atraso':>8} │ {'comparadas':>10} {'faltan':>7} {'sobran':>7} {'distintas':>9} {'desalin.':>8}  estado")
    bad = 0
    async with httpx.AsyncClient(timeout=20) as client:
        for symbol, interval in series:
            step = interval_delta(interval)
            last_closed = closed_until(now, step)
            first = last_closed - step * (n - 1)
            last_db = await conn.fetchval(
                "SELECT max(time) FROM ohlcv_data WHERE broker = 'bybit' AND symbol = $1 AND interval = $2", symbol, interval)
            lag = (now - last_db) if last_db else None
            stale = last_db is None or lag > step + timedelta(minutes=2)
            try:
                remote = await bybit_closed(client, symbol, interval, n, last_closed)
            except Exception as e:
                print(f"{symbol + ' ' + interval:16} ERROR consultando Bybit: {e}")
                bad += 1
                continue
            rows = await conn.fetch(
                """SELECT time, open, high, low, close, volume FROM ohlcv_data
                   WHERE broker = 'bybit' AND symbol = $1 AND interval = $2 AND time BETWEEN $3 AND $4""",
                symbol, interval, min(remote) if remote else first, last_closed)
            local = {r['time']: r for r in rows}
            missing = [t for t in remote if t not in local]
            extra = [t for t in local if t not in remote]
            diff = []
            for t, rb in remote.items():
                rl = local.get(t)
                if rl is not None and any(differs(float(rl[f]), rb[f]) for f in FIELDS):
                    diff.append(t)
            epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
            misaligned = [t for t in local if (t - epoch) % step]
            ok = not (stale or missing or extra or diff or misaligned)
            bad += not ok
            notes = []
            if stale:
                notes.append('DESACTUALIZADA')
            if missing:
                notes.append(f"faltan p.ej. {min(missing):%m-%d %H:%M}")
            if diff:
                t = diff[0]
                notes.append(f"distinta {t:%m-%d %H:%M}: DB c={float(local[t]['close'])} v={float(local[t]['volume'])} "
                             f"/ Bybit c={remote[t]['close']} v={remote[t]['volume']}")
            lag_s = '—' if lag is None else (f"{lag.total_seconds() / 60:.0f} min" if lag < timedelta(hours=2) else f"{lag.total_seconds() / 3600:.1f} h")
            print(f"{symbol + ' ' + interval:16} {(f'{last_db:%m-%d %H:%M}' if last_db else 'SIN DATOS'):17} {lag_s:>8} │ "
                  f"{len(remote):>10} {len(missing):>7} {len(extra):>7} {len(diff):>9} {len(misaligned):>8}  "
                  f"{'OK' if ok else 'FALLA · ' + ' · '.join(notes)}")
            await asyncio.sleep(0.15)
    await conn.close()
    print(f"\nRESULTADO: {'TODO OK' if bad == 0 else f'{bad} serie(s) con fallas'} ({len(series)} series)")
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
