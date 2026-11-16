"""Checklist de cumplimiento verificable por programa (sin ejecutar el motor). Escribe outputs/csvs/compliance_checks.json.

Cubre: restricciones del archivo evaluado (stdlib, sin hilos/procesos/red/E-S), integridad de archivos protegidos,
estructura exacta de submission/, manifest contra su schema, longitud de STRATEGY.md y exclusiones de generated_artifacts.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "solucion" / "outputs" / "csvs" / "compliance_checks.json"
ALLOWED_IMPORTS = {"__future__", "heapq", "collections", "interfaces"}
FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "input", "breakpoint"}
FORBIDDEN_MODULES = {"os", "sys", "subprocess", "threading", "multiprocessing", "socket", "urllib", "http", "requests", "ctypes",
                     "importlib", "shutil", "pathlib", "asyncio", "concurrent", "numpy", "pandas", "scipy", "optuna", "ortools"}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_candidate(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    imports, bad_calls, bad_attrs = set(), [], []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imports.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            imports.add((n.module or "").split(".")[0])
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FORBIDDEN_NAMES:
            bad_calls.append((n.func.id, n.lineno))
        elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in FORBIDDEN_MODULES:
            bad_attrs.append((n.value.id, n.lineno))
    return {
        "imports": sorted(imports),
        "imports_permitidos": imports <= ALLOWED_IMPORTS,
        "llamadas_prohibidas": bad_calls,
        "usos_de_modulos_prohibidos": bad_attrs,
        "tiene_clase_CandidateStrategy": any(isinstance(n, ast.ClassDef) and n.name == "CandidateStrategy" for n in tree.body),
        "sha256": sha(path),
    }


def main() -> dict:
    res: dict = {}
    root_c, sub_c = REPO / "candidate_strategy.py", REPO / "submission" / "candidate_strategy.py"
    res["candidato_raiz"] = check_candidate(root_c)
    if sub_c.exists():
        res["submission_identico_a_raiz"] = sha(sub_c) == sha(root_c)
    prot = json.loads((REPO / "protected_files.sha256").read_text(encoding="utf-8"))["files"]
    res["protegidos_alterados"] = [k for k, v in prot.items() if sha(REPO / k) != v]
    sub = REPO / "submission"
    if sub.exists():
        expected = {"candidate_strategy.py", "generated_artifacts", "ai_conversations", "STRATEGY.md", "submission_manifest.json"}
        present = {p.name for p in sub.iterdir()}
        res["submission_estructura_exacta"] = present == expected
        res["submission_entradas"] = sorted(present)
        conv = sorted(p.name for p in (sub / "ai_conversations").iterdir() if p.name != ".gitkeep")
        res["ai_conversations_archivos"] = conv
        res["ai_conversations_con_archivos_y_sin_gitkeep"] = bool(conv) and not (sub / "ai_conversations" / ".gitkeep").exists()
        strat = sub / "STRATEGY.md"
        if strat.exists():
            text = strat.read_text(encoding="utf-8")
            words = len(re.findall(r"\w+", text))
            res["strategy_palabras"] = words
            res["strategy_<=2500"] = words <= 2500
            res["strategy_menciona_LEG07_y_LEG12"] = "LEG-07" in text and "LEG-12" in text
        man = sub / "submission_manifest.json"
        if man.exists():
            import jsonschema
            m = json.loads(man.read_text(encoding="utf-8"))
            jsonschema.validate(m, json.loads((REPO / "submission_manifest.schema.json").read_text(encoding="utf-8")))
            res["manifest_valido_schema"] = True
            res["manifest_candidate"] = m["candidate"]
            res["manifest_candidate_name"] = m["candidate_name"]
            listed = set(m["generated_artifacts"])
            actual = {f"generated_artifacts/{p.relative_to(sub / 'generated_artifacts').as_posix()}"
                      for p in (sub / "generated_artifacts").rglob("*") if p.is_file()}
            res["manifest_lista_coincide_con_carpeta"] = listed == actual
            res["manifest_conversation_files_existen"] = all((sub / f).is_file() for f in m["conversation_files"]) and set(m["conversation_files"]) == {f"ai_conversations/{n}" for n in conv}
            res["manifest_sin_claves_extra_y_modelos"] = sorted(m.keys()) == sorted(["candidate", "candidate_name", "models_and_tools", "evaluated_file", "generated_artifacts", "conversation_files", "redactions", "declaration"])
        ga = sub / "generated_artifacts"
        bad = [p.as_posix() for p in ga.rglob("*") if "__pycache__" in p.parts or p.suffix == ".pyc" or p.name == "shipments.csv"
               or "cache" in p.relative_to(ga).parts or "scratch" in p.relative_to(ga).parts or p.suffix == ".log"]
        res["generated_artifacts_exclusiones_ok"] = not bad
        res["generated_artifacts_archivos"] = sum(1 for p in ga.rglob("*") if p.is_file())
        res["generated_artifacts_MB"] = round(sum(p.stat().st_size for p in ga.rglob("*") if p.is_file()) / 1048576, 2)
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    return res


if __name__ == "__main__":
    r = main()
    print(json.dumps(r, indent=2, ensure_ascii=False))
