"""Verificador de estilo (reglas de la skill de redaccion): muletillas, guiones largos, parrafos largos, arranques repetidos.
Uso: python lint_estilo.py archivo.md [...]   (sale con codigo 1 si hay hallazgos)"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

PROHIBIDAS = ["más allá de", "es importante destacar", "no hay que olvidar", "es crucial", "cabe resaltar", "cabe señalar", "hoy en día",
              "en la actualidad", "en el vertiginoso", "profundizar en", "abordar la problemática", "juega un rol", "juega un papel", "se erige como",
              "de vital importancia", "resulta fundamental", "en un mundo donde", "en resumen", "como se verá más adelante", "como se vio antes"]
MAX_PARRAFO = 200


def lint(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    out = []
    low = text.lower()
    for p in PROHIBIDAS:
        n = low.count(p)
        if n:
            out.append(f"muletilla «{p}» x{n}")
    n = low.count("conviene")
    if n > 2:
        out.append(f"«conviene» x{n} (maximo 2)")
    for ch, name in (("—", "guion largo"), ("–", "guion medio")):
        n = text.count(ch)
        if n:
            out.append(f"{name} x{n}")
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip() and not b.lstrip().startswith(("|", "#", "```", "- ", "1.", "2.", "3."))]
    for b in blocks:
        w = len(re.findall(r"\w+", b))
        if w > MAX_PARRAFO:
            out.append(f"parrafo de {w} palabras: «{b[:60]}…»")
    starts = Counter(re.findall(r"\w+", b)[0].lower() for b in blocks if re.findall(r"\w+", b))
    for s, n in starts.items():
        if n >= 4 and s not in ("el", "la", "los", "las", "en"):
            out.append(f"{n} parrafos abren con «{s}»")
    for m in re.finditer(r"(?<![\w`])(Para ello|Con ello|Por ello)", text):
        pass
    n = len(re.findall(r"\bPara ello\b", text))
    if n > 1:
        out.append(f"«Para ello» x{n}")
    return out


if __name__ == "__main__":
    bad = False
    for f in sys.argv[1:]:
        res = lint(Path(f))
        print(f, "OK" if not res else "")
        for r in res:
            print("  -", r)
            bad = True
    sys.exit(1 if bad else 0)
