"""Limpieza mecanica de estilo (sin guiones largos/medios como separador): coma, dos puntos o 'a' en rangos."""
import re


def limpiar(md: str) -> str:
    out = []
    for line in md.split("\n"):
        if line.startswith("```"):
            out.append(line)
            continue
        head = line.lstrip().startswith("#")
        line = re.sub(r"(\d)\s*[–—]\s*(\d)", r"\1 a \2", line)           # rangos numericos: 2–6 -> 2 a 6
        line = re.sub(r"(\d)\s*[–—]\s*(?=[A-Za-z])", r"\1 a ", line)
        line = re.sub(r"\s[—–]\s", ": " if head else ", ", line)
        line = line.replace("—", ", ").replace("–", "-")
        out.append(line)
    return "\n".join(out)
