"""Arma submission/ (raiz del repo) con la estructura EXACTA de PRUEBA_TECNICA.md. No hace push.

 submission/candidate_strategy.py   copia exacta del archivo raiz
 submission/generated_artifacts/    copia CURADA de solucion/ (sin cachés, datasets, scratch ni bibliografia)
 submission/ai_conversations/       solo .gitkeep (se vuelca el lunes)
 submission/STRATEGY.md             desde solucion/STRATEGY_final.md
 submission/submission_manifest.json  validado contra submission_manifest.schema.json
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOL = REPO / "solucion"
SUB = REPO / "submission"
GA = SUB / "generated_artifacts"

INCLUDE_DIRS = {
    "notebooks": ("*.ipynb",),
    "src": ("*.py", "*.sh", "*.ps1"),
}
INCLUDE_FILES = ["VERIFICACION_CIFRAS.md"]   # prompts e informes internos de IA NO se publican; resultados y figuras viven en solucion/outputs/
MAX_MB = 2.5          # ningun archivo de artefactos por encima de esto (datasets/caches fuera)


def build() -> dict:
    import time
    if SUB.exists():
        for child in SUB.iterdir():
            if child.name == "ai_conversations":
                continue   # las conversaciones exportadas se conservan entre reconstrucciones
            for _ in range(8):     # OneDrive puede bloquear carpetas un instante
                try:
                    shutil.rmtree(child) if child.is_dir() else child.unlink()
                    break
                except OSError:
                    time.sleep(2)
            else:
                shutil.rmtree(child, ignore_errors=True)
    GA.mkdir(parents=True, exist_ok=True)
    (SUB / "ai_conversations").mkdir(exist_ok=True)
    if not any(f for f in (SUB / "ai_conversations").iterdir() if f.name != ".gitkeep"):
        (SUB / "ai_conversations" / ".gitkeep").write_text("", encoding="utf-8")
    shutil.copy2(REPO / "candidate_strategy.py", SUB / "candidate_strategy.py")
    copied = []

    def cp(src: Path, rel: str):
        if src.stat().st_size > MAX_MB * 1048576:
            return
        dst = GA / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(f"generated_artifacts/{rel}")

    for d, pats in INCLUDE_DIRS.items():
        for pat in pats:
            for f in sorted((SOL / d).glob(pat)):
                if f.is_file() and "__pycache__" not in f.parts:
                    cp(f, f"{d}/{f.name}")
    for name in INCLUDE_FILES:
        if (SOL / name).exists():
            cp(SOL / name, name)
    for name in ("presentacion.html", "build_presentacion.py", "plantilla.html"):
        cp(SOL / "presentacion" / name, f"presentacion/{name}")
    # pruebas unitarias propias
    cp(REPO / "tests" / "test_policy_unit.py", "tests/test_policy_unit.py")
    # README corto de la carpeta
    readme = GA / "LEEME.md"
    readme.write_text(
        "# generated_artifacts/\n"
        "\n"
        "Código y cuadernos del trabajo offline: `src/` (política parametrizable, generador de escenarios, harness, optimizadores, robustez, validación y constructores de documentos), `notebooks/` (01 a 05, ejecutados), `presentacion/` (presentación interactiva autocontenida, `presentacion.html`, y su generador), `tests/test_policy_unit.py` (copia de la prueba de la raíz) y `VERIFICACION_CIFRAS.md` (cada cifra de `STRATEGY.md` con el CSV de donde sale).\n"
        "\n"
        "Los resultados (CSV, figuras e informes del motor), los índices de los escenarios sintéticos y las referencias están en `solucion/` del mismo repositorio, para no duplicarlos aquí. Los scripts de `src/` suponen esa estructura (`solucion/outputs/`, `solucion/scenarios_mc/`).\n"
        "\n"
        "No incluye dependencias, cachés ni datasets: los `shipments.csv` sintéticos se regeneran con `src/build_scenarios.py` y `src/build_edge.py` (semillas fijas).\n", encoding="utf-8")
    copied.append("generated_artifacts/LEEME.md")
    return {"copied": copied}


def write_manifest(copied: list[str]) -> Path:
    convs = sorted(f"ai_conversations/{f.name}" for f in (SUB / "ai_conversations").iterdir() if f.is_file() and f.name != ".gitkeep") or ["ai_conversations/session-01.md"]
    redactions = []
    red_file = SOL / "outputs" / "csvs" / "ai_conversations_redacciones.json"
    if red_file.exists():
        redactions += json.loads(red_file.read_text(encoding="utf-8"))["redactions"]
    redactions.append({"file": "ai_conversations/cowork-sesion-01.md", "reason": "Copiada a mano por el candidato desde la interfaz en dos pegados; se conserva el texto sin reescribir y se señala el tramo intermedio que no se pudo pegar por errores. Se añadió una cabecera con herramienta, modelos, fechas y roles, etiquetas de rol entre corchetes, y un correo personal ajeno a la prueba sustituido por [REDACTED: correo personal]"})
    manifest = {
        "candidate": "[correo de inscripcion omitido]",
        "candidate_name": "Diego Alonso Araujo Villegas",
        "models_and_tools": [
            {"tool": "Claude Code (Anthropic)", "model": "claude-sonnet-5-5"},
            {"tool": "Claude Cowork (Anthropic): auditoria de la carpeta y los resultados, investigacion bibliografica y redaccion de prompts", "model": "claude-opus-4-8; claude-opus-5-5"},
            {"tool": "Optuna (TPE, QMC) y cmaes (CMA-ES), solo offline", "model": "no aplica"},
            {"tool": "pandas, numpy, matplotlib, Jupyter/nbclient, scipy (solo offline)", "model": "no aplica"},
            {"tool": "MarkItDown (Microsoft) para leer la bibliografia consultada", "model": "no aplica"},
            {"tool": "Obsidian (notas de trabajo y memoria del proyecto)", "model": "no aplica"},
            {"tool": "Playwright (navegador automatizado, solo para revisar visualmente la presentacion)", "model": "no aplica"},
        ],
        "evaluated_file": "candidate_strategy.py",
        "generated_artifacts": sorted(copied),
        "conversation_files": convs,
        "redactions": redactions,
        "declaration": "He revisado y asumo la responsabilidad de la entrega final.",
    }
    path = SUB / "submission_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    import jsonschema
    schema = json.loads((REPO / "submission_manifest.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(manifest, schema)
    return path


if __name__ == "__main__":
    info = build()
    strat = SOL / "STRATEGY_final.md"
    if strat.exists():
        shutil.copy2(strat, SUB / "STRATEGY.md")
    p = write_manifest(info["copied"])
    print("submission armada:", len(info["copied"]), "artefactos; manifest valido:", p)
