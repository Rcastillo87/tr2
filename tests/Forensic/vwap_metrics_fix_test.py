"""
D-43 (p82): corrección de los números guardados de VWAP Tendencia (`ops/datafix/2026_11_19_d43_vwap_metrics.py`).
A. Las columnas de cada config salen con la MISMA cuenta que Laravel: se compara contra el PHP real
   (`StrategyConfigSync::metricAttributes` + `tradesPerMonth`, `RatingHelper::calculate`).
B. La fila consolidada es la de `BacktestingController::run`; la verificación de reproducción y las métricas
   corregidas (las anteriores quedan en r21_previous).
C. Con PostgreSQL (DB_* en el entorno; si no, SKIP): sin --apply no cambia nada; un backtest que no se reproduce →
   código 1 y nada aplicado; --apply corrige backtests (métricas y código) y configs (métricas y estrellas) sin tocar
   params, estado ni el historial de parámetros; segunda corrida «YA APLICADO»; estrategia sin p80 → código 2.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/vwap_metrics_fix_test.py
"""
import asyncio
import importlib.util
import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, os.getcwd())   # python-engine/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # tests/Forensic/ (C5-04: barrera de base)
from test_db import require_test_db, test_dsn  # noqa: E402
ROOT = Path(__file__).resolve().parents[2]
fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


path = ROOT / 'ops' / 'datafix' / '2026_11_19_d43_vwap_metrics.py'
if not path.exists():
    check('existe ops/datafix/2026_11_19_d43_vwap_metrics.py', False, 'no (antes de p82)')
    print('\nRESULTADO: 1 FALLO(S)')
    sys.exit(1)
spec = importlib.util.spec_from_file_location('d43', path)
fx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fx)

# ── A. Mismas cuentas que Laravel (PHP real) ──
CASES = [
    # (metrics, run_params, months, symbol, n_symbols)
    (dict(total_trades=91, win_rate=37.36, sharpe_ratio=0.68, profit_factor=1.22, avg_monthly_pnl=0.54, consist_pct=47.8,
          total_return_pct=12.32, trades_by_symbol={'DOGEUSDT': 91}, closed_at_end=0),
     dict(start_date='2024-12-01', end_date='2026-10-31'), 23, 'DOGEUSDT', 1),
    (dict(total_trades=154, win_rate=45.45, sharpe_ratio=2.34, profit_factor=1.78, avg_monthly_pnl=2.4735913043478264,
          consist_pct=82.6, total_return_pct=56.89),   # guardado viejo: sin trades_by_symbol
     dict(start_date='2024-12-01', end_date='2026-10-31'), 23, 'DOGEUSDT', 1),
    (dict(total_trades=145, win_rate=66.0, sharpe_ratio=4.2, profit_factor=999.99, avg_monthly_pnl=21.0, consist_pct=100,
          total_return_pct=123456.0, trades_by_symbol={'SOLUSDT': 48, 'ETHUSDT': 96}, closed_at_end=1),
     dict(start_date='2024-10-01', end_date='2026-09-30'), 24, 'ETHUSDT', 2),
    (dict(total_trades=10, win_rate=None, sharpe_ratio='1.5', profit_factor=0, avg_monthly_pnl=-0.67, consist_pct=41.7),
     dict(), 0, 'BTCUSDT', 2),   # sin periodo ni conteo por moneda: trades/mes null
    (dict(total_trades=40, win_rate=50.0, sharpe_ratio=1.18, profit_factor=1.8, avg_monthly_pnl=0.62, consist_pct=52.2,
          total_return_pct=14.2, closed_at_end=1), dict(start_date='2026-10-20', end_date='2026-10-25'), 1, 'BTCUSDT', 1),
]
php = r'''
require 'app/Helpers/RatingHelper.php';
require 'app/Services/StrategyConfigSync.php';
$cases = json_decode(stream_get_contents(STDIN), true);
$S = \App\Services\StrategyConfigSync::class;
$o = (new ReflectionClass($S))->newInstanceWithoutConstructor();
$m = new ReflectionMethod($S, 'metricAttributes'); $m->setAccessible(true);
$out = [];
foreach ($cases as [$metrics, $rp, $months, $sym, $n]) {
    $a = $m->invoke($o, $metrics, $rp, $months);
    $a['avg_monthly_trades'] = $S::tradesPerMonth($metrics, $rp, $months, $sym, $n);
    $out[] = $a;
}
echo json_encode(['cols' => $out]);
'''
try:
    res = subprocess.run(['php', '-r', php], input=json.dumps(CASES), capture_output=True, text=True, cwd=ROOT, timeout=60)
    ref = json.loads(res.stdout)
except Exception as e:   # noqa: BLE001
    ref = None
    check('PHP de referencia corre', False, f"{e} {getattr(res, 'stderr', '')[:300] if 'res' in dir() else ''}")
if ref:
    for i, (case, want) in enumerate(zip(CASES, ref['cols'])):
        got = fx.config_columns(*case)
        # D-70 (25-nov): las estrellas cambiaron de fórmula; la datafix D-43 (ya aplicada en p82) usó la anterior y
        # StrategyConfigSync las recalcula con la nueva al guardar. Se comparan las demás columnas.
        bad = {k: (got[k], want.get(k)) for k in fx.CONFIG_COLS if k != 'star_rating'
               and ((got[k] is None) != (want.get(k) is None) or (got[k] is not None and abs(float(got[k]) - float(want[k])) > 1e-9))}
        check(f'A{i + 1}: columnas de la config = StrategyConfigSync (PHP)', not bad, bad)
    print('NOTA A6: las estrellas de la datafix D-43 (fórmula anterior) ya no se comparan: D-70 cambió la fórmula')
check('A7: no se tocan params ni estado (solo columnas de métricas)',
      set(fx.CONFIG_COLS).isdisjoint({'params', 'active', 'display_name', 'interval', 'backtest_id'}))

# ── B. Consolidado, reproducción y métricas corregidas ──
per = [dict(symbol='SOLUSDT', closed_at_end=1, metrics=dict(total_trades=10, winning_trades=6, gross_profit=300.0, gross_loss=100.0,
                                                             sharpe_ratio=1.5, max_drawdown_pct=4.0, max_drawdown_floating_pct=6.0),
            monthly=[dict(month='2026-01', total_pnl_pct=2.0), dict(month='2026-02', total_pnl_pct=-1.0)]),
       dict(symbol='ETHUSDT', closed_at_end=0, metrics=dict(total_trades=5, winning_trades=1, gross_profit=50.0, gross_loss=150.0,
                                                             sharpe_ratio=0.5, max_drawdown_pct=7.5, max_drawdown_floating_pct=None),
            monthly=[dict(month='2026-01', total_pnl_pct=-0.5), dict(month='2026-02', total_pnl_pct=0.25)])]
c = fx.consolidate(per)
check('B1: consolidado como BacktestingController (WR global, PF global, Sharpe promedio, retorno = suma de meses)',
      (c['total_trades'], c['win_rate'], c['profit_factor'], c['sharpe_ratio'], c['total_return_pct'], c['avg_monthly_pnl'],
       c['consist_pct']) == (15, 46.67, 1.4, 1.0, 0.75, 0.38, 50.0), c)
check('B2: drawdown = el peor de las monedas (el flotante ignora la que no lo informa); trades por moneda sin el cierre forzado',
      c['max_drawdown_pct'] == 7.5 and c['max_drawdown_floating_pct'] == 6.0
      and c['trades_by_symbol'] == {'SOLUSDT': 9, 'ETHUSDT': 5} and c['closed_at_end'] == 1, c)
c0 = fx.consolidate([dict(symbol='X', metrics=dict(total_trades=0), monthly=[])])
check('B3: sin operaciones: ceros, sin dividir por cero', (c0['win_rate'], c0['profit_factor'], c0['consist_pct']) == (0, 0, 0), c0)
saved = dict(total_trades=154, win_rate=45.45, avg_monthly_pnl=2.4735913043478264, sharpe_ratio=2.34, extra='x')
check('B4: lo guardado sin redondear (2,4736) se reproduce con 2,47', fx.mismatches(saved, dict(total_trades=154, win_rate=45.45,
      avg_monthly_pnl=2.47, sharpe_ratio=2.34)) == [])
check('B5: un trade de diferencia no se reproduce', fx.mismatches(saved, dict(total_trades=153, win_rate=45.45, avg_monthly_pnl=2.47,
      sharpe_ratio=2.34)) == ['total_trades 154 vs 153'])
check('B6: una clave que falta en la repetición no se reproduce', fx.mismatches(saved, dict(total_trades=154)) != [])
new = dict(c)
cm = fx.corrected_metrics(saved, new, '2026-11-19')
check('B7: métricas corregidas con las anteriores en r21_previous y las claves ajenas intactas',
      cm['total_trades'] == 15 and cm['r21_previous'] == dict(total_trades=154, win_rate=45.45, avg_monthly_pnl=2.4735913043478264,
                                                              sharpe_ratio=2.34)
      and cm['extra'] == 'x' and 'p82' in cm['r21_corrected'] and saved['total_trades'] == 154, cm)

# ── C. De punta a punta con PostgreSQL ──
if not require_test_db('C'):   # C5-04: nunca la base de producción
    pass
else:
    import asyncpg
    import numpy as np
    from datetime import datetime, timedelta, timezone
    DB_DSN = test_dsn()
    spec2 = importlib.util.spec_from_file_location('r21', ROOT / 'ops' / 'datafix' / '2026_11_19_r21_vwap_std.py')
    r21 = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(r21)
    OLD = (ROOT / 'tests' / 'Forensic' / 'fixtures' / 'vwap_tendencia_19nov.py').read_text(encoding='utf-8')
    NEW = r21.patch_code(OLD)
    SYM = 'D43USDT'

    async def seed(strategy_code, tamper=False):
        c = await asyncpg.connect(DB_DSN)
        try:
            await c.execute(f"""DELETE FROM strategy_config_changes WHERE symbol = '{SYM}';
                DELETE FROM paper_strategy_configs WHERE symbol = '{SYM}'; DELETE FROM backtests WHERE strategy_id = 7043;
                DELETE FROM strategies WHERE id = 7043""")
            if not await c.fetchval("SELECT count(*) FROM ohlcv_data WHERE symbol = $1", SYM):
                rng = np.random.default_rng(11)
                t0 = datetime(2026, 8, 1, tzinfo=timezone.utc); n = 60 * 24 * 92
                r = rng.normal(0, 0.0009, n) + 0.00003 * np.sin(np.arange(n) / 4000)
                close = 100 * np.exp(np.cumsum(r)); op = np.r_[100, close[:-1]]
                hi = np.maximum(op, close) * (1 + np.abs(rng.normal(0, 3e-4, n)))
                lo = np.minimum(op, close) * (1 - np.abs(rng.normal(0, 3e-4, n)))
                vol = rng.uniform(10, 100, n)
                ts = [t0 + timedelta(minutes=i) for i in range(n)]
                rows = [('bybit', SYM, '1', ts[i], float(op[i]), float(hi[i]), float(lo[i]), float(close[i]), float(vol[i]))
                        for i in range(n)]
                rows += [('bybit', SYM, '60', ts[k], float(op[k]), float(hi[k:k + 60].max()), float(lo[k:k + 60].min()),
                          float(close[k + 59]), float(vol[k:k + 60].sum())) for k in range(0, n, 60)]
                await c.copy_records_to_table('ohlcv_data', records=rows, columns=['broker', 'symbol', 'interval', 'time',
                                                                                    'open', 'high', 'low', 'close', 'volume'])
            await c.execute("INSERT INTO strategies (id, name, code, active, config, created_at, updated_at) "
                            "VALUES (7043, 'VWAP Tendencia', $1, true, '{}', now(), now())", strategy_code)
            pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=2)
            for bid, months, end in ((70431, 2, '2026-10-31'), (70432, 1, '2026-10-15')):
                cp = dict(strategy='VWAP Tendencia', strategy_code=OLD, strategy_config={'vwap_std_filter': 1.0}, symbol=SYM,
                          interval='60', start_date='2026-09-01', end_date=end, sl_pct=1.0, tp_pct=2.0, be_pct=1.0,
                          walk_forward=True, monthly_breakdown=True)
                runs = await fx.rerun(pool, cp, [SYM], {'old': OLD})
                m = fx.consolidate(runs['old'])
                saved = {k: m[k] for k in ('total_trades', 'win_rate', 'sharpe_ratio', 'profit_factor', 'avg_monthly_pnl',
                                           'consist_pct', 'total_return_pct')}
                if tamper and bid == 70432:
                    saved['total_trades'] += 1
                await c.execute("""INSERT INTO backtests (id, strategy_id, symbols, interval, months, config_params,
                    strategy_snapshot, metrics, approved, created_at, updated_at) VALUES ($1, 7043, $2, '60', $3, $4, $5, $6,
                    false, now(), now())""", bid, json.dumps([SYM]), months, json.dumps(cp),
                                json.dumps({'code': OLD, 'config': {}}), json.dumps(saved))
            await pool.close()
            P = json.dumps(dict(strategy_code=NEW, sl_pct=1.0))
            await c.execute(f"""INSERT INTO paper_strategy_configs (id, display_name, strategy_class, symbol, interval, params,
                active, backtest_id, star_rating, total_return_pct) VALUES
                (90431, 'VWAP Tendencia — {SYM} H1', 'DynamicStrategy', '{SYM}', '60', $1::jsonb, true, 70431, 3.4, 50.0),
                (90432, 'VWAP Tendencia — {SYM} H1 b', 'DynamicStrategy', '{SYM}', '60', $1::jsonb, false, 70432, 3.0, 40.0)""", P)
        finally:
            await c.close()

    async def state():
        c = await asyncpg.connect(DB_DSN)
        try:
            b = {r['id']: (json.loads(r['m']), json.loads(r['cp'])['strategy_code'], json.loads(r['s'])['code'])
                 for r in await c.fetch("SELECT id, metrics::text m, config_params::text cp, strategy_snapshot::text s "
                                        "FROM backtests WHERE strategy_id = 7043")}
            cf = {r['id']: dict(r) for r in await c.fetch(f"""SELECT id, active, params::text AS params, star_rating,
                total_return_pct, avg_win_rate, avg_monthly_trades FROM paper_strategy_configs WHERE symbol = '{SYM}'""")}
            hist = await c.fetchval(f"SELECT count(*) FROM strategy_config_changes WHERE symbol = '{SYM}'")
            return b, cf, hist
        finally:
            await c.close()

    def run(args):
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                code = asyncio.run(fx.main(args))
        except Exception as e:   # noqa: BLE001
            code = f'excepción {type(e).__name__}: {e}'
        return code, buf.getvalue()

    # sólo nuestra estrategia de prueba: el script busca por nombre; se aparta cualquier otra «VWAP Tendencia» local
    async def hide_others(on):
        c = await asyncpg.connect(DB_DSN)
        try:
            await c.execute("UPDATE strategies SET name = name || ' (oculta)' WHERE name = 'VWAP Tendencia' AND id <> 7043"
                            if on else "UPDATE strategies SET name = 'VWAP Tendencia' WHERE name = 'VWAP Tendencia (oculta)'")
        finally:
            await c.close()

    asyncio.run(hide_others(True))
    try:
        asyncio.run(seed(NEW, tamper=True))
        before = asyncio.run(state())
        code, out = run([])
        check('C1: un backtest que no se reproduce con el código viejo → código 1', code == 1 and 'NO se reproduce' in out, (code, out[-300:]))
        code, out = run(['--apply'])
        check('C2: … y con --apply no se aplica NADA (ni el que sí se reproduce)', code == 1 and asyncio.run(state()) == before,
              (code, out[-200:]))
        asyncio.run(seed(NEW))
        before = asyncio.run(state())
        code, out = run([])
        check('C3: sin --apply: muestra el plan y no cambia nada', code == 0 and 'solo lectura' in out
              and asyncio.run(state()) == before, (code, out[-300:]))
        bk = '/tmp/vwap_metrics_fix_backup.json'
        code, out = run(['--apply', '--backup', bk])
        b, cf, hist = asyncio.run(state())
        m1 = b[70431][0]
        check('C4: aplicado: código 0', code == 0 and 'APLICADO' in out, (code, out[-400:]))
        check('C5: el backtest guarda el código corregido (config_params y strategy_snapshot)',
              all(r21.is_patched(x[1]) and r21.is_patched(x[2]) for x in b.values()), [x[1][-60:] for x in b.values()])
        check('C6: métricas corregidas, con las anteriores en r21_previous',
              m1['r21_previous']['total_trades'] == before[0][70431][0]['total_trades']
              and m1['total_trades'] != before[0][70431][0]['total_trades'] and 'trades_by_symbol' in m1, m1)
        want = fx.config_columns(m1, dict(start_date='2026-09-01', end_date='2026-10-31'), 2, SYM, 1)
        got = cf[90431]
        check('C7: la config toma las estrellas, retorno y trades/mes del backtest corregido',
              float(got['star_rating']) == want['star_rating'] and abs(float(got['total_return_pct']) - want['total_return_pct']) < 1e-4
              and abs(float(got['avg_monthly_trades']) - want['avg_monthly_trades']) < 0.006, (dict(got), want))
        check('C8: params y estado (activa/apagada) de las configs sin cambio; sin filas en el historial de parámetros',
              all(cf[i]['params'] == before[1][i]['params'] and cf[i]['active'] == before[1][i]['active'] for i in cf) and hist == 0,
              hist)
        bj = json.load(open(bk))
        check('C9: respaldo con los valores anteriores de backtests y configs',
              {x['id'] for x in bj['backtests']} == {70431, 70432} and {x['id'] for x in bj['configs']} == {90431, 90432}
              and next(x for x in bj['configs'] if x['id'] == 90431)['star_rating'] == 3.4, bj['configs'])
        after = asyncio.run(state())
        code, out = run(['--apply'])
        check('C10: segunda corrida: YA APLICADO, sin cambios', code == 0 and 'YA APLICADO' in out and asyncio.run(state()) == after,
              (code, out[-200:]))
        asyncio.run(seed(OLD))
        code, out = run(['--apply'])
        check('C11: estrategia sin el código de p80 → código 2, sin tocar nada', code == 2, (code, out[-200:]))
    finally:
        async def clean():
            c = await asyncpg.connect(DB_DSN)
            try:
                await c.execute(f"""DELETE FROM paper_strategy_configs WHERE symbol = '{SYM}'; DELETE FROM backtests
                    WHERE strategy_id = 7043; DELETE FROM strategies WHERE id = 7043; DELETE FROM ohlcv_data WHERE symbol = '{SYM}'""")
            finally:
                await c.close()
        asyncio.run(clean())
        asyncio.run(hide_others(False))

print('\nRESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(0 if fails == 0 else 1)
