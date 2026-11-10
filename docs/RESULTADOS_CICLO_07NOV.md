# Resultados del 3.er ciclo de fixes — auditoría del 07-nov-2026

> **Para el auditor.** Ciclo del 09 al 10 de noviembre de 2026 (Bogotá). Base: `TR2_Actualizacion_Auditoria_Con_Hallazgos_Originales_2026-11-07.md` y su matriz CSV. Punto de partida `main` = `1e867d5` (p32); cierre `main` = `a0fa1a3` (p46).
> Estado de cada hallazgo: `docs/CERTIFICACION_AUDITORIA.md`. Detalle técnico y decisiones: `docs/BITACORA.md`, sección «Auditoría del 07-nov». Lo que sigue: `docs/PENDIENTES_AUDITORIA.md`.

## 1. Método

Un hallazgo por parche, del más crítico al menos. Cada fix siguió los mismos pasos:
1. **Validar** el hallazgo contra el código vigente y medir su alcance en producción. El diagnóstico de solo lectura del 09-nov está en la §2.
2. **Revisar** la documentación de la función afectada y actualizarla junto con el código.
3. **Prueba forense antes/después:** la prueba se escribe primero y debe **fallar con el código anterior** y pasar con el nuevo.
4. **Mutaciones:** se introducen errores deliberados en el fix y la prueba debe detectarlos.
5. **Regresión completa** local y en el servidor.
6. **Instalador** `pNN_instalar.sh`, probado dos veces en una copia simulada del servidor, más la ruta de reversión. Verifica el `HEAD` esperado, aplica el diff con md5 de origen y final, corre la regresión (revierte si falla), reinicia solo lo que cambió, verifica el tick de Paper y los errores en `engine.log`, y hace commit y push.
7. **Integración:** lo que solo se puede probar con Laravel y la base real corrió durante la instalación, dentro de una transacción que se revierte y con `Http::fake`. Incluyó un control con el criterio anterior que reproduce el bug.

## 2. Diagnóstico en producción (solo lectura, 09-nov 14:19 UTC)

| Hallazgo | Medición | Lectura |
|---|---|---|
| N-05 | 0 trades Real cerrados sin PnL | Latente: el fix previene |
| N-01 | 0 `pending_open`; 1 cuenta (11, demo) | Latente |
| N-09 | **«VWAP Tendencia — ETHUSDT H4» = configs #68 (activa) y #62** | **Caso real** |
| N-10 | 15 configs, todos los flags booleanos | Defensa |
| N-15 | Servidor, base y motor en UTC | Defensa |
| N-12 | `INTERNAL_API_KEY` con valor en `python-engine/.env` | Defensa (falla cerrada) |
| CFG-05 | 0 trades Paper abiertos sin config | Latente |
| N-02 | 0 trades Paper abiertos | Sin efecto en curso |

## 3. Resultado por hallazgo

| ID | Prioridad (auditor → validada) | Parche · commit | Prueba (casos) | Antes del fix | Mutaciones detectadas | Integración |
|---|---|---|---|---|---|---|
| N-05 | P1 → P1 | p33 · `01fc216` | `real_close_settle_test.py` (18) | 12 fallos | 2/2 | — |
| N-01 | P1 → P1 | p34 · `9adecbb` | `real_reconcile_statuses_test.php` (12) | 8 fallos | — | `real_reconcile_selector_test.php`: 6 PASS; el selector anterior no enviaba la cuenta |
| N-02 | P1 → P1 | p35 · `1734f98` | `minute_tail_test.py` (10) | 7 fallos | 4/4 | — |
| N-07 | P2 → P2 alto | p36 · `bf4fce0` | `real_concurrency_test.py` (16, tiempos reales) | 12 fallos | 5/5 | Verifica que el motor corre en 1 proceso |
| N-06 + N-16 | P2, P2/P3 | p37 · `7abfa89` | `real_close_accounting_test.py` (13) | 11 fallos | 5/5 | Datos: `pnl_pct` neto en los trades Real #85 (−0,9956 → −1,0540) y #86 (−0,3285 → −0,4020) |
| N-09 | P2 → P2 (caso real) | p38 · `387d646` | `strategy_label_test.php` (16) | 10 fallos | — | `strategy_identity_test.php`: 7 PASS, con 2 controles que reproducen el bug |
| N-10 | P2 → defensa | p39 · `bd904e9` | `flag_normalization_test.py` (33) | 21 fallos | 3/3 | — |
| CFG-05 | P1 → P2 | p40 revertido; **p40b** · `474c162` | `backtest_delete_rules_test.php` (12) | 12 fallos | — | `backtest_delete_test.php`: 10 PASS, con 2 controles |
| N-12, N-14, N-15 | P2, P3, P3 | p41 · `b64b4ce` | `engine_hardening_test.py` (18) | 8 fallos y la prueba se corta | 4/4 | — |
| N-04 | P1 → P3 (no habilita nada en la app) | p42 · `c193ee3` | `quality_gate_test.py` (15) | 13 fallos | 4/4 | — |
| N-03 | P1 → P1 · decisión (a) | p43 · `352ca33` | `is_oos_attribution_test.py` (11) | 8 fallos y la prueba se corta | 3/3 | — |
| N-11 | P2 · decisión (a) | p44 · `c45cd42` | `collector_deletion_test.py` (14) | 6 fallos; **un corte a mitad dejó 1.200 de 1.500 velas borradas** sin registro | 4/4 | Migración `ohlcv_deletions` aplicada (12 columnas) |
| N-08 | P2 → P3 | p45 · `d22b684` | `strategy_config_types_test.php` (14) | 14 fallos | 3/3 | Ninguna estrategia guarda números como texto |
| N-13 | P2 → cerrado por análisis | — | — | — | — | El SL/TP se recalcula con el precio de ejecución: el desvío del riesgo es del tamaño del slippage |

Fuera de la auditoría, antes de empezar el ciclo: **p32** · `1e867d5` arregló un error 500 en `/trading`. Un fallo latente en la vista apareció con el primer trade Real de la cuenta 11.

## 4. Hallazgos recuperados (REAL-05, CFG-01, 02, 06–09) y CFG-03/04/05

- **REAL-05 (TP2–TP4):** fuera de alcance por decisión del dueño. Es lógica antigua; no se implementa ni se homologa.
- **CFG-01, 02, 08:** por diseño, verificados en el código. Auto-sync al volver a guardar, `config_snapshot` en trades abiertos, Real independiente de Paper.
- **CFG-06, 07, 09:** por diseño o documentados: versionado por publicación, interruptor del catálogo, propagación en el siguiente tick. Falta explicarlos en la pantalla, lo que requiere maqueta.
- **CFG-03, 04:** corregidos con `scopeRunnable` (`5017d2e`). Tienen prueba de integración (`real_config_gate_test.php`).
- **CFG-05:** pasa de parcial a corregido con p40b.

## 5. Desviaciones y cómo se resolvieron

- **p40 lo revirtió su propia prueba de integración.** La prueba buscaba la fila de auditoría `deleted` por `paper_strategy_config_id`, y la FK de producción es `ON DELETE SET NULL`. El volcado de esquema del repo está desactualizado y ni siquiera tiene esa tabla. El instalador revirtió todo, se consultó `pg_constraint` y salió **p40b**: la identidad de lo borrado queda en `new_params.deleted`.
- **p41 asumió `timestamp` para `ohlcv_data.time`.** La columna es `timestamptz`. Se corrigió en p44: `invalidate` recibe instantes UTC con zona.
- **p42 llegó como «YA APLICADO».** Se pidió el `HEAD` real (`c193ee3`, con push hecho) antes de generar p43.
- **Entorno local:** tenía FastAPI 0.162; se fijó la versión del servidor, `fastapi==0.115.0`.

## 6. Pruebas

- **Regresión:** de **43** (p32) a **56**: 45 Python + 11 PHP, todas en TODO OK en el servidor tras p46. La lista está en `docs/CERTIFICACION_AUDITORIA.md`.
- **Integración** contra la base real, en transacción revertida: `real_config_gate_test`, `real_reconcile_selector_test`, `strategy_identity_test` y `backtest_delete_test`.
- **Límite:** PASS demuestra el caso probado. No demuestra Bybit real, la base bajo carga ni Horizon/Scheduler de punta a punta.

## 7. Estado y recomendación

- **Hallazgos:** los 70 están clasificados. 50 corregidos, 15 por diseño o documentados, 2 cerrados con datos, 1 fuera de alcance y 2 en Fase 12.
- **Antes de aumentar el capital Real:**
  1. Confirmar el respaldo de la base fuera del VPS.
  2. Correr el comparador Paper ↔ backtest sobre las configs activas.
  3. Elegir las opciones de Fase 12.
