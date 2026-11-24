#!/usr/bin/env python3
"""
Paridad Paper vs backtest de una config de Paper (BP-06): mismas reglas → mismos eventos.
Corre el backtest (/v1/backtest/run) con los parámetros CONGELADOS de los trades de Paper (config_snapshot) en el mismo
rango y empareja las operaciones por (lado, vela de entrada). Compara motivo y hora EXACTA de salida (Paper y backtest
guardan la hora del evento: p19, p24), precios y PnL en % (el PnL absoluto no es comparable: Paper dimensiona con un
saldo fijo y el backtest con el acumulado). Una posición abierta en Paper frente a un end_of_data del backtest se
informa aparte (no es divergencia).
Rango: termina en el último día COMPLETO (ayer UTC). Con el día en curso, el backtest no tiene el 1m completo de todo el
rango y evalúa sin él (corrida 1 del 19-nov, inválida); un --end de hoy o posterior se recorta a ayer.
Cambios de parámetros: un tramo por snapshot (tramos consecutivos de trades con los mismos parámetros congelados). Cada
tramo corre su propio backtest con sus parámetros y compara solo sus operaciones, desde el cambio de la config
(`strategy_config_changes`; sin registro, desde el primer trade del tramo) hasta el cambio siguiente.

Uso (desde python-engine/):
  venv/bin/python tools/analysis/compare_paper_vs_backtest.py --config 54 [--start 2026-10-20] [--end 2026-11-06]
                                                                   [--latest-only] [--json-out salida.json]
Código de salida: 0 = sin divergencias · 1 = hay divergencias · 2 = no se pudo comparar.
"""
import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())

import pandas as pd  # noqa: E402

from collectors.broker_resolver import interval_delta  # noqa: E402

PRICE_TOL_PCT = 0.3      # Δ de precio de entrada/salida tolerado (Paper entra al precio vivo del tick)
TIME_EXIT_TOL_MIN = 5    # salida por tiempo máximo: Paper la ejecuta en el tick siguiente (hora de proceso, por diseño)
TIME_EXITS = ('time_exit', 'time_exit_profit')
SKIP_KEYS = {'symbol', 'interval', 'start_date', 'end_date', 'walk_forward', 'monthly_breakdown', 'strategy'}


# ───────────────────────────── funciones puras (probadas en tests/Forensic/compare_tool_test.py) ─────────────────────

def as_dict(v) -> dict:
    return json.loads(v) if isinstance(v, str) else dict(v or {})


def code_version(params: dict) -> str | None:
    """md5 del código de la estrategia del snapshot: la misma huella que la columna strategy_code_md5 (MEJ-002)."""
    code = (params or {}).get('strategy_code')
    return hashlib.md5(code.encode('utf-8')).hexdigest() if isinstance(code, str) else None


def snapshot_key(params: dict) -> str:
    return hashlib.md5(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()[:10]


def naive_utc(t) -> datetime | None:
    if t is None:
        return None
    t = pd.Timestamp(t)
    return (t.tz_convert('UTC').tz_localize(None) if t.tzinfo is not None else t).to_pydatetime()


def candle(t, step: timedelta) -> datetime:
    """Vela (UTC, alineada a 00:00) que contiene t."""
    t = naive_utc(t)
    epoch = datetime(1970, 1, 1)
    return epoch + ((t - epoch) // step) * step


def snapshot_segments(trades: list[dict], change_times=(), fallback: dict | None = None) -> list[dict]:
    """Tramos consecutivos de trades con los mismos parámetros congelados, en orden de entrada. Cada tramo:
    params, key, trades, lo (inicio; None = el del rango) y hi (fin exclusivo; None = el del rango). El límite entre dos
    tramos es el cambio de la config registrado entre el último trade de uno y el primero del otro (el más reciente); sin
    registro, la entrada del primer trade del tramo nuevo. Trades sin snapshot usan `fallback` (params de la config)."""
    segs: list[dict] = []
    for t in sorted(trades, key=lambda x: naive_utc(x['entry_time'])):
        params = as_dict(t.get('config_snapshot')) if t.get('config_snapshot') else dict(fallback or {})
        key = snapshot_key(params)
        if segs and segs[-1]['key'] == key:
            segs[-1]['trades'].append(t)
        else:
            segs.append(dict(params=params, key=key, trades=[t], lo=None, hi=None))
    changes = sorted(naive_utc(c) for c in change_times if c is not None)
    for prev, seg in zip(segs, segs[1:]):
        last, first = naive_utc(prev['trades'][-1]['entry_time']), naive_utc(seg['trades'][0]['entry_time'])
        inside = [c for c in changes if last < c <= first]
        seg['lo'] = prev['hi'] = inside[-1] if inside else first
    return segs


def changed_after(segs: list[dict], change_times=()) -> datetime | None:
    """C5-06 (p104): último cambio de la config registrado DESPUÉS de la entrada de la última operación de Paper (el
    último tramo ya no es la config vigente: no hay operaciones con ella todavía). None si no cambió después."""
    if not segs:
        return None
    last = naive_utc(segs[-1]['trades'][-1]['entry_time'])
    after = sorted(naive_utc(c) for c in change_times if c is not None and naive_utc(c) > last)
    return after[-1] if after else None


def version_line(cfg: dict) -> str:
    """Qué versión tiene hoy la config (huella de los parámetros y del código), para ponerla junto a cada tramo."""
    p = as_dict(cfg.get('params'))
    code = code_version(p)
    return f"config vigente #{cfg['id']}: parámetros {snapshot_key(p)} · código {code[:8] if code else 'sin código'}"


def stale_warning(changed: datetime) -> str:
    return (f"*** AVISO: el último tramo NO es la configuración vigente: la config cambió el {changed:%Y-%m-%d %H:%M} UTC "
            f"y todavía no hay operaciones de Paper con ella. Lo comparado es la versión anterior. ***")


def backtest_payload(cfg: dict, params: dict, start: str, end: str) -> dict:
    p = {k: v for k, v in params.items() if k not in SKIP_KEYS}
    return dict(p, strategy=cfg['display_name'] or f"config #{cfg['id']}", symbol=cfg['symbol'],
                interval=str(cfg['interval']), start_date=start, end_date=end, walk_forward=False,
                monthly_breakdown=False)


def last_full_day(end: str | None, today: date) -> tuple[str, str | None]:
    """Fin del rango (inclusive): el pedido, pero nunca después de ayer (UTC); y el aviso si se recortó."""
    cap = today - timedelta(days=1)
    if end is None:
        return cap.isoformat(), None
    if date.fromisoformat(end) > cap:
        return cap.isoformat(), (f"Aviso: --end {end} incluye un día sin terminar: se compara hasta {cap.isoformat()} "
                                 f"(último día completo, con todas sus velas de 1m).")
    return end, None


def default_range(trades: list[dict], start: str | None, end: str | None, today: date) -> tuple[str, str]:
    """Desde el primer trade de Paper (o el pedido) hasta el último día completo (o el pedido, si es anterior)."""
    first = min((naive_utc(t['entry_time']) for t in trades), default=None)
    s = start or (first.date().isoformat() if first else (today - timedelta(days=30)).isoformat())
    return s, last_full_day(end, today)[0]


def pct(a, b) -> float | None:
    return None if a is None or b is None or float(b) == 0 else (float(a) - float(b)) / float(b) * 100


def match_trades(paper: list[dict], bt: list[dict], step: timedelta) -> list[dict]:
    """Empareja por (lado, vela de entrada), en orden. Cada fila: kind = igual | distinta | abierta | solo_paper |
    solo_backtest, con las diferencias."""
    def group(rows):
        g = {}
        for t in sorted(rows, key=lambda x: naive_utc(x['entry_time'])):
            g.setdefault((t['side'], candle(t['entry_time'], step)), []).append(t)
        return g
    gp, gb = group(paper), group(bt)
    out = []
    for key in sorted(set(gp) | set(gb), key=lambda k: (k[1], k[0])):
        ps, bs = gp.get(key, []), gb.get(key, [])
        for i in range(max(len(ps), len(bs))):
            p = ps[i] if i < len(ps) else None
            b = bs[i] if i < len(bs) else None
            row = dict(side=key[0], candle=key[1], paper=p, backtest=b)
            if p and b:
                is_open = p.get('status') == 'open'
                d_entry = pct(p['entry_price'], b['entry_price'])
                row.update(d_entry_pct=d_entry)
                if is_open:
                    row['kind'] = 'abierta' if b.get('exit_reason') == 'end_of_data' else 'distinta'
                    row['why'] = [] if row['kind'] == 'abierta' else [f"Paper abierta, backtest cerró por {b.get('exit_reason')}"]
                else:
                    pe, be = naive_utc(p.get('exit_time')), naive_utc(b.get('exit_time'))
                    d_exit_min = None if pe is None or be is None else (pe - be).total_seconds() / 60
                    d_exit = pct(p.get('exit_price'), b.get('exit_price'))
                    why = []
                    if p.get('exit_reason') != b.get('exit_reason'):
                        why.append(f"motivo {p.get('exit_reason')} vs {b.get('exit_reason')}")
                    tol = TIME_EXIT_TOL_MIN if b.get('exit_reason') in TIME_EXITS else 0
                    if d_exit_min is None or abs(d_exit_min) > tol:
                        why.append(f"hora de salida {'+' if (d_exit_min or 0) > 0 else ''}{d_exit_min} min"
                                   if d_exit_min is not None else 'hora de salida desconocida')
                    if d_entry is not None and abs(d_entry) > PRICE_TOL_PCT:
                        why.append(f"entrada Δ {d_entry:.3f} %")
                    if d_exit is not None and abs(d_exit) > PRICE_TOL_PCT:
                        why.append(f"salida Δ {d_exit:.3f} %")
                    row.update(d_exit_pct=d_exit, d_exit_min=d_exit_min, why=why, kind='distinta' if why else 'igual',
                               pnl_pct=(p.get('pnl_pct'), b.get('pnl_pct')))
            elif p:
                row.update(kind='solo_paper', why=['sin operación en el backtest'])
            else:
                row.update(kind='solo_backtest', why=['sin operación en Paper'])
            out.append(row)
    return out


def summarize(rows: list[dict]) -> dict:
    n = {k: sum(1 for r in rows if r['kind'] == k) for k in ('igual', 'distinta', 'abierta', 'solo_paper', 'solo_backtest')}
    closed = [r for r in rows if r['kind'] in ('igual', 'distinta') and r.get('paper') and r.get('backtest')
              and r['paper'].get('status') != 'open']
    same_reason = sum(1 for r in closed if r['paper'].get('exit_reason') == r['backtest'].get('exit_reason'))
    same_time = sum(1 for r in closed if r.get('d_exit_min') is not None and abs(r['d_exit_min']) <= (
        TIME_EXIT_TOL_MIN if r['backtest'].get('exit_reason') in TIME_EXITS else 0))
    d_entry = [abs(r['d_entry_pct']) for r in rows if r.get('d_entry_pct') is not None]
    return dict(**n, emparejadas_cerradas=len(closed), mismo_motivo=same_reason, misma_hora=same_time,
                d_entry_medio_pct=round(sum(d_entry) / len(d_entry), 4) if d_entry else None,
                divergencias=n['distinta'] + n['solo_paper'] + n['solo_backtest'])


def report(cfg: dict, start: str, end: str, rows: list[dict], s: dict, title: str = '') -> str:
    lines = [f"=== Paridad Paper vs backtest · config #{cfg['id']} {cfg['display_name']} · {cfg['symbol']} {cfg['interval']}"
             f" · {start} → {end}{' · ' + title if title else ''} ===",
             f"{'vela de entrada':<17} {'lado':<5} {'resultado':<13} {'Paper':<34} {'backtest':<34} diferencias"]
    for r in rows:
        def side(t):
            if not t:
                return '—'
            if t.get('status') == 'open':
                return f"abierta @ {float(t['entry_price']):.6g}"
            return f"{t.get('exit_reason')} {naive_utc(t.get('exit_time')):%m-%d %H:%M} {t.get('pnl_pct')}%"
        lines.append(f"{r['candle']:%Y-%m-%d %H:%M} {r['side']:<5} {r['kind']:<13} {side(r.get('paper')):<34} "
                     f"{side(r.get('backtest')):<34} {'; '.join(r.get('why') or [])}")
    lines += ['', f"Iguales {s['igual']} · distintas {s['distinta']} · solo Paper {s['solo_paper']} · solo backtest "
                  f"{s['solo_backtest']} · abiertas (end_of_data) {s['abierta']}",
              f"Cerradas emparejadas {s['emparejadas_cerradas']}: mismo motivo {s['mismo_motivo']}, misma hora de salida "
              f"{s['misma_hora']} · Δ entrada medio {s['d_entry_medio_pct']} %",
              f"DIVERGENCIAS: {s['divergencias']}"]
    return '\n'.join(lines)


# ───────────────────────────── E/S (base de datos y motor) ─────────────────────────────

async def load(config_id: int, start: str | None, end: str | None) -> tuple[dict | None, list[dict]]:
    import asyncpg
    from dotenv import load_dotenv
    load_dotenv()
    dsn = (f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:"
           f"{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")
    conn = await asyncpg.connect(dsn)
    try:
        cfg = await conn.fetchrow("SELECT id, display_name, symbol, interval, params FROM paper_strategy_configs"
                                  " WHERE id = $1", config_id)
        changes = [r['created_at'] for r in await conn.fetch(
            "SELECT created_at FROM strategy_config_changes WHERE paper_strategy_config_id = $1"
            " AND action IN ('created', 'updated')", config_id)]   # C5-06: solo lo que cambia parámetros
        q = ("SELECT id, side, entry_price, exit_price, entry_time, exit_time, exit_reason, pnl_pct, status,"
             " config_snapshot FROM paper_trades WHERE paper_strategy_config_id = $1")
        args = [config_id]
        if start:
            q += f" AND entry_time >= ${len(args) + 1}"
            args.append(datetime.fromisoformat(start))
        if end:
            q += f" AND entry_time < ${len(args) + 1}"
            args.append(datetime.fromisoformat(end) + timedelta(days=1))
        trades = [dict(r) for r in await conn.fetch(q + " ORDER BY entry_time", *args)]
    finally:
        await conn.close()
    return (dict(cfg, change_times=changes) if cfg else None), trades


def run_backtest(payload: dict) -> dict:
    import httpx
    from dotenv import load_dotenv
    load_dotenv()
    key = os.getenv('INTERNAL_API_KEY')
    if not key:
        raise SystemExit('INTERNAL_API_KEY no definida en python-engine/.env')
    url = os.getenv('ENGINE_URL', 'http://127.0.0.1:8002') + '/v1/backtest/run'
    r = httpx.post(url, headers={'X-Internal-API-Key': key}, json=payload, timeout=600)
    if r.status_code != 200:
        raise SystemExit(f'el backtest respondió {r.status_code}: {r.text[:300]}')
    return r.json()


def main(argv=None, loader=load, backtester=run_backtest, today: date | None = None) -> int:
    ap = argparse.ArgumentParser(description='Paridad Paper vs backtest de una config de Paper')
    ap.add_argument('--config', type=int, required=True, help='id de paper_strategy_configs')
    ap.add_argument('--start', help='YYYY-MM-DD (por defecto: el primer trade de Paper)')
    ap.add_argument('--end', help='YYYY-MM-DD inclusive (por defecto y como máximo: ayer UTC, el último día completo)')
    ap.add_argument('--latest-only', action='store_true',
                    help='solo el último tramo con operaciones (si la config cambió después, el reporte lo avisa)')
    ap.add_argument('--json-out')
    a = ap.parse_args(argv)

    today = today or datetime.now(timezone.utc).date()
    end, end_note = last_full_day(a.end, today)
    if end_note:
        print(end_note)
    cfg, trades = asyncio.run(loader(a.config, a.start, end))
    if not cfg:
        print(f'No existe la config de Paper #{a.config}')
        return 2
    if not trades:
        print(f'La config #{a.config} no tiene trades de Paper hasta {end} (último día completo)')
        return 2
    start, end = default_range(trades, a.start, end, today)
    step = interval_delta(str(cfg['interval']))
    segs = snapshot_segments(trades, cfg.get('change_times') or (), as_dict(cfg.get('params')))
    changed = changed_after(segs, cfg.get('change_times') or ())   # C5-06: ¿el último tramo es la config vigente?
    print(version_line(cfg))
    if changed:
        print(stale_warning(changed))
    if a.latest_only:
        segs = segs[-1:]
    if len(segs) > 1:
        print(f"La config cambió de parámetros en el rango: {len(segs)} tramos, cada uno con su backtest.")
    all_rows, out_segs = [], []
    for n, seg in enumerate(segs, 1):
        lo = seg['lo'] or datetime.fromisoformat(start)
        hi = seg['hi']
        s_start = max(datetime.fromisoformat(start), lo).date().isoformat()
        # el backtest corre hasta el fin del rango (una operación del tramo sigue con sus parámetros, como en Paper);
        # solo cuentan sus entradas dentro del tramo
        out = backtester(backtest_payload(cfg, seg['params'], s_start, end))
        bt = [t for t in (out.get('result') or {}).get('trades', [])
              if naive_utc(t['entry_time']) >= max(datetime.fromisoformat(start), lo)
              and (hi is None or naive_utc(t['entry_time']) < hi)]
        rows = match_trades(seg['trades'], bt, step)
        for r in rows:
            r['snapshot'] = seg['key']
        s = summarize(rows)
        code_md5 = code_version(seg['params'])
        # C5-06: cada tramo dice siempre qué versión compara (parámetros, código y desde cuándo)
        last_seg = n == len(segs)
        title = (f"tramo {n}/{len(segs)} · parámetros {seg['key']} · código {code_md5[:8] if code_md5 else 'sin código'}"
                 f" · desde {lo:%Y-%m-%d %H:%M}{' hasta ' + format(hi, '%Y-%m-%d %H:%M') if hi else ''}"
                 + (f" · {'NO es la vigente' if changed else 'vigente'}" if last_seg else ''))
        print(report(cfg, s_start, end, rows, s, title))
        for w in out.get('warnings') or []:
            print(w)
        all_rows += rows
        out_segs.append(dict(snapshot=seg['key'], code_md5=code_md5, start=s_start, lo=lo, hi=hi, summary=s,
                             vigente=bool(last_seg and not changed)))
    total = summarize(all_rows)
    if len(segs) > 1:
        print(f"\n=== Total de los {len(segs)} tramos: iguales {total['igual']} · distintas {total['distinta']} · solo Paper "
              f"{total['solo_paper']} · solo backtest {total['solo_backtest']} · DIVERGENCIAS: {total['divergencias']}")
    if a.json_out:
        with open(a.json_out, 'w', encoding='utf-8') as f:
            json.dump(dict(config=cfg['id'], start=start, end=end, summary=total, rows=all_rows, segments=out_segs,
                           config_params_key=snapshot_key(as_dict(cfg.get('params'))),
                           config_code_md5=code_version(as_dict(cfg.get('params'))), config_changed_after=changed),
                      f, ensure_ascii=False, default=str)
    return 1 if total['divergencias'] else 0


if __name__ == '__main__':
    sys.exit(main())
