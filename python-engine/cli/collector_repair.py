"""
Reparación del collector: valida contra Bybit, repara lo que falla y vuelve a validar.
NUNCA borra: solo vuelve a descargar de Bybit y guarda con save_bars (UPSERT; reescribe solo las filas distintas).

Qué repara, por serie con fallas:
  · Recientes (últimas N velas cerradas): faltantes o distintas → descarga la ventana completa y la guarda.
  · Historial: días incompletos (velas por día < esperadas, con time_bucket; sin lag()). Máximo --max-days días por
    serie y pasada, los más recientes primero. El resto queda para la pasada siguiente.
  · Días que Bybit tampoco tiene completos: se registran en storage/app/collector_bybit_gaps.json y la validación deja
    de contarlos como huecos (no hay nada que reparar).
No repara: velas que sobran o fuera de horario (borrar está prohibido) ni series detenidas (eso es del vigilante).

Uso (desde python-engine/):
  venv/bin/python cli/collector_repair.py [--max-days 7] [--recent 300] [--solo BTCUSDT] [--dry-run] [--json-out f]
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

from cli.collector_validate import (BYBIT_GAPS_FILE, SETTLE, bybit_gaps, current_bar,  # noqa: E402
                                    summarize, validate)
from collectors.broker_resolver import interval_delta  # noqa: E402
from collectors.ohlcv_collector import DB_DSN, OhlcvCollector  # noqa: E402

DAY = timedelta(days=1)


def day_floor(t: datetime) -> datetime:
    return t.replace(hour=0, minute=0, second=0, microsecond=0)


def needs_repair(s: dict) -> bool:
    return bool(s.get('missing_recent') or s.get('diff_recent') or s.get('missing_hist'))


async def incomplete_days(conn, symbol: str, interval: str, step: timedelta, until: datetime,
                          known: dict) -> list[tuple[datetime, int]]:
    """Días completos (UTC) con menos velas alineadas que las esperadas, del más reciente al más antiguo."""
    if step > DAY:
        return []
    per_day = int(DAY / step)
    first = await conn.fetchval(
        "SELECT min(time) FROM ohlcv_data WHERE broker = 'bybit' AND symbol = $1 AND interval = $2", symbol, interval)
    if first is None:
        return []
    start = day_floor(first) + (DAY if first != day_floor(first) else timedelta(0))   # el primer día puede ser parcial
    rows = await conn.fetch(
        """SELECT time_bucket('1 day', time) AS d, count(*) AS n FROM ohlcv_data
           WHERE broker = 'bybit' AND symbol = $1 AND interval = $2 AND time >= $3 AND time < $4
             AND extract(epoch FROM time)::bigint % $5 = 0
           GROUP BY 1""", symbol, interval, start, until, int(step.total_seconds()))
    have = {r['d']: int(r['n']) for r in rows}
    out, d = [], until - DAY
    while d >= start:
        missing = per_day - have.get(d, 0) - int(known.get(d.date().isoformat(), 0))
        if missing > 0:
            out.append((d, missing))
        d -= DAY
    return out


async def repair_series(conn, collector, client, s: dict, now: datetime, n_recent: int, max_days: int,
                        gaps: dict, dry: bool) -> dict:
    symbol, interval = s['symbol'], s['interval']
    step = interval_delta(interval)
    last_closed = current_bar(now, step) - step
    if now - (last_closed + step) < SETTLE:
        last_closed -= step
    rep = dict(symbol=symbol, interval=interval, recent_written=0, days=[], days_written=0, bybit_gaps_new=0,
               pending_days=0, error=None)
    key = f'{symbol}|{interval}'

    async def fetch_save(start: datetime, end: datetime) -> tuple[int, int]:
        bars = await collector.fetch_from_bybit(symbol, interval, int(start.timestamp()), int(end.timestamp()),
                                                client=client)
        bars = [b for b in bars if start <= b['time'] <= min(end, last_closed)]
        written = 0 if dry else await collector.save_bars(bars, broker='bybit')
        return len(bars), written

    try:
        if s.get('missing_recent') or s.get('diff_recent'):
            _, rep['recent_written'] = await fetch_save(last_closed - step * (n_recent - 1), last_closed)
        if s.get('missing_hist'):
            days = await incomplete_days(conn, symbol, interval, step, day_floor(now), gaps.get(key, {}))
            rep['pending_days'] = max(0, len(days) - max_days)
            for d, missing in days[:max_days]:
                got, written = await fetch_save(d, d + DAY - step)
                rep['days'].append(dict(day=d.date().isoformat(), missing=missing, bybit=got, written=written))
                rep['days_written'] += written
                lack = int(DAY / step) - got
                if lack > 0 and not dry:   # Bybit tampoco las tiene: no es un hueco reparable
                    gaps.setdefault(key, {})[d.date().isoformat()] = lack
                    rep['bybit_gaps_new'] += 1
                await asyncio.sleep(0.1)
    except Exception as e:
        rep['error'] = str(e)[:200]
    return rep


async def run(n_recent: int, max_days: int, only: set | None, dry: bool, log) -> dict:
    t0 = time.monotonic()
    before = await validate(n_recent, only)
    failing = [s for s in before['series'] if not s.get('ok') and needs_repair(s)]
    repairs = []
    if failing:
        now = datetime.now(timezone.utc)
        gaps = bybit_gaps()
        pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=2)
        try:
            collector = OhlcvCollector(pool)
            async with pool.acquire() as conn, httpx.AsyncClient(timeout=30) as client:
                for s in failing:
                    r = await repair_series(conn, collector, client, s, now, n_recent, max_days, gaps, dry)
                    repairs.append(r)
                    log(r)
        finally:
            await pool.close()
        if not dry and any(r['bybit_gaps_new'] for r in repairs):
            tmp = BYBIT_GAPS_FILE.with_suffix('.tmp')
            tmp.write_text(json.dumps(gaps, ensure_ascii=False, sort_keys=True), encoding='utf-8')
            tmp.replace(BYBIT_GAPS_FILE)

    result = before
    if repairs and not dry:   # revalida solo las monedas tocadas y reemplaza sus series en el resultado
        again = await validate(n_recent, {r['symbol'] for r in repairs})
        fresh = {(s['symbol'], s['interval']): s for s in again['series']}
        series = [fresh.get((s['symbol'], s['interval']), s) for s in before['series']]
        result = dict(before, at=again['at'], series=series, summary=summarize(series))
    result['duration_s'] = round(time.monotonic() - t0, 1)
    result['repair'] = dict(
        dry_run=dry, max_days=max_days, before=before['summary'], series=repairs,
        recent_written=sum(r['recent_written'] for r in repairs), days_written=sum(r['days_written'] for r in repairs),
        days_fixed=sum(len(r['days']) for r in repairs), pending_days=sum(r['pending_days'] for r in repairs),
        bybit_gaps_new=sum(r['bybit_gaps_new'] for r in repairs), errors=sum(1 for r in repairs if r['error']))
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--recent', type=int, default=300)
    ap.add_argument('--max-days', type=int, default=7)
    ap.add_argument('--solo', default='')
    ap.add_argument('--dry-run', action='store_true', help='descarga y cuenta, pero no escribe nada')
    ap.add_argument('--json-out')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    only = {s.strip() for s in a.solo.split(',') if s.strip()} or None

    def log(r):
        if not a.quiet:
            print(f"{r['symbol'] + ' ' + r['interval']:16} recientes {r['recent_written']:>4} · días {len(r['days']):>2} "
                  f"(+{r['days_written']} velas, pendientes {r['pending_days']}, sin datos en Bybit {r['bybit_gaps_new']})"
                  + (f" · ERROR {r['error']}" if r['error'] else ''))

    result = asyncio.run(run(a.recent, a.max_days, only, a.dry_run, log))
    if a.json_out:
        tmp = Path(a.json_out).with_suffix('.tmp')
        tmp.write_text(json.dumps(result, ensure_ascii=False, default=str), encoding='utf-8')
        tmp.replace(a.json_out)
    s, r = result['summary'], result['repair']
    print(f"\nANTES: {r['before']['ok']}/{r['before']['series']} OK · DESPUÉS: {s['ok']}/{s['series']} OK"
          f"{' (simulación)' if a.dry_run else ''} · {len(r['series'])} serie(s) reparadas · "
          f"{r['recent_written']} velas recientes · {r['days_fixed']} día(s) (+{r['days_written']} velas) · "
          f"pendientes {r['pending_days']} · sin datos en Bybit {r['bybit_gaps_new']} · {result['duration_s']} s")
    return 0 if s['ok'] == s['series'] else 1


if __name__ == '__main__':
    sys.exit(main())
