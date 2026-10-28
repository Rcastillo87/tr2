# Migración Fase 1 — Columna broker en ohlcv_data

Fecha: 2026-10-20
Rama: feature/multibroker-data
Tag pre-migración: pre-multibroker-2026-10-20

## Cambios aplicados

### Schema
- Añadida columna `broker VARCHAR(32) NOT NULL DEFAULT 'bybit'` a `ohlcv_data`
- Clasificadas filas existentes:
  - bybit: BNBUSDT, BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, XAUUSD (⚠️ XAUUSD probablemente IG)
  - ig: EURUSD, GBPUSD

### Índices
- DROP `idx_ohlcv_symbol_interval_time` (sin broker)
- CREATE `idx_ohlcv_broker_symbol_interval_time` UNIQUE (broker, symbol, interval, time DESC)
- MANTENER `ohlcv_data_time_idx` (time DESC)

## Verificaciones
- Filas antes: 2,307,017
- Filas después: 2,307,017 ✅
- TimescaleDB 2.27.2 (ALTER en hypertable sin chunk-by-chunk)

## Rollback disponible
/tmp/fase1_rollback.sql — recrea el estado previo. NO probado post-migración.

## Siguiente
- Fase 2: adaptar lectores Python a aceptar `broker` opcional
- Fase 3: importador Binance Vision
- Fase 4: importar 10 monedas × 6 timeframes
