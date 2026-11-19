#!/usr/bin/env python3
"""
R-21 (p80), decisión del dueño 19-nov: VWAP Tendencia calculaba la banda de desviación con TODAS las velas del día
(`groupby('date')['typical'].transform('std')`). En el backtest eso incluye velas posteriores a la señal (mira el
futuro); en Paper y Real esas velas todavía no existen. Evidencia (lectura_paridad3, 19-nov): 8 operaciones que solo
abrió el backtest, todas «sin señal» con los datos de ese momento, 6 de 8 ganadoras.
Arreglo: la desviación de cada vela usa solo las velas del día HASTA ella (`expanding().std()` por día). En la última
vela de la ventana de Paper/Real es la misma cuenta que hacían: en vivo no cambia nada; el backtest pasa a ver lo mismo.

Dónde está el código: tabla `strategies` (lo usan el backtest y la búsqueda) y una copia congelada en
`paper_strategy_configs.params.strategy_code` (la usan Paper y Real). Se cambian las dos; cada config deja su cambio en
`strategy_config_changes` (action 'updated', source 'p80 R-21'). Las operaciones abiertas siguen con su snapshot.

Uso (desde python-engine/):
  venv/bin/python ../ops/datafix/2026_11_19_r21_vwap_std.py            # verificación con datos reales (solo lectura)
  venv/bin/python ../ops/datafix/2026_11_19_r21_vwap_std.py --apply    # verifica y aplica (una transacción)
Salida: 0 = OK (o ya aplicado) · 1 = la verificación encontró diferencias (no se aplica) · 2 = el código no es el esperado
· 3 = error (sin base, sin datos, o la config cambió durante la verificación: no se aplica nada).
"""
import argparse
import asyncio
import json
import os
import re
import sys

STRATEGY_NAME = 'VWAP Tendencia'
OLD_PREFIX = '979d8dec'   # huella (md5) del código vigente al 19-nov
OLD_LINE = "df['vwap_std_dev'] = df.groupby('date')['typical'].transform('std')"
NEW_LINE = "df['vwap_std_dev'] = df.groupby('date')['typical'].transform(lambda s: s.expanding().std())"
COMMENT = "# R-21: desviación del día HASTA cada vela (sin velas futuras): lo mismo que ven Paper y Real"
# la línea completa, con su sangría y su fin de línea (el código guardado puede venir con \r\n)
_OLD_RE = re.compile(r"^([ \t]*)" + re.escape(OLD_LINE) + r"[ \t]*(\r?)$", re.M)
SOURCE = 'p80 R-21'


def patch_code(code: str) -> str:
    """El código con la desviación corregida (misma sangría y fin de línea). Exige exactamente una línea vieja."""
    new, n = _OLD_RE.subn(lambda m: f"{m.group(1)}{COMMENT}{m.group(2)}\n{m.group(1)}{NEW_LINE}{m.group(2)}", code)
    if n != 1:
        raise ValueError(f"se esperaba 1 línea vieja de vwap_std_dev y hay {n}")
    return new


def is_patched(code: str) -> bool:
    return NEW_LINE in code and OLD_LINE not in code


def signals(code: str, params: dict, df):
    """Señales de la estrategia sobre df (indicadores + reglas, sin los filtros de H4/BTC, que no cambian)."""
    from backtesting.strategies.loader import build_strategy
    p = dict(params)
    p['strategy_code'] = code
    st = build_strategy(p)
    st.params = p
    return st.generate_signals(st.prepare(df))['signal'].to_numpy()


def live_parity(old_code: str, new_code: str, params: dict, df, last_n: int, window: int = 500) -> dict:
    """
    En cada una de las últimas `last_n` velas: la señal de Paper/Real (código viejo sobre las `window` velas hasta esa
    vela) contra la señal del backtest con el código nuevo (todo el rango). Deben ser iguales siempre.
    También cuenta las señales del backtest con el código viejo que en vivo no existían (las que miraban el futuro).
    """
    import numpy as np
    full_new = signals(new_code, params, df)
    full_old = signals(old_code, params, df)
    n = len(df)
    mism, ghost, live_sig = [], 0, 0
    for t in range(max(window, n - last_n), n):
        live = int(signals(old_code, params, df.iloc[t - window + 1:t + 1].reset_index(drop=True))[-1])
        live_sig += live != 0
        if live != int(full_new[t]):
            mism.append(str(df['time'].iloc[t]))
        ghost += int(full_old[t]) != 0 and live == 0
    return dict(checked=min(last_n, n - window), live_signals=live_sig, mismatches=mism, ghost_old=ghost,
                new_full_signals=int(np.count_nonzero(full_new[n - min(last_n, n - window):])))


async def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='R-21: VWAP Tendencia sin mirar el futuro')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--days', type=int, default=45)
    ap.add_argument('--expect', default=OLD_PREFIX, help='huella esperada del código vigente (pruebas)')
    a = ap.parse_args(argv)
    sys.path.insert(0, os.getcwd())
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.getcwd(), '.env'))
    import asyncpg
    from db import DB_DSN
    from collectors.bars import bars_frame
    from collectors.broker_resolver import interval_delta

    pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=2)
    try:
        row = await pool.fetchrow("SELECT id, code, md5(code) AS h FROM strategies WHERE name = $1", STRATEGY_NAME)
        if row is None:
            print(f"no existe la estrategia «{STRATEGY_NAME}»")
            return 2
        code = row['code']
        if is_patched(code):
            print(f"YA APLICADO: «{STRATEGY_NAME}» (#{row['id']}) ya calcula la desviación sin velas futuras")
            left = await pool.fetchval("SELECT count(*) FROM paper_strategy_configs WHERE strpos(params->>'strategy_code', $1) > 0",
                                       OLD_LINE)
            print(f"configs de Paper con el código viejo: {left}")
            return 0 if left == 0 else 2
        if not row['h'].startswith(a.expect):
            print(f"el código de «{STRATEGY_NAME}» no es el esperado (huella {row['h'][:8]}, se esperaba {a.expect}): no se toca")
            return 2
        new_code = patch_code(code)
        compile(new_code, 'vwap_tendencia', 'exec')

        configs = await pool.fetch("""SELECT id, display_name, symbol, interval, params, active FROM paper_strategy_configs
                                      WHERE md5(params->>'strategy_code') = md5($1) ORDER BY active DESC, id""", code)
        configs_other = await pool.fetch("""SELECT id, display_name FROM paper_strategy_configs
                                            WHERE strpos(params->>'strategy_code', $1) > 0 AND md5(params->>'strategy_code') <> md5($2)""",
                                         OLD_LINE, code)
        if configs_other:
            print(f"AVISO: {len(configs_other)} config(s) con otra versión del código que también tiene la línea vieja "
                  f"(no se tocan): {[(c['id'], c['display_name']) for c in configs_other]}")
        print(f"«{STRATEGY_NAME}» #{row['id']} huella {row['h'][:8]} · configs de Paper con este código: {len(configs)}")

        bad = 0
        for c in configs:
            params = json.loads(c['params']) if isinstance(c['params'], str) else dict(c['params'])
            iv = str(c['interval'])
            per_day = 86400 // int(interval_delta(iv).total_seconds())
            need = 500 + a.days * per_day + 5
            rows = await pool.fetch("""SELECT time, open, high, low, close, volume FROM ohlcv_data WHERE broker = 'bybit'
                AND symbol = $1 AND interval = $2 AND time < date_trunc('day', now()) ORDER BY time DESC LIMIT $3""",
                c['symbol'], iv, need)
            df = bars_frame(rows, f"r21 {c['symbol']}").sort_values('time').reset_index(drop=True)
            r = live_parity(code, new_code, params, df, a.days * per_day)
            bad += len(r['mismatches'])
            print(f"  #{c['id']} {c['display_name']} (activa={c['active']}): {r['checked']} velas · señales en vivo "
                  f"{r['live_signals']} · backtest nuevo {r['new_full_signals']} · diferencias {len(r['mismatches'])}"
                  f"{' ' + str(r['mismatches'][:5]) if r['mismatches'] else ''} · señales del backtest viejo que en vivo "
                  f"no existían: {r['ghost_old']}")
        if bad:
            print(f"VERIFICACIÓN FALLIDA: {bad} vela(s) donde el backtest nuevo no coincide con lo que ve Paper; no se aplica")
            return 1
        print("verificación: el backtest con el código nuevo da en cada vela la misma señal que Paper/Real")
        if not a.apply:
            print("(solo lectura: sin --apply no se cambia nada)")
            return 0

        async with pool.acquire() as conn:
            async with conn.transaction():
                cur = await conn.fetchval("SELECT md5(code) FROM strategies WHERE id = $1 FOR UPDATE", row['id'])
                if cur != row['h']:
                    raise SystemExit("el código cambió durante la verificación: no se aplica")
                await conn.execute("UPDATE strategies SET code = $1, updated_at = timezone('UTC', now()) WHERE id = $2",
                                   new_code, row['id'])
                for c in configs:
                    old = json.loads(c['params']) if isinstance(c['params'], str) else dict(c['params'])
                    new = dict(old, strategy_code=patch_code(old['strategy_code']))
                    n = await conn.execute("""UPDATE paper_strategy_configs SET params = $1::jsonb, updated_at = timezone('UTC', now())
                        WHERE id = $2 AND md5(params->>'strategy_code') = md5($3)""", json.dumps(new), c['id'], old['strategy_code'])
                    if n != 'UPDATE 1':
                        raise SystemExit(f"config #{c['id']} cambió durante la verificación: no se aplica nada")
                    await conn.execute("""INSERT INTO strategy_config_changes (paper_strategy_config_id, backtest_id, symbol, action,
                        old_params, new_params, changed_keys, source)
                        SELECT id, backtest_id, symbol, 'updated', $2::jsonb, $3::jsonb, '{strategy_code}', $4
                        FROM paper_strategy_configs WHERE id = $1""", c['id'], json.dumps(old), json.dumps(new), SOURCE)
        h = await pool.fetchval("SELECT md5(code) FROM strategies WHERE id = $1", row['id'])
        print(f"APLICADO: «{STRATEGY_NAME}» huella {row['h'][:8]} -> {h[:8]} · {len(configs)} config(s) de Paper "
              f"actualizadas (historial en strategy_config_changes, source '{SOURCE}')")
        return 0
    finally:
        await pool.close()


if __name__ == '__main__':
    try:
        sys.exit(asyncio.run(main()))
    except SystemExit as e:
        if isinstance(e.code, str):          # abortos con mensaje (la transacción ya se revirtió)
            print(f"NO APLICADO: {e.code}")
            sys.exit(3)
        raise
    except Exception as e:                   # sin base, sin velas, etc.: nunca se confunde con «verificación fallida»
        print(f"ERROR: {type(e).__name__}: {e}")
        sys.exit(3)
