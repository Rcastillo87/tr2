"""
Eventos de broker (bandeja de salida → avisos en la plataforma).

El motor registra aquí lo que el dueño de la cuenta debe saber (orden rechazada, cierre no confirmado,
cuenta pausada, claves API, conciliación). Laravel (`php artisan broker:events`, cada minuto) los convierte
en avisos de la campana y los marca como procesados. Una tabla, y no la respuesta HTTP del tick, para que
ningún evento se pierda si la respuesta no llega (timeout, reinicio).

emit_event nunca lanza: un fallo al registrar un aviso no puede interrumpir la gestión de una posición.
"""
import json
import logging

logger = logging.getLogger(__name__)

EVENTS = frozenset({
    'open_rejected',        # Bybit rechazó la apertura
    'open_unconfirmed',     # apertura sin confirmar -> 'orphaned'
    'close_failed',         # el cierre no se ejecutó (la posición sigue viva)
    'close_unconfirmed',    # no se pudo saber si el cierre se ejecutó
    'account_paused',       # circuit breaker pausó la cuenta
    'max_loss_close',       # cierre de emergencia por pérdida máxima
    'liquidation_risk',     # SL más allá del precio de liquidación: cerrada al abrir
    'api_auth_failed',      # Bybit rechaza las claves
    'api_auth_ok',          # Bybit vuelve a aceptarlas
    'reconcile_closed',     # cerrado en TR2 con los números de Bybit (ya no existía en Bybit)
    'reconcile_adopted',    # posición de Bybit adoptada (sin registro o huérfana)
    'reconcile_discarded',  # apertura huérfana descartada: nunca llegó a Bybit
})


async def emit_event(pool, account_id: int, event: str, trade_id: int | None = None, **data) -> bool:
    """Registra un evento para el dueño de la cuenta. Devuelve False si no se pudo (y lo deja en el log)."""
    if event not in EVENTS:
        logger.error(f"[EVENTS] evento desconocido '{event}' (cuenta {account_id}): no se registra")
        return False
    try:
        payload = json.dumps({k: v for k, v in data.items() if v is not None}, default=str, ensure_ascii=False)
        async with pool.acquire() as conn:
            # ::text::jsonb: independiente de que el pool tenga codec jsonb o no
            await conn.execute(
                "INSERT INTO broker_events (broker_account_id, trade_id, event, data) VALUES ($1, $2, $3, $4::text::jsonb)",
                int(account_id), trade_id, event, payload,
            )
        return True
    except Exception as e:  # noqa: BLE001 - un aviso nunca tumba la operación
        logger.error(f"[EVENTS] no se pudo registrar '{event}' (cuenta {account_id}, trade {trade_id}): {e}")
        return False
