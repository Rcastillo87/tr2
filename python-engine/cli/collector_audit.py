"""
Auditoría histórica rotativa del collector (C-03): compara vela por vela (open, high, low, close, volume) TODO el
histórico de ohlcv_data contra Bybit, por porciones cada noche, sin pasar del presupuesto.

  · Ventanas de BYBIT_LIMIT velas, de la más vieja hacia adelante, con un cursor por serie que persiste entre noches
    (storage/app/collector_audit_cursor.json). Al llegar a la zona que ya cubre el chequeo de recientes (últimas N
    velas) vuelve a empezar: así todo el histórico se revisa cada ~18.200 / presupuesto días.
  · Reparto por turnos entre series (una ventana por serie y turno) hasta agotar el presupuesto o el tiempo.
  · Distintas o faltantes: con repair se vuelven a guardar con el UPSERT del collector (NUNCA borra; reescribe solo
    filas distintas). Sobrantes (en la base y no en Bybit): se reportan, no se borran.
  · Presupuesto por noche: COLLECTOR_AUDIT_BUDGET consultas (por defecto 1.500, ~5 min). Lo ejecuta la reparación
    diaria (cli/collector_repair.py, 04:00, cola research, prioridad mínima de CPU y disco).
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cli.collector_validate import FIELDS, SETTLE, current_bar, differs
from collectors.broker_resolver import interval_delta
from collectors.bybit_http import BybitRateLimited, get_json
from collectors.ohlcv_collector import BYBIT_BASE_URL, BYBIT_LIMIT

logger = logging.getLogger(__name__)

AUDIT_CURSOR_FILE = Path(__file__).resolve().parents[2] / 'storage/app/collector_audit_cursor.json'
AUDIT_BUDGET = int(os.getenv('COLLECTOR_AUDIT_BUDGET', '1500'))
AUDIT_PACE_S = 0.2   # ~5 consultas por segundo: muy por debajo del límite público de Bybit


def load_cursor(path: Path = AUDIT_CURSOR_FILE) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_cursor(cursor: dict, path: Path = AUDIT_CURSOR_FILE) -> None:
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(cursor, ensure_ascii=False, sort_keys=True), encoding='utf-8')
    tmp.replace(path)   # escritura atómica


def _ts(t: datetime) -> int:
    return int(t.timestamp() * 1000)


async def bybit_window(client, symbol: str, interval: str, start: datetime, end: datetime) -> dict:
    payload = await get_json(client, f'{BYBIT_BASE_URL}/v5/market/kline', params={
        'category': 'linear', 'symbol': symbol, 'interval': interval, 'limit': BYBIT_LIMIT,
        'start': _ts(start), 'end': _ts(end)})
    out = {}
    for b in payload.get('result', {}).get('list', []):
        t = datetime.fromtimestamp(int(b[0]) / 1000, tz=timezone.utc)
        if start <= t <= end:
            out[t] = dict(zip(FIELDS, map(float, b[1:6])))
    return out


async def audit_window(conn, collector, client, symbol: str, interval: str, start: datetime, end: datetime,
                       repair: bool) -> dict:
    remote = await bybit_window(client, symbol, interval, start, end)
    rows = await conn.fetch(
        """SELECT time, open, high, low, close, volume FROM ohlcv_data
           WHERE broker = 'bybit' AND symbol = $1 AND interval = $2 AND time BETWEEN $3 AND $4""",
        symbol, interval, start, end)
    local = {r['time']: r for r in rows}
    missing = [t for t in remote if t not in local]
    diff = [t for t, rb in remote.items() if t in local and any(differs(float(local[t][f]), rb[f]) for f in FIELDS)]
    extra = [t for t in local if t not in remote]
    to_fix = sorted(missing + diff)
    written = 0
    if repair and to_fix:
        written = await collector.save_bars(
            [dict(time=t, symbol=symbol, interval=interval, **remote[t]) for t in to_fix], broker='bybit')
    example = None
    if diff:
        t = min(diff)
        example = dict(time=t.isoformat(), db={f: float(local[t][f]) for f in FIELDS}, bybit=remote[t])
    return dict(compared=len(remote), missing=len(missing), diff=len(diff), extra=len(extra), repaired=written,
                unrepaired=max(0, len(to_fix) - written), diff_example=example)


async def run_audit(conn, collector, client, series: list[tuple[str, str]], now: datetime, n_recent: int,
                    cursor: dict, budget: int = AUDIT_BUDGET, deadline: float | None = None, repair: bool = True,
                    pace=None, clock=time.monotonic) -> dict:
    """Audita por turnos hasta gastar `budget` consultas o llegar a `deadline` (reloj monotónico). Actualiza `cursor`."""
    import asyncio
    pace = pace or (lambda: asyncio.sleep(AUDIT_PACE_S))
    per: dict[str, dict] = {}
    plan = []   # (key, symbol, interval, step, recent_start, first)
    for symbol, interval in series:
        step = interval_delta(interval)
        last_closed = current_bar(now, step) - step
        if now - (last_closed + step) < SETTLE:
            last_closed -= step
        recent_start = last_closed - step * (n_recent - 1)   # desde aquí lo cubre el chequeo de recientes
        first = await conn.fetchval(
            "SELECT min(time) FROM ohlcv_data WHERE broker = 'bybit' AND symbol = $1 AND interval = $2", symbol, interval)
        key = f'{symbol}|{interval}'
        per[key] = dict(symbol=symbol, interval=interval, windows=0, compared=0, missing=0, diff=0, extra=0,
                        repaired=0, unrepaired=0, diff_example=None, error=None)
        if first is not None:
            plan.append((key, symbol, interval, step, recent_start, first))

    used, stopped = 0, None
    active = list(plan)
    while active:
        progressed = []
        for item in active:
            key, symbol, interval, step, recent_start, first = item
            if used >= budget:
                stopped = 'presupuesto'
                break
            if deadline is not None and clock() >= deadline:
                stopped = 'tiempo'
                break
            c = cursor.setdefault(key, {})
            start = datetime.fromisoformat(c['next']) if c.get('next') else first
            start = max(start, first)
            end = min(start + step * (BYBIT_LIMIT - 1), recent_start - step)
            if start > end:   # llegó a la zona de recientes: vuelta completa; la próxima noche empieza de nuevo
                if c.get('next'):   # (una serie sin histórico fuera de la zona de recientes no completa nada)
                    c.update(next=first.isoformat(), last_cycle_done=now.isoformat())
                continue            # como máximo una vuelta por serie y noche: el presupuesto pasa a las demás
            try:
                r = await audit_window(conn, collector, client, symbol, interval, start, end, repair)
            except BybitRateLimited as e:
                per[key]['error'] = f'Bybit limita: {e}'[:200]
                stopped = 'límite de tasa de Bybit'
                break
            except Exception as e:   # noqa: BLE001 - una serie con error no frena las demás
                per[key]['error'] = str(e)[:200]
                used += 1
                continue
            used += 1
            p = per[key]
            p['windows'] += 1
            for k in ('compared', 'missing', 'diff', 'extra', 'repaired', 'unrepaired'):
                p[k] += r[k]
            p['diff_example'] = p['diff_example'] or r['diff_example']
            c['next'] = (end + step).isoformat()
            c['found_total'] = int(c.get('found_total', 0)) + r['missing'] + r['diff']
            progressed.append(item)
            await pace()
        if stopped:
            break
        active = progressed

    for key, p in per.items():
        c = cursor.get(key, {})
        p.update(next=c.get('next'), last_cycle_done=c.get('last_cycle_done'))
    tot = lambda k: sum(p[k] for p in per.values())  # noqa: E731
    return dict(budget=budget, requests=used, stopped=stopped or 'sin trabajo pendiente', repair=repair,
                windows=tot('windows'), compared=tot('compared'), missing=tot('missing'), diff=tot('diff'),
                extra=tot('extra'), repaired=tot('repaired'), unrepaired=tot('unrepaired'),
                errors=sum(1 for p in per.values() if p['error']), series=per)
