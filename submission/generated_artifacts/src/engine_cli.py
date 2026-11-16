"""Lanzador del motor LOG-8092 para experimentos OFFLINE (solo vive en solucion/).

Equivale a ``run.py`` pero acepta cualquier carpeta de datos y cualquier archivo de
estrategia. No modifica el motor: solo lo importa desde ``<repo>/engine``.

Uso:  python engine_cli.py --data DIR --strategy FILE --output FILE.json
"""

from __future__ import annotations

from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "engine"))

from log8092_engine.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main([
        "--interfaces", str(REPO / "interfaces.py"),
        *sys.argv[1:],
    ]))
