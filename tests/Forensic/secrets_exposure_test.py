"""
R-05 y R-07 (p65): las claves del broker no salen del pedido y el motor no necesita el APP_KEY de Laravel.
- R-07: un 422 (pedido Real con un campo faltante) NO repite lo recibido: sin 'input', sin la clave ni el secreto,
  y conserva loc/msg/type para saber qué falló. Control: el 422 por defecto de FastAPI sí los devuelve.
- R-05: sin laravel_crypt.py, sin get_active_subscriptions (leía claves cifradas de la base) y sin APP_KEY en
  .env.example; ningún archivo del motor lee APP_KEY.
Sin DB ni red. Uso: cd python-engine && venv/bin/python ../tests/Forensic/secrets_exposure_test.py
"""
import importlib
import logging
import os
import re
import sys

sys.path.insert(0, os.getcwd())   # python-engine/
logging.disable(logging.CRITICAL)

import dotenv  # noqa: E402

dotenv.load_dotenv = lambda *a, **k: False
os.environ['INTERNAL_API_KEY'] = 'clave-de-prueba'

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

fails = 0


def check(name, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print(('PASS ' if ok else 'FAIL ') + name + (f'  -> {detail}' if detail != '' else ''))


KEY, SECRET = 'KEY-r07-visible', 'SECRET-r07-no-debe-salir'
H = {'X-Internal-API-Key': 'clave-de-prueba'}
# Cuenta sin 'subscriptions' (requerido): el 422 por defecto devuelve la cuenta completa en 'input'
BAD = {'accounts': [{'id': 11, 'broker': 'bybit', 'account_type': 'demo', 'api_key': KEY, 'api_secret': SECRET}]}

import main  # noqa: E402
app = importlib.reload(main).app
c = TestClient(app)
for path in ('/v1/real/tick', '/v1/real/reconcile', '/v1/real/circuit-breaker-max-loss'):
    r = c.post(path, json=BAD, headers=H)
    body = r.text
    check(f'S1 {path}: 422', r.status_code == 422, r.status_code)
    check(f'S2 {path}: la respuesta no contiene la clave ni el secreto', KEY not in body and SECRET not in body, body[:200])
    errs = (r.json() or {}).get('detail') or []
    check(f'S3 {path}: sin "input" y con loc/msg/type (sigue diciendo qué falta)',
          errs != [] and all('input' not in e and {'loc', 'msg', 'type'} <= set(e) for e in errs)
          and any('subscriptions' in [str(x) for x in e['loc']] for e in errs), errs)

# Control: el manejador por defecto de FastAPI SÍ repite el secreto (el escenario reproduce el hallazgo)
from api.v1.real_trading import router  # noqa: E402
plain = FastAPI()
plain.include_router(router, prefix='/v1')
r = TestClient(plain).post('/v1/real/tick', json=BAD)
check('S4-control: con el 422 por defecto el secreto SÍ salía', r.status_code == 422 and SECRET in r.text, r.status_code)

# Otro 422 cualquiera (no Real): mismo formato, sin input
r = c.post('/v1/real/tick', json={'accounts': 'x'}, headers=H)
check('S5 422 de tipo (accounts no es lista): sin "input"', r.status_code == 422 and '"input"' not in r.text, r.text[:160])

# ── R-05 ──
check('D1 laravel_crypt.py eliminado', not os.path.exists('trading/laravel_crypt.py'))
rt = open('trading/real_trader.py', encoding='utf-8').read()
check('D2 sin get_active_subscriptions (leía api_key/api_secret de la base)', 'def get_active_subscriptions' not in rt)
env = open('.env.example', encoding='utf-8').read()
check('D3 .env.example no pide APP_KEY', not re.search(r'^\s*APP_KEY\s*=', env, re.M))
readers = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('venv', '.venv', '__pycache__', 'node_modules')]
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            t = open(p, encoding='utf-8', errors='replace').read()
            if re.search(r"""getenv\(\s*['"]APP_KEY|environ\[\s*['"]APP_KEY|laravel_crypt|laravel_decrypt""", t):
                readers.append(p)
check('D4 ningún archivo del motor lee APP_KEY ni usa laravel_crypt', readers == [], readers)

print('RESULTADO:', 'TODO OK' if fails == 0 else f'{fails} FALLO(S)')
sys.exit(0 if fails == 0 else 1)
