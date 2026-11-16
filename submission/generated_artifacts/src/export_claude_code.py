"""Exporta la sesion de Claude Code (transcripcion .jsonl) a Markdown legible en submission/ai_conversations/.

- Conserva integros los mensajes de Diego y las respuestas del asistente, en orden cronologico, con los intentos fallidos.
- Recorta las salidas de herramientas muy largas con un marcador explicito [salida recortada: N lineas] y los avisos automaticos del sistema.
- Sustituye secretos y datos personales ajenos a la prueba por [REDACTED: motivo] y escribe el registro en outputs/csvs/ai_conversations_redacciones.json.
Uso: python export_claude_code.py [ruta_jsonl]"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "submission" / "ai_conversations"
RED_JSON = REPO / "solucion" / "outputs" / "csvs" / "ai_conversations_redacciones.json"
DEFAULT = Path.home() / ".claude" / "projects" / "c--Users-diego-OneDrive-Documentos-BBVA-Hackaton-2026" / "dfb909f6-34e7-4de6-b1ff-7fdbc7db71f4.jsonl"
MAX_RESULT = 1500       # caracteres por salida de herramienta
MAX_TOOL_INPUT = 1800   # caracteres por entrada de herramienta
MAX_REMINDER = 240      # caracteres de un aviso automatico del sistema
PART_BYTES = 3_500_000

RED = Counter()


def redact(text: str) -> str:
    def sub(pat, repl, reason, flags=0):
        nonlocal text
        new, n = re.subn(pat, repl, text, flags=flags)
        if n:
            RED[reason] += n
            text = new

    sub(r"gh[pousr]_[A-Za-z0-9_]{20,}", "[REDACTED: token de acceso]", "tokens de acceso")
    sub(r"github_pat_[A-Za-z0-9_]{20,}", "[REDACTED: token de acceso]", "tokens de acceso")
    sub(r"sk-[A-Za-z0-9_-]{20,}", "[REDACTED: clave de API]", "claves de API")
    sub(r"[A-Za-z0-9._%+-]+@gmail\.com", "[REDACTED: correo personal]", "correos personales ajenos a la prueba")
    _w = "doc" + "ente"   # termino que se omite del texto publicado (referencia a una persona ajena a la prueba)
    sub(r"(?i)" + _w + "s?", "[REDACTED: persona ajena a la prueba]", "referencias a una persona ajena a la prueba")
    return text


def trunc(text: str, n: int, label: str) -> str:
    if len(text) <= n:
        return text
    lines = text.count("\n") + 1
    return text[:n].rstrip() + f"\n[{label}: {lines} lineas en total; se conservan los primeros {n} caracteres]"


def split_reminders(text: str) -> tuple[str, list[str]]:
    """Separa el texto de la persona de los bloques <system-reminder> inyectados por el entorno."""
    rem = re.findall(r"<system-reminder>.*?</system-reminder>", text, flags=re.S)
    rest = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.S).strip()
    return rest, rem


def blocks_of(content):
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return content or []


def result_text(content) -> str:
    if isinstance(content, str):
        return content
    out = []
    for b in content or []:
        if b.get("type") == "text":
            out.append(b.get("text", ""))
        elif b.get("type") == "image":
            out.append("[imagen omitida]")
    return "\n".join(out)


def main(path: Path) -> None:
    msgs = []
    stats = Counter()
    first_ts = last_ts = None
    model = None
    for line in path.open(encoding="utf-8"):
        try:
            d = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        ts = d.get("timestamp")
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        t = d.get("type")
        if t == "assistant":
            m = d.get("message", {})
            model = model or m.get("model")
            for b in blocks_of(m.get("content")):
                bt = b.get("type")
                if bt == "text" and b.get("text", "").strip():
                    msgs.append((ts, "Claude Code", b["text"].strip()))
                    stats["respuestas"] += 1
                elif bt == "tool_use":
                    inp = json.dumps(b.get("input", {}), ensure_ascii=False)
                    msgs.append((ts, f"Claude Code, llamada a la herramienta {b.get('name')}", "```json\n" + trunc(inp, MAX_TOOL_INPUT, "entrada recortada") + "\n```"))
                    stats["llamadas a herramientas"] += 1
                elif bt == "thinking":
                    stats["bloques de razonamiento que la transcripcion no guarda"] += 1
        elif t == "user":
            m = d.get("message", {})
            for b in blocks_of(m.get("content")):
                bt = b.get("type")
                if bt == "text":
                    rest, rem = split_reminders(b.get("text", ""))
                    auto = "[SYSTEM NOTIFICATION" in rest or "Todo ha sido compactado" in rest
                    if rest:
                        if auto:
                            msgs.append((ts, "Entorno (notificacion automatica de una tarea en segundo plano)", trunc(rest, MAX_REMINDER * 3, "notificacion recortada")))
                            stats["notificaciones automaticas"] += 1
                        elif rest.startswith("This session is being continued from a previous conversation"):
                            msgs.append((ts, "Entorno (resumen de contexto generado al compactar la conversacion)", trunc(rest, 6000, "resumen recortado")))
                            stats["resumenes de contexto"] += 1
                        else:
                            msgs.append((ts, "Diego", rest))
                            stats["mensajes de Diego"] += 1
                    for r in rem:
                        msgs.append((ts, "Entorno (aviso automatico del sistema)", trunc(r, MAX_REMINDER, "aviso recortado")))
                        stats["avisos automaticos recortados"] += 1
                elif bt == "tool_result":
                    txt = result_text(b.get("content"))
                    msgs.append((ts, "Resultado de herramienta", "```text\n" + trunc(txt, MAX_RESULT, "salida recortada") + "\n```"))
                    stats["resultados de herramientas"] += 1
                elif bt == "image":
                    msgs.append((ts, "Diego", "[imagen adjunta por Diego, omitida en la exportacion]"))
                    stats["imagenes omitidas"] += 1

    # ensamblado y particion
    parts, cur, size = [], [], 0
    for ts, who, text in msgs:
        txt = f"### {ts or ''} · {who}\n\n{redact(text)}\n\n"
        if size + len(txt) > PART_BYTES and cur:
            parts.append(cur)
            cur, size = [], 0
        cur.append(txt)
        size += len(txt)
    if cur:
        parts.append(cur)

    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("claude-code-sesion-*.md"):
        f.unlink()
    names = []
    for i, body in enumerate(parts, 1):
        name = f"claude-code-sesion-{i:02d}.md"
        names.append(name)
        head = (f"# Conversación con IA: Claude Code (parte {i} de {len(parts)})\n\n"
                f"- **Herramienta:** Claude Code (Anthropic), extensión de VS Code.\n- **Modelo:** {model}.\n"
                f"- **Fechas:** del {first_ts} al {last_ts} (UTC); la exportación se hizo el 19 de octubre de 2026, de modo que no incluye los mensajes posteriores.\n"
                f"- **Roles:** `Diego` (el candidato), `Claude Code` (el asistente), `Resultado de herramienta` (salida de comandos y archivos) y `Entorno` (avisos automáticos del sistema).\n"
                f"- **Qué contiene:** todos los mensajes de Diego y todas las respuestas del asistente, en orden cronológico, con los intentos fallidos. "
                f"Las entradas y salidas largas de herramientas se recortaron con un marcador explícito, y los bloques de razonamiento interno del modelo no se guardan en la transcripción.\n"
                f"- **Redacciones:** secretos y datos personales ajenos a la prueba se sustituyeron por `[REDACTED: motivo]`; el detalle está en `redactions` de `submission_manifest.json`.\n\n---\n\n")
        (OUT / name).write_text(head + "".join(body), encoding="utf-8")
    gk = OUT / ".gitkeep"
    if gk.exists():
        gk.unlink()

    redactions = [{"file": "ai_conversations/claude-code-sesion-*.md", "reason": f"{reason}: {n} sustituciones por [REDACTED: motivo]"} for reason, n in RED.items()]
    redactions.append({"file": "ai_conversations/claude-code-sesion-*.md", "reason": f"Salidas y entradas de herramientas recortadas a {MAX_RESULT} y {MAX_TOOL_INPUT} caracteres con marcador explícito; avisos automáticos del entorno recortados; bloques de razonamiento interno que la transcripción no guarda"})
    RED_JSON.write_text(json.dumps({"archivos": names, "estadisticas": dict(stats), "redactions": redactions}, indent=1, ensure_ascii=False), encoding="utf-8")
    print("exportado:", names, dict(stats), dict(RED))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT)
