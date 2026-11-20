"""
Limpieza (p88): ningún import sin usar en el código del motor (`python-engine/`, sin venv ni __init__.py, que
re-exportan). Un import sin usar confunde al que lee («¿esto usa la base aquí?») y al auditor. Se ignoran las líneas con
`# noqa` (imports a propósito, p. ej. para que una prueba los reemplace) y los nombres que aparecen en `__all__`.
Detección por AST: un nombre importado a nivel de módulo, de clase o de función que no se vuelve a nombrar en el archivo.
Uso: cd python-engine && venv/bin/python ../tests/Forensic/unused_imports_test.py
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'python-engine'
SKIP_DIRS = {'venv', '__pycache__', '.venv', 'logs'}


def unused_imports(path: Path) -> list[str]:
    src = path.read_text(encoding='utf-8')
    tree = ast.parse(src)
    lines = src.splitlines()
    imported: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if 'noqa' in lines[node.lineno - 1] or (isinstance(node, ast.ImportFrom) and node.module == '__future__'):
                continue
            for a in node.names:
                if a.name == '*':
                    continue
                name = a.asname or a.name.split('.')[0]
                imported.setdefault(name, node.lineno)
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            base = node
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name):
                used.add(base.id)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            used.update(w for w in imported if re.search(rf'(?<![\w.]){re.escape(w)}\b', node.value)
                        and re.fullmatch(r'[\w\[\]., |]+', node.value))   # anotaciones en texto y __all__
    return [f"{path.relative_to(ROOT)}:{line} {name}" for name, line in sorted(imported.items(), key=lambda x: x[1])
            if name not in used]


files = [p for p in ROOT.rglob('*.py') if not (set(p.relative_to(ROOT).parts) & SKIP_DIRS) and p.name != '__init__.py']
bad = []
for p in sorted(files):
    bad += unused_imports(p)
print(f"{len(files)} archivos revisados")
for b in bad:
    print('FAIL import sin usar:', b)
ok = not bad
print('PASS ningún import sin usar' if ok else '')
print('\nRESULTADO:', 'TODO OK' if ok else f'{len(bad)} FALLO(S)')
sys.exit(0 if ok else 1)
