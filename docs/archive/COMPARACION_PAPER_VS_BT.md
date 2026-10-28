# Comparación paper vs backtest — VWAP Tendencia BTCUSDT H2

## Estado 2026-10-16
- Config hash: 362359b091be1a0ae37626a453fd061d
- Config: sin trailing, solo TP1, max_leverage=1.0

## Motores alineados (4 fixes)
- Fix 1 (334603c): sizing con tope nocional
- Fix 2 (334603c): Sharpe sobre retornos diarios
- Fix 3 (9431f5c): solo TP1 (no multi-TP lookahead)
- Fix 4 (pendiente commit): minute_bars siempre que interval >= H1
- Fix 4b (pendiente commit): use_minute_exit sin exigir trailing

## Paper histórico (pre-fix) — NO comparable
- 46 trades, 2026-07-09 → 2026-10-15
- Config: tenía trailing (params exactos desconocidos)
- PnL: +6.26
- Comparación inválida: config distinta a la actual

## Paper forward (post-fix) — el que cuenta
- Desde 2026-10-16
- Comparar cada 7 días:
  python compare_paper_vs_backtest.py "VWAP Tendencia — BTCUSDT H2"

## Criterio de alineación
- Δ entry < 0.3%
- exit_reason coincide > 80%
- Δ PnL < 10%
