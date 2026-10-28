# Roadmap: Mejoras de rendimiento del backtesting

## Estado actual
- 3 monedas: ~25 segundos
- 5 monedas: ~45 segundos
- 10 monedas: ~90 segundos

## Cuello de botella
- Procesamiento secuencial (foreach en controlador + workers=1 en Python)
- 5 ventanas de Walk-Forward (multiplica el trabajo × 5)
- Motor con loop por vela (lento en Python puro)

## Mejoras pendientes (en orden de impacto)
- [ ] Opción 1: n_windows 5→3 (~30s de trabajo, -40% tiempo)
- [ ] Opción 2: Http::pool en Laravel (~30 min, -60% si hay cores)
- [ ] Opción 3: uvicorn workers=4 (~15 min, -70% si hay cores)
- [ ] Opción 4: Vectorizar engine.py con pandas (2-4h, -95% tiempo)
- [ ] Opción 5: Cola asíncrona (4-6h, no reduce tiempo pero permite batch)

## Implementado
(ninguno todavía)
