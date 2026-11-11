# Pendientes — TR2

> Estado al **2026-11-11 (Bogotá)**, `main` = `de37022` (p56). RQ-01 cerrado (ver §0).
> Estado anterior: 2026-11-10, `main` = `d22b684` (p45). **Las tres rondas de auditoría externa están resueltas en
> código** (54 hallazgos originales + N-01 a N-16): estado de cada uno en `docs/CERTIFICACION_AUDITORIA.md`, detalle en
> `docs/BITACORA.md`. Esta lista reemplaza la del 05-nov (fixes 1 a 11, todos instalados).
> **Empezar aquí la próxima sesión.** Al cerrar un punto: tacharlo aquí y en «Próxima sesión» de la bitácora.

## 0. RQ-01 — gestión de configuraciones Paper, búsqueda y diagnóstico: CERRADO (p48–p56)

| Parte | Parche · commit | Resultado |
|---|---|---|
| RQ-01.5 motor + RQ-01.6 | p48 · `06f1212` | El motor registra cada decisión de Paper y el filtro que anuló la señal; límites por cuenta verificados |
| RQ-01.1 Trades/mes | p49 · `10f4f61` | Por moneda, sin cierre forzado, sobre el rango real; 15/15 configs |
| RQ-01.3 Origen | p50 · `5ca81c7` | Manual / búsqueda con su foto; 27 de 28 recuperados |
| RQ-01.2 Crear en historial | p51 · `5c5ab53` | Disponible si se borra su backtest; sin duplicados; creaciones colgadas se liberan |
| Pantallas | p52 · `0e85584` | Trades/mes, Paper y enlace en Estrategias; insignias en la búsqueda |
| Historial único | p53 `8f5b7b8` → p55 `4b55d2d` → p56 `de37022` | Historial y Guardados en UNA vista (todas o una estrategia), tarjeta compacta, filtros Estrategia/Paper/Origen/Moneda (lista)/Orden global; botón «Historial de backtests» en Estrategias. Fix: retorno mensual 0,71 % se veía 71 % |
| RQ-01.5 pantalla | p54 · `feea8c0` | Sección «Diagnóstico» en Paper Trading |

Regresión al cierre: 47 Python + 17 PHP. Pendiente propio de RQ-01: ninguno. Observación abierta: la config #65 NEAR evalúa con régimen NO_OPERAR porque tiene el filtro de régimen apagado (confirmar si es intencional).

## Cómo se trabaja (acordado con el dueño)

Un fix a la vez, del más crítico al menos: validar el hallazgo contra el código → revisar la documentación de esa
función → cambio → prueba forense antes/después + mutaciones + regresión completa → instalador `pNN_instalar.sh`
(sin subir archivos: el dueño copia el contenido y lo pega en la SSH) → commit y push → bitácora.

## 1. Antes de aumentar el capital Real (recomendación del auditor)

1. **Respaldo de la base fuera del VPS:** confirmar que existe y que se puede restaurar. Si no existe, es lo primero.
2. **Paridad Paper ↔ backtest con datos reales:** correr `tools/analysis/compare_paper_vs_backtest.py --config <id>`
   sobre las configs Paper activas y registrar el resultado (código de salida 0 = paridad).
3. **Fase 12:** elegir opciones en `docs/FASE12_ESTADISTICA.md` (holdout, cartera, drawdown flotante, costos en el
   tamaño). N-03 ya quitó la contaminación por trades que cruzan el corte.

## 2. Infraestructura y mantenimiento

- `trading2-horizon` como `tr2` en vez de root (revisar antes qué necesita root).
- Revisión automática de lotes solapados de TimescaleDB dos veces al día, tras `policy_compression`.
- **Esquema del repo desactualizado:** `database/schema/pgsql-schema.sql` no tiene `strategy_config_changes`,
  `paper_trades.paper_strategy_config_id` ni las tablas de las migraciones SQL recientes. Para FK, CHECK y columnas,
  consultar la base (`pg_constraint`, `information_schema`), no el volcado. Regenerarlo requiere un comando en el
  servidor y un commit.
- Aviso de vencimiento de la clave API de la cuenta 11 (vence ~85 días desde el 03-nov).
- `fastapi==0.115.0` es la versión del servidor: el entorno local de pruebas debe usar la misma.

## 3. Decisiones o pantallas pendientes del dueño (requieren maqueta)

- Mostrar en los resultados de la búsqueda los trades que cruzan el corte (`cross`, N-03).
- Explicar en la UI la separación estrategia maestra / config Paper / suscripción Real (CFG-06, CFG-07) y que los
  cambios se aplican en el siguiente tick (CFG-09).
- Borrar una **estrategia** borra sus backtests en cascada (FK `ON DELETE CASCADE`) sin pasar por las reglas de CFG-05;
  sus configs y trades sobreviven. ¿Bloquearlo también?
- Funding en pantalla (diseño listo, pospuesto). Etiqueta «código desactualizado» en Paper.
- Mejora de la pantalla del collector (estado de la auditoría histórica).

## 4. Limpieza

- Residuos TP2–TP4 (REAL-05, legado; no tocar TP1 ni SL).
- `docs/01_GENERAL.md`, `02_TECHNICAL.md`, `03_AI_CONTEXT.md` son de julio: las secciones afectadas están marcadas
  `[V7.x]` y lo obsoleto como histórico; falta reescribirlos.
- Slippage de altcoins en demo (`real_demo_roundtrip.py` con SOL, SUI, LINK).
