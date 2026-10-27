"""
Validación del collector (solo lectura): ¿ohlcv_data es exactamente lo que publica Bybit, sin huecos?

Por cada serie activa de Bybit en collector_configs:
  · Frescura: atraso de la última vela guardada (al día = ≤ 1 vela + 2 min; la última es la vela en curso).
  · Recientes vs Bybit: descarga las últimas N velas CERRADAS y compara una a una (faltan / sobran / distintas en
    open, high, low, close, volume).
  · Historial completo: velas guardadas vs esperadas entre la primera y la última, y velas fuera de su horario.
    Sin funciones de ventana: faltantes = esperadas − alineadas (la clave única impide duplicados). La auditoría
    anterior con lag() sobre chunks comprimidos daba huecos falsos.

Uso (desde python-engine/):
  venv/bin/python cli/collector_validate.py                    # tabla en consola
  venv/bin/python cli/collector_validate.py --json-out f.json  # además guarda el resultado (lo usa la pantalla)
  opciones: --recent 300 · --solo BTCUSDT,ETHUSDT
"""
import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

import asyncpg  # noqa: E402
import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path.cwd() / '.env')

from collectors.broker_resolver import interval_delta  # noqa: E402
from collectors.ohlcv_collector import BYBIT_BASE_URL, DB_DSN  # noqa: E402

FIELDS = ('open', 'high', 'low', 'close', 'volume')
REL_TOL = 1e-9
SETTLE = timedelta(minutes=2)   # una vela recién cerrada se compara solo tras ≥ 1 corrida del collector
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def current_bar(now: datetime, step: timedelta) -> datetime:
    return EPOCH + ((now - EPOCH) // step) * step


def differs(a: float, b: float) -> bool:
    return abs(a - b) > REL_TOL * max(1.0, abs(a), abs(b))


async def bybit_closed(client, symbol, interval, n, last_closed):
    r = await client.get(f'{BYBIT_BASE_URL}/v5/market/kline', params={
        'category': 'linear', 'symbol': symbol, 'interval': interval, 'limit': min(n, 1000),
        'end': int(last_closed.timestamp() * 1000)})
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


async def check_series(conn, client, symbol: str, interval: str, n: int, now: datetime) -> dict:
    step = interval_delta(interval)
    step_s = int(step.total_seconds())
    last_closed = current_bar(now, step) - step
    if now - (last_closed + step) < SETTLE:   # cerró hace < 2 min: el collector aún puede estar actualizándola
        last_closed -= step
    res = dict(symbol=symbol, interval=interval, ok=False, error=None)

    hist = await conn.fetchrow(
        """SELECT min(time) AS first, max(time) AS last, count(*) AS bars,
                  count(*) FILTER (WHERE extract(epoch FROM time)::bigint % $3 <> 0) AS misaligned
           FROM ohlcv_data WHERE broker = 'bybit' AND symbol = $1 AND interval = $2""",
        symbol, interval, step_s)
    if not hist['bars']:
        res.update(error='sin datos', stale=True)
        return res
    lag = now - hist['last']
    aligned = hist['bars'] - hist['misaligned']
    expected = int((hist['last'] - hist['first']) / step) + 1
    res.update(first=hist['first'].isoformat(), last=hist['last'].isoformat(), lag_s=int(lag.total_seconds()),
               stale=lag > step + timedelta(minutes=2), bars=int(hist['bars']), expected=expected,
               missing_hist=max(0, expected - aligned), misaligned=int(hist['misaligned']))

    try:
        remote = await bybit_closed(client, symbol, interval, n, last_closed)
    except Exception as e:
        res['error'] = f'Bybit: {e}'[:200]
        return res
    rows = await conn.fetch(
        """SELECT time, open, high, low, close, volume FROM ohlcv_data
           WHERE broker = 'bybit' AND symbol = $1 AND interval = $2 AND time BETWEEN $3 AND $4""",
        symbol, interval, min(remote) if remote else last_closed, last_closed)
    local = {r['time']: r for r in rows}
    missing = sorted(t for t in remote if t not in local)
    extra = sorted(t for t in local if t not in remote)
    diff = sorted(t for t, rb in remote.items()
                  if t in local and any(differs(float(local[t][f]), rb[f]) for f in FIELDS))
    example = None
    if diff:
        t = diff[0]
        example = dict(time=t.isoformat(), db={f: float(local[t][f]) for f in FIELDS}, bybit=remote[t])
    res.update(compared=len(remote), missing_recent=len(missing), extra_recent=len(extra), diff_recent=len(diff),
               diff_example=example, first_missing=missing[0].isoformat() if missing else None)
    res['identical'] = not (missing or extra or diff)
    res['ok'] = res['identical'] and not res['stale'] and res['missing_hist'] == 0 and res['misaligned'] == 0
    return res


async def validate(n_recent: int = 300, only: set | None = None, log=None) -> dict:
    t0 = time.monotonic()
    now = datetime.now(timezone.utc)
    conn = await asyncpg.connect(DB_DSN)
    try:
        series = [(r['symbol'], r['interval']) for r in await conn.fetch(
            "SELECT symbol, interval FROM collector_configs WHERE broker = 'bybit' AND active ORDER BY symbol, interval")
            if not only or r['symbol'] in only]
        out = []
        async with httpx.AsyncClient(timeout=20) as client:
            for k, (symbol, interval) in enumerate(series, 1):
                try:
                    out.append(await check_series(conn, client, symbol, interval, n_recent, now))
                except Exception as e:
                    out.append(dict(symbol=symbol, interval=interval, ok=False, error=str(e)[:200]))
                if log:
                    log(k, len(series), out[-1])
                await asyncio.sleep(0.15)   # cortesía con Bybit
    finally:
        await conn.close()
    total = lambda key: sum(int(s.get(key) or 0) for s in out)  # noqa: E731
    summary = dict(series=len(out), ok=sum(1 for s in out if s['ok']),
                   identical=sum(1 for s in out if s.get('identical')),
                   diff_recent=total('diff_recent'), missing_recent=total('missing_recent'),
                   extra_recent=total('extra_recent'), missing_hist=total('missing_hist'),
                   misaligned=total('misaligned'), stale=sum(1 for s in out if s.get('stale')),
                   errors=sum(1 for s in out if s.get('error')))
    return dict(version=1, at=now.isoformat(), duration_s=round(time.monotonic() - t0, 1), n_recent=n_recent,
                summary=summary, series=out)


def print_row(_k, _n, s):
    if s.get('error') and 'bars' not in s:
        print(f"{s['symbol'] + ' ' + s['interval']:16} ERROR {s['error']}")
        return
    lag = s.get('lag_s', 0) / 60
    lag_s = f"{lag:.0f} min" if lag < 120 else f"{lag / 60:.1f} h"
    notes = []
    if s.get('stale'):
        notes.append('DESACTUALIZADA')
    if s.get('missing_hist'):
        notes.append(f"{s['missing_hist']} velas faltan en el historial")
    if s.get('misaligned'):
        notes.append(f"{s['misaligned']} fuera de horario")
    if s.get('diff_example'):
        e = s['diff_example']
        notes.append(f"distinta {e['time'][5:16]}: DB c={e['db']['close']} / Bybit c={e['bybit']['close']}")
    if s.get('error'):
        notes.append(s['error'])
    print(f"{s['symbol'] + ' ' + s['interval']:16} {s['last'][5:16]:12} {lag_s:>8} │ {s.get('compared', 0):>6} "
          f"{s.get('missing_recent', 0):>6} {s.get('extra_recent', 0):>6} {s.get('diff_recent', 0):>6} │ "
          f"{s['bars']:>9} {s['expected']:>9} {s['missing_hist']:>6} {s['misaligned']:>6}  "
          f"{'OK' if s['ok'] else 'FALLA · ' + ' · '.join(notes)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--recent', type=int, default=300)
    ap.add_argument('--solo', default='')
    ap.add_argument('--json-out')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    only = {s.strip() for s in a.solo.split(',') if s.strip()} or None
    if not a.quiet:
        print(f"{'serie':16} {'última':12} {'atraso':>8} │ {'recien':>6} {'faltan':>6} {'sobran':>6} {'distin':>6} │ "
              f"{'velas':>9} {'esperad':>9} {'huecos':>6} {'desal':>6}  estado")
    result = asyncio.run(validate(a.recent, only, None if a.quiet else print_row))
    if a.json_out:
        tmp = Path(a.json_out).with_suffix('.tmp')
        tmp.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        tmp.replace(a.json_out)   # escritura atómica
    s = result['summary']
    print(f"\nRESULTADO: {'TODO OK' if s['ok'] == s['series'] else f'{s['series'] - s['ok']} serie(s) con fallas'} "
          f"({s['series']} series · {s['identical']} idénticas a Bybit · huecos {s['missing_hist']} · "
          f"desalineadas {s['misaligned']} · {result['duration_s']} s)")
    return 0 if s['ok'] == s['series'] else 1


if __name__ == '__main__':
    sys.exit(main())
