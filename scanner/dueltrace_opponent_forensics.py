"""Forensic summaries for ambiguous FM opponent records.

The source is only the executable already held in memory by the scanner.
The report contains bounded counters and rejection codes: no ROM bytes,
candidate names, filenames, private paths, or raw MIPS code. Never promotes
IDs, drops, effects, or RANK.
"""
from __future__ import annotations

from collections import Counter

from dueltrace_opponent_boundary_probe import inspect_boundary_window

MAX_WINDOWS = 5
OPPONENTS = 39
MAX_RECORD_SPAN = 96

def _hist(values, max_items=10):
    return {str(key): int(count) for key, count in
            Counter(values).most_common(max_items) if key is not None}

def inspect_forensic_windows(
        exe: bytes, *, hypotheses: list, records: dict,
        pointers: dict, text_base: int, max_windows: int = MAX_WINDOWS) -> dict:
    """Explain *why* the strongest 39-name candidate windows were rejected."""
    out = {"schema": 1, "status": "nenhuma_janela", "windows": [],
           "inGameVerified": False, "validated": False,
           "mayPromote": False, "dropsVerified": False, "rankVerified": False}
    if (not isinstance(exe, bytes) or len(exe) > 8*1024*1024
            or not isinstance(hypotheses, list)
            or not isinstance(records, dict) or not isinstance(pointers, dict)
            or type(text_base) is not int or text_base < 0):
        out["status"] = "entrada_invalida"
        return out
    max_windows = max(0, min(MAX_WINDOWS, max_windows if type(max_windows) is int else 0))
    for hypothesis in hypotheses:
        if len(out["windows"]) >= max_windows:
            break
        if not isinstance(hypothesis, dict):
            continue
        start = hypothesis.get("startIndex")
        if type(start) is not int or start < 0:
            continue
        indices = range(start, start + OPPONENTS)
        try:
            rows = [records[i] for i in indices]
            positions = [text_base + pointers[i] for i in indices]
        except (KeyError, TypeError):
            continue
        if any(not isinstance(row, dict) for row in rows):
            continue
        deltas = [b-a for a,b in zip(positions, positions[1:])]
        statuses = [row.get("recordStatus") for row in rows]
        invalid = [row.get("firstInvalidHex") for row in rows
                   if row.get("firstInvalidHex")]
        code = inspect_boundary_window(exe, start_index=start, records=records,
                                       pointers=pointers, text_base=text_base)
        out["windows"].append({
            "startIndex": start,
            "candidateReadable": hypothesis.get("readablePrefixes", 0),
            "terminatedFF": sum(value == "ff_encontrado" for value in statuses),
            "statusHistogram": _hist(statuses),
            "firstInvalidByteHistogram": _hist(invalid),
            "firstInvalidOffsetMin": min(
                (row["firstInvalidOffset"] for row in rows
                 if type(row.get("firstInvalidOffset")) is int), default=None),
            "firstInvalidOffsetMax": max(
                (row["firstInvalidOffset"] for row in rows
                 if type(row.get("firstInvalidOffset")) is int), default=None),
            "pointerCountDistinct": len(set(positions)),
            "pointerNonIncreasingPairs": sum(delta <= 0 for delta in deltas),
            "pointerSpanMin": min(deltas) if deltas else None,
            "pointerSpanMax": max(deltas) if deltas else None,
            "recordBoundaryKnown": sum(row.get("boundaryKnown") is True
                                       for row in rows),
            "recordBoundaryReached": sum(row.get("boundaryReached") is True
                                         for row in rows),
            "recordWithHeader": sum(row.get("headerPresent") is True
                                    for row in rows),
            "boundaryDecision": code["status"],
            "eligibleForStructuralOnly": bool(code["eligible"]),
            "terminatorHypothesis": code.get("terminator"),
            "validated": False, "inGameVerified": False,
        })
    out["status"] = "janelas_auditadas" if out["windows"] else "nenhuma_janela"
    return out

REJECTION_REASONS = {
    "dados_apos_marcador":
        "Há dados não nulos após o possível marcador antes do próximo registro.",
    "ponteiros_repetidos_ou_fora_de_ordem":
        "Os ponteiros são repetidos ou não seguem ordem física crescente.",
    "fronteira_fisica_fora_do_limite":
        "O espaço entre os registros excede o limite conservador do parser.",
    "marcadores_inconsistentes":
        "Os registros usam bytes de controle diferentes no ponto de parada.",
    "marcador_nao_suportado":
        "O primeiro byte não reconhecido não pertence aos marcadores permitidos.",
    "nomes_ou_codificacao_nao_conclusivos":
        "Os nomes legíveis não formam 39 registros com codificação coerente.",
    "ultimo_registro_sem_limite_seguro":
        "O último nome não possui um limite seguro comprovado.",
    "marcador_nao_reproduzivel":
        "O marcador observado não coincide com a posição física esperada.",
    "incompleto":
        "Não há informações suficientes para comprovar 39 nomes.",
    "delimitador_fisico_coerente":
        "Os limites são coerentes estruturalmente; IDs ainda não foram conferidos em jogo.",
}

def explain_forensic_failure(summary: dict) -> dict:
    rows = summary.get("windows", []) if isinstance(summary, dict) else []
    if not isinstance(rows, list) or not rows:
        return {"code": "sem_diagnostico_profundo",
                "reason": "Ainda não há dados para verificar a fronteira física dos 39 nomes."}
    row = rows[0]
    code = row.get("boundaryDecision", "incompleto")
    return {"code": code, "reason": REJECTION_REASONS.get(
        code, "A estrutura de nomes permanece ambígua e não será publicada.")}
