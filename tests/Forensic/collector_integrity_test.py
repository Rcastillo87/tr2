"""
Prueba forense del collector (solo lectura): ¿ohlcv_data es exactamente lo que publica Bybit, sin huecos?
Usa la misma implementación que el botón "Validar contra Bybit" del Data Collector (cli/collector_validate.py):
frescura, últimas N velas cerradas vs Bybit y completitud del historial completo.

Uso (desde python-engine/): venv/bin/python ../tests/Forensic/collector_integrity_test.py [N=300] [--solo BTCUSDT,ETHUSDT]
"""
import os
import sys

sys.path.insert(0, os.getcwd())

from cli import collector_validate  # noqa: E402

if __name__ == '__main__':
    args = sys.argv[1:]
    n = next((a for a in args if a.isdigit()), '300')
    solo = args[args.index('--solo') + 1] if '--solo' in args else ''
    sys.argv = ['collector_validate', '--recent', n] + (['--solo', solo] if solo else [])
    sys.exit(collector_validate.main())
