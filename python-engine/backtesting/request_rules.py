"""
Validación de los parámetros de un backtest (F-03) con las reglas de request_rules.json, las mismas que usa Laravel
(App\\Services\\BacktestPayload::validate). Solo se validan los campos presentes; los ausentes toman sus defaults.
"""
import json
import math
from pathlib import Path

RULES = json.loads((Path(__file__).with_name('request_rules.json')).read_text(encoding='utf-8'))

_BOUNDS = (('gt', lambda v, x: v > x, 'mayor que'), ('ge', lambda v, x: v >= x, 'mayor o igual que'),
           ('lt', lambda v, x: v < x, 'menor que'), ('le', lambda v, x: v <= x, 'menor o igual que'))


def _fmt(x) -> str:
    return f'{x:g}' if isinstance(x, float) else str(x)


def field_error(name: str, value) -> str | None:
    r = RULES['fields'].get(name)
    if r is None:
        return None
    label = r['label']
    if r['type'] == 'enum':
        if value in r['values']:
            return None
        ok = ', '.join('ninguno' if v is None else str(v) for v in r['values'])
        return f'{label}: valor no válido ({value!r}); se admite: {ok}.'
    if value is None:
        return None if r.get('nullable') else f'{label}: es obligatorio.'
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return f'{label}: debe ser un número (recibido: {value!r}).'
    if r['type'] == 'int' and float(value) != int(value):
        return f'{label}: debe ser un número entero (recibido: {_fmt(value)}).'
    bad = [f'{word} {_fmt(r[k])}' for k, ok, word in _BOUNDS if k in r and not ok(value, r[k])]
    if bad:
        want = ' y '.join(f'{word} {_fmt(r[k])}' for k, _, word in _BOUNDS if k in r)
        return f'{label}: debe ser {want} (recibido: {_fmt(value)}).'
    return None


def errors(values: dict) -> list[str]:
    """Errores de los campos presentes en `values` (en el orden de las reglas) y de las reglas cruzadas."""
    out = [e for name in RULES['fields'] if name in values for e in [field_error(name, values[name])] if e]
    for c in RULES['cross']:
        if c['rule'] == 'le':
            a, b = values.get(c['a']), values.get(c['b'])
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a > b:
                out.append(c['message'])
        elif c['rule'] == 'requires_when' and values.get(c['field']) == c['equals']:
            need = values.get(c['needs']) or (values.get('strategy_config') or {}).get(c['needs'])
            if not (isinstance(need, list) and need):
                out.append(c['message'])
    return out
