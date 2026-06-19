"""
Script de investigacion: corre la matriz completa de backtests
(estrategia x simbolo x intervalo) usando el endpoint /v1/backtest/run,
y muestra una tabla resumen ordenada por retorno total.

Uso: python3 strategy_matrix.py
(ejecutar desde python-engine/, con el venv activado)
"""

import httpx
import json

BASE_URL = "http://localhost:8002/v1/backtest/run"
API_KEY  = "trading2_internal_key_2026"

SYMBOLS    = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
INTERVALS  = ["60", "120"]

# Estrategias con sus parametros base (los ya optimizados como punto de partida)
STRATEGIES = [
    {
        "name": "VWAP Tendencia",
        "params": {"sl_pct": 1.5, "tp_pct": 3.0, "be_pct": 1.8, "max_duration": 24, "regime_filter": True},
    },
    {
        "name": "VWAP Reversión",
        "params": {"sl_pct": 1.5, "tp_pct": 2.0, "tp2_pct": 3.5, "be_pct": 1.8, "max_duration": 24, "regime_filter": True},
    },
    {
        "name": "Reversión a la Media",
        "params": {"sl_pct": 1.5, "tp_pct": 3.0, "be_pct": 1.8, "max_duration": 24, "regime_filter": True},
    },
    {
        "name": "Tendencia EMA/Donchian",
        "params": {"sl_pct": 1.5, "tp_pct": 3.0, "be_pct": 1.8, "max_duration": 24, "regime_filter": True},
    },
]


def run_backtest(strategy_name: str, symbol: str, interval: str, params: dict) -> dict | None:
    payload = {
        "strategy": strategy_name,
        "symbol": symbol,
        "interval": interval,
        "walk_forward": True,
        **params,
    }

    try:
        r = httpx.post(
            BASE_URL,
            headers={"X-Internal-API-Key": API_KEY},
            json=payload,
            timeout=60,
        )
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}: {r.text[:150]}"}

        result = r.json().get("result", {})
        agg = result.get("aggregate_metrics", {})

        return {
            "trades":   agg.get("total_trades", 0),
            "win_rate": agg.get("win_rate", 0),
            "pf":       agg.get("profit_factor"),
            "sharpe":   agg.get("sharpe_ratio", 0),
            "dd":       agg.get("max_drawdown_pct", 0),
            "return":   agg.get("total_return_pct", 0),
            "passed":   result.get("passed", False),
        }
    except Exception as e:
        return {"error": str(e)}


def main():
    rows = []
    total = len(STRATEGIES) * len(SYMBOLS) * len(INTERVALS)
    count = 0

    for strat in STRATEGIES:
        for symbol in SYMBOLS:
            for interval in INTERVALS:
                count += 1
                print(f"[{count}/{total}] {strat['name']} | {symbol} | {interval}...", end=" ", flush=True)

                res = run_backtest(strat["name"], symbol, interval, strat["params"])

                if res is None or "error" in res:
                    print(f"ERROR: {res.get('error') if res else 'sin respuesta'}")
                    continue

                print(f"OK ({res['trades']} trades, {res['return']}%)")

                rows.append({
                    "strategy": strat["name"],
                    "symbol":   symbol,
                    "interval": interval,
                    **res,
                })

    # Ordenar por retorno descendente
    rows.sort(key=lambda r: r["return"], reverse=True)

    print("\n" + "=" * 110)
    print(f"{'Estrategia':<24} {'Símbolo':<10} {'Int':<5} {'Trades':<7} {'WR%':<7} {'PF':<6} {'Sharpe':<7} {'DD%':<6} {'Return%':<8} {'OK'}")
    print("=" * 110)

    for r in rows:
        pf_str = f"{r['pf']:.2f}" if r['pf'] is not None else "—"
        passed_str = "✓" if r['passed'] else ""
        print(
            f"{r['strategy']:<24} {r['symbol']:<10} {r['interval']:<5} "
            f"{r['trades']:<7} {r['win_rate']:<7} {pf_str:<6} {r['sharpe']:<7} "
            f"{r['dd']:<6} {r['return']:<8} {passed_str}"
        )

    print("=" * 110)

    # Guardar resultado completo en JSON para analisis posterior
    with open("strategy_matrix_results.json", "w") as f:
        json.dump(rows, f, indent=2)
    print("\nResultados completos guardados en strategy_matrix_results.json")


if __name__ == "__main__":
    main()
