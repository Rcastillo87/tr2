# Validación del informe de mejoras — Ciclo 6 (TR2)

> Validación punto por punto del «Informe de mejoras y trabajos pendientes — Ciclo 6» (24-nov, versión auditada
> `542b6f4`). **Método (PROMPT_MAESTRO §6.0):** validar contra el código y el servidor (lectura de solo lectura);
> clasificar como **defecto** (contradice una decisión, dato equivocado o riesgo de dinero/datos → arreglo
> recomendado), **sugerencia** (cambia algo que funciona como el dueño decidió → decide el dueño) o **refutado**;
> proponer en español simple; prueba que falla con el código anterior, mutaciones y regresión completa; registrar aquí,
> en `docs/BITACORA.md` y, si hay decisión, en `docs/DECISIONES_DUENO.md`. Orden del informe (§3); resueltos aparte.
> Se mantienen D-48, D-58, D-63, D-64, D-67 y D-45/D-49 (informe §4).

## Pendientes del ciclo

| Orden | ID | Prioridad | Punto | Estado |
|---|---|---|---|---|
| 1 | C6-03 | P1 | Circuit breaker ante operaciones dudosas | Implementado en p114 (D-68) |
| 2 | C6-01 | P2 | Equidad de la cola del libro de ejecuciones | Pendiente de validar |
| 3 | C6-02 | P2 | Estado engañoso del panel de riesgo sin saldo base | Pendiente de validar |
| 4 | C6-05 | P2 | Detección de lotes comprimidos solapados (TimescaleDB) | Pendiente de validar |
| 5 | C6-07 | P2 | Comparación SL/TP fijo vs automático | Pendiente (del dueño, D-45) |
| 6 | C6-06 | P3 | Esquema PostgreSQL del repositorio tras D-66 | Pendiente de validar |
| 7 | C6-04 | P3 | Fechas reales de cada tramo de la búsqueda | Pendiente de validar |

## Validados

### C6-03 · Circuit breaker ante operaciones dudosas (P1) — **Defecto pequeño (latente)** · Implementado en p114 (D-68)
- **Código:** `CircuitBreakerMaxLossJob` elegía las cuentas con `open` / `pending_close` y
  `check_max_loss_circuit_breaker` solo revisaba `open`: una operación `pending_open` vieja u `orphaned` viva en Bybit
  quedaba fuera de la segunda red mientras no se adoptara. La protegían el SL provisional de la orden (2 %, D-13), el
  bloqueo de entradas (D-50), la conciliación adelantada cada minuto y el aviso a los 15 min. Hallazgo aparte: si Bybit
  no da el precio al abrir, la orden sale sin SL provisional.
- **Servidor (lectura 24-nov 18:38 UTC):** 16 cerradas, 2 abiertas; 0 operaciones dudosas en la historia (0 adoptadas,
  0 huérfanas, 0 cierres recuperados); 0 errores del circuit breaker y de la conciliación en `engine.log`; los 3
  `protection_failed` son del caso R-17 (19-nov). **Nunca ocurrió.**
- **Fix (D-68, «Vigilar y cerrar si es segura» 24-nov):** el job elige también las cuentas con dudosas (misma regla de
  3 min de D-50); `RealTrader._circuit_breaker_unresolved`: por cada dudosa, la posición de Bybit; si es con certeza la
  suya (`identify_unresolved_position`: lado igual, tamaño ≤ pedido, sin otra operación viva en la moneda, no huérfana
  de cierre), la misma regla que las abiertas con la entrada de Bybit y su SL (o 2 % desde la entrada si no lo tiene):
  si pasa el tope (1,2 ×), cierre reduce-only del tamaño de Bybit, historial `circuit_breaker_unresolved_close` y aviso
  `max_loss_close` («operación sin confirmar»); la conciliación anota el cierre (C5-14). Sin certeza: nunca cierra;
  aviso `unresolved_unprotected` una vez. Error de Bybit = «no sé». Corre con el turno exclusivo de la cuenta.
- **Prueba:** `circuit_breaker_unresolved_test.py` (nueva, U1–U13b); código anterior 15 FALLOS; mutaciones 11/11 (una
  duodécima, «ignora el SL de Bybit», sobrevivía porque el SL de la prueba era el 2 %: se agregó U2c); regresión 80
  Python + 35 PHP en TODO OK.

## Resueltos del ciclo (instalados y verificados)

| ID | Fix | Instalado | Verificación |
|---|---|---|---|
