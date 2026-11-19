"""
Motivo de salida cuando salta el stop. Una sola regla para backtest, Paper y Real (D-40, dueño 19-nov):
  · trailing_stop — el trailing ya había movido el stop;
  · break_even    — el break-even había llevado el stop al precio de entrada (o mejor) y nada lo alejó después:
                    se cierra en la entrada y lo que se pierde son solo los costos (ETH #100: −0,08 %);
  · stop_loss     — cualquier otro caso (el stop original, o uno que la protección por volatilidad alejó tras el BE).
Solo cambia el nombre del motivo: ningún precio ni resultado.
"""
STOP_LOSS, TRAILING_STOP, BREAK_EVEN = 'stop_loss', 'trailing_stop', 'break_even'


def stop_exit_reason(side: str, sl: float, entry: float, be_activated: bool, trailing_applied: bool) -> str:
    if trailing_applied:
        return TRAILING_STOP
    if be_activated and (float(sl) >= float(entry) if side == 'long' else float(sl) <= float(entry)):
        return BREAK_EVEN
    return STOP_LOSS
