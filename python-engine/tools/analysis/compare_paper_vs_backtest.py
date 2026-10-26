#!/usr/bin/env python3
"""
Compara trades de paper_trading (DB) contra backtest (endpoint) para una
config especifica. Alinea por entry_time redondeado a la hora (H2), muestra
divergencias en entry_price, exit_price, exit_reason y pnl.
"""
import asyncio
import asyncpg
import httpx
import os
import json
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

DB_DSN = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
API_URL = "http://localhost:8002/v1/backtest/run"
API_KEY = "trading2_internal_key_2026"

# Config a comparar (editable)
DISPLAY_NAME = sys.argv[1] if len(sys.argv) > 1 else "VWAP Tendencia — BTCUSDT H2"
START_DATE   = sys.argv[2] if len(sys.argv) > 2 else "2026-10-16"  # forward: solo post-fix
END_DATE     = sys.argv[3] if len(sys.argv) > 3 else "2026-10-15"


async def fetch_paper_trades():
    pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=3)
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, strategy, symbol, side, entry_price, sl, tp, size,
                   entry_time, exit_time, exit_price, exit_reason,
                   pnl, pnl_pct, status
            FROM paper_trades
            WHERE strategy = $1
              AND entry_time >= $2
              AND entry_time <= $3
            ORDER BY entry_time ASC
        """, DISPLAY_NAME,
             datetime.fromisoformat(START_DATE),
             datetime.fromisoformat(END_DATE + " 23:59:59"))
    await pool.close()
    return [dict(r) for r in rows]


async def fetch_config():
    pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=3)
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT strategy_class, symbol, interval, params
            FROM paper_strategy_configs
            WHERE display_name = $1
        """, DISPLAY_NAME)
    await pool.close()
    return dict(row) if row else None


def run_backtest(config):
    params = config['params']
    if isinstance(params, str):
        params = json.loads(params)

    strategy_name = config['strategy_class']
    if strategy_name == 'VwapStrategy':
        strategy = "VWAP Tendencia" if params.get('mode') == 'trend_follow' else "VWAP Reversión"
    elif strategy_name == 'MeanReversionStrategy':
        strategy = "Reversión a la Media"
    elif strategy_name == 'EmaDonchianStrategy':
        strategy = "Tendencia EMA/Donchian"
    else:
        raise ValueError(f"Clase desconocida: {strategy_name}")

    payload = {
        "strategy": strategy,
        "symbol": config['symbol'],
        "interval": config['interval'],
        "walk_forward": False,     # false → devuelve trades crudos
        "start_date": START_DATE,
        "end_date": END_DATE,
        **params
    }
    payload.setdefault('max_leverage', 1.0)

    print(f"[backtest] POST {API_URL} → {strategy} {config['symbol']} {config['interval']} "
          f"({START_DATE} → {END_DATE})")
    r = httpx.post(API_URL, headers={"X-Internal-API-Key": API_KEY},
                   json=payload, timeout=180)
    r.raise_for_status()
    return r.json().get('result', {})


def floor_to_interval(dt, interval_minutes):
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    if dt.tzinfo:
        dt = dt.replace(tzinfo=None)
    total = dt.hour * 60 + dt.minute
    floored = (total // interval_minutes) * interval_minutes
    return dt.replace(hour=floored // 60, minute=floored % 60, second=0, microsecond=0)


def main():
    paper_trades = asyncio.run(fetch_paper_trades())
    config = asyncio.run(fetch_config())

    if not config:
        print(f"❌ Config no encontrada: {DISPLAY_NAME}")
        return

    interval_minutes = int(config['interval'])

    print(f"=== {DISPLAY_NAME} ===")
    print(f"Paper trades (ventana): {len(paper_trades)}")
    print()

    bt = run_backtest(config)
    bt_trades = bt.get('trades', [])
    print(f"Backtest trades: {len(bt_trades)}")
    print()

    def key(t, field='entry_time'):
        et = t.get(field)
        return floor_to_interval(et, interval_minutes) if et else None

    paper_by_key = {}
    for t in paper_trades:
        k = key(t)
        if k:
            paper_by_key.setdefault(k, []).append(t)

    bt_by_key = {}
    for t in bt_trades:
        k = key(t)
        if k:
            bt_by_key.setdefault(k, []).append(t)

    all_keys = sorted(set(paper_by_key.keys()) | set(bt_by_key.keys()))

    matched = paper_only = bt_only = 0
    sum_d_entry = 0.0
    n_d_entry = 0
    sum_d_exit = 0.0
    n_d_exit = 0

    print(f"{'entry_time':<20} {'side':<6} {'paper_entry':<14} {'bt_entry':<14} {'Δe%':<7} "
          f"{'paper_exit':<14} {'bt_exit':<14} {'paper_rsn':<18} {'bt_rsn':<18} {'p_pnl':<9} {'b_pnl':<9}")
    print("-" * 165)

    for k in all_keys:
        p_trades = paper_by_key.get(k, [])
        b_trades = bt_by_key.get(k, [])
        n = max(len(p_trades), len(b_trades))
        for i in range(n):
            p = p_trades[i] if i < len(p_trades) else None
            b = b_trades[i] if i < len(b_trades) else None

            if p and b:
                matched += 1
                pe = float(p['entry_price'])
                be = float(b['entry_price'])
                d_pct = abs(pe - be) / be * 100 if be else 0
                sum_d_entry += d_pct
                n_d_entry += 1

                pex = p.get('exit_price')
                bex = b.get('exit_price')
                d_ex = "—"
                if pex is not None and bex is not None:
                    pex_f, bex_f = float(pex), float(bex)
                    d_ex = f"{abs(pex_f - bex_f) / bex_f * 100:.3f}"
                    sum_d_exit += float(d_ex)
                    n_d_exit += 1

                print(f"{str(k):<20} {p['side']:<6} {pe:<14.4f} {be:<14.4f} {d_pct:<7.3f} "
                      f"{str(pex or '—'):<14} {str(bex or '—'):<14} "
                      f"{str(p.get('exit_reason') or '—'):<18} {str(b.get('exit_reason') or '—'):<18} "
                      f"{str(p.get('pnl') or '—'):<9} {str(b.get('pnl') or '—'):<9}")
            elif p:
                paper_only += 1
                print(f"{str(k):<20} {p['side']:<6} PAPER-only   entry={p['entry_price']} "
                      f"exit={p.get('exit_price')} rsn={p.get('exit_reason')} pnl={p.get('pnl')}")
            else:
                bt_only += 1
                print(f"{str(k):<20} {b['side']:<6} BT-only      entry={b['entry_price']} "
                      f"exit={b.get('exit_price')} rsn={b.get('exit_reason')} pnl={b.get('pnl')}")

    paper_pnl = sum(float(t.get('pnl') or 0) for t in paper_trades if t.get('pnl') is not None)
    bt_pnl    = sum(float(t.get('pnl') or 0) for t in bt_trades)

    print()
    print(f"=== Resumen ===")
    print(f"  Matched (mismo bar):  {matched}")
    print(f"  Paper-only:           {paper_only}")
    print(f"  BT-only:              {bt_only}")
    if n_d_entry:
        print(f"  Δ entry % promedio:   {sum_d_entry / n_d_entry:.4f}%")
    if n_d_exit:
        print(f"  Δ exit  % promedio:   {sum_d_exit / n_d_exit:.4f}%")
    print()
    print(f"  Paper PnL total:      {paper_pnl:.4f}")
    print(f"  Backtest PnL total:   {bt_pnl:.4f}")
    print(f"  Diferencia PnL:       {(paper_pnl - bt_pnl):.4f}")


if __name__ == "__main__":
    main()
