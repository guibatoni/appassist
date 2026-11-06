"""Bounded, non-promoting control-flow investigation of FM text streams.

Reads ONLY the currently selected executable's own text bank. The original
game's FD lo hi cursor redirection is an investigative hypothesis. We never
publish card/opponent strings, infer live IDs, or modify ROMs. Unknown F8/Fx
controls stop the traversal instead of being guessed as one-byte symbols.
"""
from __future__ import annotations

from dueltrace_name_boundaries import read_glyphs

WINDOW_SIZE = 39
MAX_WINDOWS = 5
MAX_EXE_SIZE = 8 * 1024 * 1024
BANK_SIZE = 0x10000
MAX_STEPS = 192
MAX_HOPS = 4

def trace_one_stream(exe: bytes, *, start: int, local_end: int,
                     text_base: int, glyphs: tuple[str, ...]) -> dict:
    """Inspect bounded cursor movement; only counters/status may leave."""
    result = {"state": "limite", "fdJumps": 0, "glyphCount": 0,
              "glyphsAfterJump": 0, "steps": 0, "controlF8": 0}
    bank_end = min(len(exe), text_base + BANK_SIZE)
    if not (text_base <= start < bank_end and start < local_end <= len(exe)):
        result["state"] = "fora_do_banco"
        return result
    cursor, boundary = start, local_end
    visited = set()
    for _ in range(MAX_STEPS):
        if not (text_base <= cursor < bank_end and cursor < boundary):
            result["state"] = "fronteira"
            break
        if cursor in visited:
            result["state"] = "ciclo"
            break
        visited.add(cursor)
        value = exe[cursor]
        result["steps"] += 1
        if value == 0xFF:
            result["state"] = "ff_alcancado"
            break
        if value == 0xFD:
            if result["fdJumps"] >= MAX_HOPS:
                result["state"] = "limite_saltos"
                break
            if cursor + 2 >= min(boundary, bank_end):
                result["state"] = "argumento_fd_truncado"
                break
            target = text_base + exe[cursor+1] + (exe[cursor+2] << 8)
            if not text_base <= target < bank_end:
                result["state"] = "alvo_fd_fora_do_banco"
                break
            result["fdJumps"] += 1
            cursor = target
            # A new target has no independently validated name boundary;
            # cap it to the current 64 KiB bank and a per-stream step budget.
            boundary = bank_end
            continue
        if value == 0xF8:
            result["controlF8"] += 1
            result["state"] = "controle_f8_desconhecido"
            break
        if value == 0xFE:  # known line break in retail text engine
            cursor += 1
            continue
        if value == 0 or (value < len(glyphs) and bool(glyphs[value])):
            if value != 0:
                result["glyphCount"] += 1
                if result["fdJumps"]:
                    result["glyphsAfterJump"] += 1
            cursor += 1
            continue
        result["state"] = "controle_desconhecido"
        break
    return result


def audit_flow_window(exe: bytes, *, start_index: int, records: dict,
                      pointers: dict, text_base: int, glyph_base: int) -> dict:
    summary = {"schema": 1, "state": "incompleto", "recordsExamined": 0,
               "ffReached": 0, "ffReachedAfterFd": 0,
               "fdRoutes": 0, "fdRoutesWithGlyphs": 0,
               "cycleCount": 0, "unknownControlCount": 0,
               "f8ControlCount": 0, "boundaryStopCount": 0,
               "truncatedArgumentCount": 0, "hopLimitCount": 0,
               "stepLimitCount": 0, "maxHopDepth": 0,
               "inGameVerified": False, "validated": False,
               "mayPromote": False, "dropsVerified": False,
               "rankVerified": False}
    if (not isinstance(exe, bytes) or not 0 < len(exe) <= MAX_EXE_SIZE
            or type(start_index) is not int or start_index < 0
            or type(text_base) is not int or text_base < 0
            or type(glyph_base) is not int or glyph_base < 0
            or not isinstance(records, dict) or not isinstance(pointers, dict)):
        summary["state"] = "entrada_invalida"
        return summary
    try:
        glyphs = read_glyphs(exe, glyph_base)
        indices = range(start_index, start_index + WINDOW_SIZE)
        positions = [text_base + pointers[i] for i in indices]
        rows = [records[i] for i in indices]
    except (KeyError, ValueError, TypeError):
        summary["state"] = "layout_indisponivel"
        return summary
    if any(type(p) is not int or not 0 <= p < len(exe) for p in positions):
        summary["state"] = "ponteiros_invalidos"
        return summary
    for pos, row in zip(positions, rows):
        if not isinstance(row, dict):
            continue
        span = row.get("spanBytes")
        if type(span) is not int or span <= 0:
            continue
        start = pos + (3 if row.get("headerPresent") is True else 0)
        end = min(len(exe), pos + min(span, MAX_STEPS))
        metrics = trace_one_stream(
            exe, start=start, local_end=end, text_base=text_base, glyphs=glyphs)
        summary["recordsExamined"] += 1
        summary["maxHopDepth"] = max(summary["maxHopDepth"], metrics["fdJumps"])
        if metrics["fdJumps"]:
            summary["fdRoutes"] += 1
            summary["fdRoutesWithGlyphs"] += int(metrics["glyphsAfterJump"] > 0)
        state = metrics["state"]
        if state == "ff_alcancado":
            summary["ffReached"] += 1
            summary["ffReachedAfterFd"] += int(metrics["fdJumps"] > 0)
        elif state == "ciclo":
            summary["cycleCount"] += 1
        elif state in ("controle_desconhecido", "controle_f8_desconhecido"):
            summary["unknownControlCount"] += 1
            summary["f8ControlCount"] += int(state == "controle_f8_desconhecido")
        elif state in ("fronteira", "fora_do_banco", "alvo_fd_fora_do_banco"):
            summary["boundaryStopCount"] += 1
        elif state == "argumento_fd_truncado":
            summary["truncatedArgumentCount"] += 1
        elif state == "limite_saltos":
            summary["hopLimitCount"] += 1
        elif state == "limite":
            summary["stepLimitCount"] += 1
    summary["state"] = ("fluxos_auditados_sem_validacao" if summary["recordsExamined"]
                        else "sem_registros")
    return summary


def inspect_flow_windows(exe: bytes, *, hypotheses: list, records: dict,
                         pointers: dict, text_base: int, glyph_base: int) -> dict:
    summary = {"schema": 1, "state": "sem_janelas", "windows": [],
               "validated": False, "mayPromote": False}
    if not isinstance(hypotheses, list):
        return summary
    for row in hypotheses:
        if len(summary["windows"]) >= MAX_WINDOWS:
            break
        start = row.get("startIndex") if isinstance(row, dict) else None
        if type(start) is not int:
            continue
        summary["windows"].append(audit_flow_window(
            exe, start_index=start, records=records, pointers=pointers,
            text_base=text_base, glyph_base=glyph_base))
    if summary["windows"]:
        summary["state"] = "janelas_auditadas"
    return summary
