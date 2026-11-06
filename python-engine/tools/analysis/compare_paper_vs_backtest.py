#!/usr/bin/env python3
"""
Paridad Paper vs backtest de una config de Paper (BP-06): mismas reglas → mismos eventos.
Corre el backtest (/v1/backtest/run) con los parámetros CONGELADOS de los trades de Paper (config_snapshot) en el mismo
rango y empareja las operaciones por (lado, vela de entrada). Compara motivo y hora EXACTA de salida (Paper y backtest
guardan la hora del evento: p19, p24), precios y PnL en % (el PnL absoluto no es comparable: Paper dimensiona con un
saldo fijo y el backtest con el acumulado). Una posición abierta en Paper frente a un end_of_data del backtest se
informa aparte (no es divergencia).

Uso (desde python-engine/):
  venv/bin/python tools/analysis/compare_paper_vs_backtest.py --config 54 [--start 2026-10-20] [--end 2026-11-06]
                                                                           [--json-out salida.json]
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


def pick_snapshot(trades: list[dict]) -> tuple[dict | None, int]:
    """Parámetros congelados del primer trade del rango y cuántos trades tienen otros (cambio de config)."""
    snaps = [as_dict(t.get('config_snapshot')) for t in trades if t.get('config_snapshot')]
    if not snaps:
        return None, 0
    k = snapshot_key(snaps[0])
    return snaps[0], sum(1 for s in snaps if snapshot_key(s) != k)


def backtest_payload(cfg: dict, params: dict, start: str, end: str) -> dict:
    p = {k: v for k, v in params.items() if k not in SKIP_KEYS}
    return dict(p, strategy=cfg['display_name'] or f"config #{cfg['id']}", symbol=cfg['symbol'],
                interval=str(cfg['interval']), start_date=start, end_date=end, walk_forward=False,
                monthly_breakdown=False)


def default_range(trades: list[dict], start: str | None, end: str | None, today: date) -> tuple[str, str]:
    first = min((naive_utc(t['entry_time']) for t in trades), default=None)
    s = start or (first.date().isoformat() if first else (today - timedelta(days=30)).isoformat())
    return s, end or today.isoformat()


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


def report(cfg: dict, start: str, end: str, rows: list[dict], s: dict, other_snapshots: int) -> str:
    lines = [f"=== Paridad Paper vs backtest · config #{cfg['id']} {cfg['display_name']} · {cfg['symbol']} {cfg['interval']}"
             f" · {start} → {end} ===",
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
    if other_snapshots:
        lines.append(f"AVISO: {other_snapshots} trade(s) del rango tienen otros parámetros congelados (la config cambió):"
                     f" acotar --start/--end a un solo snapshot para una comparación exacta.")
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
    return (dict(cfg) if cfg else None), trades


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
    ap.add_argument('--end', help='YYYY-MM-DD inclusive (por defecto: hoy UTC)')
    ap.add_argument('--json-out')
    a = ap.parse_args(argv)

    cfg, trades = asyncio.run(loader(a.config, a.start, a.end))
    if not cfg:
        print(f'No existe la config de Paper #{a.config}')
        return 2
    if not trades:
        print(f'La config #{a.config} no tiene trades de Paper en el rango')
        return 2
    params, other = pick_snapshot(trades)
    if params is None:
        params = as_dict(cfg['params'])
    start, end = default_range(trades, a.start, a.end, today or datetime.now(timezone.utc).date())
    out = backtester(backtest_payload(cfg, params, start, end))
    bt = (out.get('result') or {}).get('trades', [])
    step = interval_delta(str(cfg['interval']))
    # el backtest arranca en `start`: solo cuentan sus operaciones desde ahí (y las de Paper del mismo rango)
    lo = datetime.fromisoformat(start)
    bt = [t for t in bt if naive_utc(t['entry_time']) >= lo]
    rows = match_trades(trades, bt, step)
    s = summarize(rows)
    print(report(cfg, start, end, rows, s, other))
    for w in out.get('warnings') or []:
        print(w)
    if a.json_out:
        with open(a.json_out, 'w', encoding='utf-8') as f:
            json.dump(dict(config=cfg['id'], start=start, end=end, summary=s, rows=rows,
                           other_snapshots=other), f, ensure_ascii=False, default=str)
    return 1 if s['divergencias'] else 0


if __name__ == '__main__':
    sys.exit(main())
