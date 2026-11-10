"""
Única puerta para borrar velas de ohlcv_data (N-11, decisión del dueño 10-nov): solo la recarga (sobrantes que Bybit
ya no tiene, re-verificados) y la invalidación explícita (confirm=True). El borrado y su registro en ohlcv_deletions
van en UNA transacción: una cancelación o un error a mitad no deja un borrado parcial ni un registro que no ocurrió.
El registro guarda las velas borradas (hasta BARS_KEEP_MAX) para poder restaurarlas. Se leen con SELECT y se borran
con un DELETE simple dentro de la misma transacción: ohlcv_data es una hypertable comprimida (TimescaleDB) y así no se
depende de DELETE … RETURNING sobre chunks comprimidos.
"""
import json
from datetime import datetime

BARS_KEEP_MAX = 50_000
DELETE_BATCH = 1000          # tiempos por sentencia en la recarga (tamaño del parámetro)
SOURCES = ('reload', 'invalidate')
_COLS = "time, open, high, low, close, volume"


async def delete_bars(conn, *, broker: str, symbol: str, interval: str, source: str, reason: str,
                      times: list[datetime] | None = None, start: datetime | None = None,
                      end: datetime | None = None) -> int:
    """
    Borra las velas de la serie indicadas por `times` (recarga) o por el rango [start, end] (invalidación; None = sin
    límite) y registra el borrado. Devuelve cuántas se borraron. Todo o nada.
    """
    if source not in SOURCES:
        raise ValueError(f'origen de borrado no permitido: {source!r}')
    if times is not None and (start is not None or end is not None):
        raise ValueError('times o rango, no los dos')
    base, args = "broker = $1 AND symbol = $2 AND interval = $3", [broker, symbol, interval]
    if times is not None:
        if not times:
            return 0
        wheres = [(base + " AND time = ANY($4::timestamptz[])", args + [times[i:i + DELETE_BATCH]])
                  for i in range(0, len(times), DELETE_BATCH)]
        expected = len(times)
    else:
        where, a = base, list(args)
        if start is not None:
            a.append(start)
            where += f" AND time >= ${len(a)}"
        if end is not None:
            a.append(end)
            where += f" AND time <= ${len(a)}"
        wheres = [(where, a)]
        expected = None

    async with conn.transaction():
        if expected is None:
            expected = await conn.fetchval(f"SELECT count(*) FROM ohlcv_data WHERE {wheres[0][0]}", *wheres[0][1])
        keep = expected <= BARS_KEEP_MAX
        bars, count, first, last = [], 0, None, None
        for where, a in wheres:
            if keep:
                rows = await conn.fetch(f"SELECT {_COLS} FROM ohlcv_data WHERE {where} ORDER BY time", *a)
                bars.extend({'t': r['time'].isoformat(), 'o': str(r['open']), 'h': str(r['high']), 'l': str(r['low']),
                             'c': str(r['close']), 'v': str(r['volume'])} for r in rows)
                ts = [r['time'] for r in rows]
            else:
                row = await conn.fetchrow(f"SELECT min(time) AS lo, max(time) AS hi FROM ohlcv_data WHERE {where}", *a)
                ts = [t for t in (row['lo'], row['hi']) if t is not None]
            res = await conn.execute(f"DELETE FROM ohlcv_data WHERE {where}", *a)
            n = int(str(res).split()[-1]) if res else 0
            count += n
            if ts:
                first = min([first, *ts]) if first else min(ts)
                last = max([last, *ts]) if last else max(ts)
        if count:
            await conn.execute(
                """INSERT INTO ohlcv_deletions (broker, symbol, interval, source, reason, deleted_count, first_time,
                                                last_time, bars, bars_saved)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)""",
                broker, symbol, interval, source, reason, count, first, last,
                json.dumps(sorted(bars, key=lambda b: b['t'])) if keep else None, keep)
    return count
