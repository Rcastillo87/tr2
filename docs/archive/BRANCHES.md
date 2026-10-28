# Estructura de ramas

| Rama | Proposito | Estado |
|------|-----------|--------|
| main | Version estable actual | OK |
| feature/multibroker-data | Trabajo multi-broker | = main |
| new_debuging | Fixes backtest pre-multibroker | Preservada |
| legacy/pre-multibroker | Snapshot inmutable | Preservada |

## Tags
- pre-multibroker-2026-10-20 -> 062e545
- v2.1-multibroker-2026-10-21 -> f5d2af9

## Como volver al estado viejo
```
git show legacy/pre-multibroker:archivo.py
```

## Como volver a main
```
git checkout main
```
