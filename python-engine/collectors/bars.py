"""
Velas leídas de ohlcv_data -> DataFrame en orden cronológico garantizado.

Por qué existe: TimescaleDB (ordered append sobre fragmentos parcialmente comprimidos, con plan genérico) llegó a
devolver filas de `ORDER BY time` fuera de orden. La base tiene timescaledb.enable_ordered_append = off, pero el
motor no debe depender de una opción del servidor: toda lectura de velas pasa por aquí, se ordena por tiempo y se
avisa en el log si llegó desordenada o con horas repetidas (nunca se corrige en silencio).
"""
import logging

import pandas as pd

logger = logging.getLogger(__name__)

OHLCV_COLUMNS = ['time', 'open', 'high', 'low', 'close', 'volume']


def bars_frame(rows, label: str, columns: list[str] = OHLCV_COLUMNS) -> pd.DataFrame:
    """Filas (asyncpg.Record / tuplas) -> DataFrame ascendente por time, sin horas repetidas, precios en float."""
    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return df
    if not df['time'].is_monotonic_increasing:
        # Las lecturas DESC LIMIT llegan al revés a propósito: solo se avisa si tampoco están en orden inverso.
        if not df['time'].is_monotonic_decreasing:
            logger.warning(f"[BARS] {label}: {len(df)} velas llegaron fuera de orden desde la DB; se ordenan por tiempo")
        df = df.sort_values('time', kind='stable')
    dup = df['time'].duplicated(keep='last')
    if dup.any():
        logger.warning(f"[BARS] {label}: {int(dup.sum())} velas con hora repetida; se conserva la última")
        df = df[~dup]
    df = df.reset_index(drop=True)
    for col in columns[1:]:
        df[col] = df[col].astype(float)
    return df


def sorted_records(rows, label: str) -> list:
    """Lista de Records ordenada por time (velas de 1m del monitor de paper, que se recorren fila a fila)."""
    times = [r['time'] for r in rows]
    if all(a < b for a, b in zip(times, times[1:])):
        return list(rows)
    logger.warning(f"[BARS] {label}: {len(rows)} velas de 1m fuera de orden o repetidas; se ordenan por tiempo")
    unique = {r['time']: r for r in rows}  # hora repetida: la última leída
    return [unique[t] for t in sorted(unique)]
