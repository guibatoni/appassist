"""Conservative, bounded discovery of independently relocated FM opponent names.

No ROM modifications, game execution, heuristically invented IDs, or cross-mod
imports. A strong isolated 39-record range is *structural evidence*, never
proof of which opponent the game uses at runtime.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
import re
import struct

from dueltrace_name_boundaries import read_name_table
from dueltrace_opponent_boundary_probe import (find_boundary_candidates,
    compact_boundary_evidence)
from dueltrace_opponent_forensics import (
    inspect_forensic_windows, explain_forensic_failure)

OPP_COUNT = 39
MIN_INDEX = 723
MAX_INDEX = 1152
MAX_INDICES = MAX_INDEX + OPP_COUNT + 1
MAX_CANDIDATES = 8
MAX_NAME = 60
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _ok_name(value: object) -> bool:
    return (isinstance(value, str) and 3 <= len(value.strip()) <= MAX_NAME
            and sum(ch.isalnum() for ch in value) >= 3
            and any(ch.isalpha() for ch in value)
            and "\ufffd" not in value and not any(ord(ch) < 32 for ch in value))


def _record_names(exe: bytes, *, pointer_base: int, text_base: int,
                  glyph_base: int) -> tuple[dict, dict]:
    ids = tuple(range(MIN_INDEX - 1, MAX_INDEX + OPP_COUNT + 1))
    records = read_name_table(
        exe, pointer_base=pointer_base, text_base=text_base,
        glyph_base=glyph_base, indices=ids, max_bytes=96)
    pointers = {
        i: struct.unpack_from("<H", exe, pointer_base + i * 2)[0]
        for i in ids
    }
    return records, pointers


def discover_independent_opponents(
        exe: bytes, *, pointer_base: int, text_base: int,
        glyph_base: int, rom_sha256: str,
        original_index: int = 0x329) -> dict:
    """Search shifted 39-name pointer runs within a finite, same-EXE range.

    A selected run requires 39 terminated and plausible names, >=37 unique
    names, distinct pointers, invalid neighbors, and no competing complete
    isolated run. Other possible names/terminators remain diagnostic only.
    """
    output = {
        "schema": 1, "state": "nao_localizado", "romSha256": rom_sha256,
        "exeSha256": sha256(exe).hexdigest() if isinstance(exe, bytes) else None,
        "searchedIndices": [MIN_INDEX, MAX_INDEX + OPP_COUNT - 1],
        "candidates": [], "selected": None,
        # Only in the local quarantined file. Compact reports deliberately
        # omit candidate names, ROM paths and extracted source bytes.
        "quarantinedRecords": [],
        "candidateCount": 0, "candidateOpponentCount": 0,
        "boundaryTerminatorEvidence": {"schema": 1, "candidateCount": 0,
                                      "candidates": [], "inGameVerified": False,
                                      "dropsVerified": False, "rankVerified": False},
        "forensicEvidence": {"schema": 1, "status": "nao_analisado",
                            "windows": [], "validated": False,
                            "inGameVerified": False, "mayPromote": False},
        "validated": False, "inGameVerified": False,
        "rankVerified": False, "dropsVerified": False,
        "note": "Identidade dos adversarios e seus drops requer prova independente."
    }
    if (not isinstance(exe, bytes) or len(exe) > 8 * 1024 * 1024
            or not isinstance(rom_sha256, str)
            or not HASH_PATTERN.fullmatch(rom_sha256)
            or not all(type(v) is int and v >= 0
                       for v in (pointer_base, text_base, glyph_base, original_index))
            or glyph_base + 93 * 4 > len(exe)
            or pointer_base + (MAX_INDEX + OPP_COUNT + 1) * 2 > len(exe)
            or text_base >= len(exe)):
        output["state"] = "executavel_ou_parametros_incompativeis"
        return output
    try:
        records, pointers = _record_names(
            exe, pointer_base=pointer_base,
            text_base=text_base, glyph_base=glyph_base)
    except (ValueError, struct.error, UnicodeError):
        output["state"] = "ponteiros_ou_glifos_incompativeis"
        return output

    # Single pass over already bounded record parsing, not hundreds of
    # independent file scans. The physical next-pointer boundary stops reads
    # from consuming a neighboring name even if a terminator is missing.
    names = {}
    readable = {}
    term = {}
    invalid = {}
    for i, record in records.items():
        raw = record.get("readablePrefix")
        readable[i] = raw if _ok_name(raw) else ""
        term[i] = record.get("recordStatus") == "ff_encontrado"
        names[i] = readable[i] if term[i] else ""
        invalid[i] = record.get("firstInvalidHex")
    hypotheses = []
    isolated = []
    for start in range(MIN_INDEX, MAX_INDEX + 1):
        indices = range(start, start + OPP_COUNT)
        complete = [names[i] for i in indices]
        prefixes = [readable[i] for i in indices]
        count = sum(bool(x) for x in complete)
        prefix_count = sum(bool(x) for x in prefixes)
        if count < 30 and prefix_count < 32:
            continue
        distinct = len(set(x for x in complete if x))
        ptr_unique = len({pointers[i] for i in indices})
        # Neighbors with readable but unterminated prefixes also count as
        # populated. A shifted window cannot redefine the first ID merely
        # because a mod uses a different terminator byte.
        left = bool(readable.get(start - 1))
        right = bool(readable.get(start + OPP_COUNT))
        edge_isolated = not left and not right
        invalid_bytes = Counter(invalid[i] for i in indices
                                if invalid.get(i) is not None)
        common_hex, common_count = (
            invalid_bytes.most_common(1)[0] if invalid_bytes else (None, 0))
        row = {
            "startIndex": start, "pointerBase": pointer_base,
            "nameTextBase": text_base, "glyphBase": glyph_base,
            "recognized": count, "readablePrefixes": prefix_count,
            "distinctNames": distinct, "distinctPointers": ptr_unique,
            "isolated": edge_isolated, "atOriginalPosition": start == original_index,
            "possibleDifferentTerminator": (
                common_hex if common_count >= 30 and prefix_count >= 34 else None),
            "firstInvalidCount": common_count,
            "samples": prefixes[:4],
            "validated": False, "inGameVerified": False
        }
        hypotheses.append(row)
        if (count == OPP_COUNT and distinct >= 37 and ptr_unique == OPP_COUNT
                and edge_isolated):
            isolated.append((row, [{"id": i + 1, "nome": complete[i]}
                                   for i in range(OPP_COUNT)]))

    hypotheses.sort(
        key=lambda x: (-x["recognized"], -x["readablePrefixes"],
                       -x["distinctNames"], -int(x["isolated"]),
                       abs(x["startIndex"] - original_index)))
    # Overlapping partial runs are not independent discoveries. Keep best
    # evidence per contiguous cluster but do not hide competing full runs.
    compact = []
    for row in hypotheses:
        if any(abs(row["startIndex"] - prev["startIndex"]) < OPP_COUNT
               for prev in compact):
            continue
        compact.append(row)
        if len(compact) >= MAX_CANDIDATES:
            break
    output["candidates"] = compact
    # Keep complete per-ID observations for investigation. These data are
    # NEVER imported into the public library from this file.
    output["quarantinedRecords"] = [
        {"startIndex": row["startIndex"],
         "records": [
             {"id": i + 1, "name": readable.get(row["startIndex"] + i, ""),
              "recordStatus": records[row["startIndex"] + i].get("recordStatus"),
              "firstInvalidHex": records[row["startIndex"] + i].get("firstInvalidHex"),
              "firstInvalidOffset": records[row["startIndex"] + i].get("firstInvalidOffset")}
             for i in range(OPP_COUNT)],
         "validated": False, "inGameVerified": False}
        for row in compact[:3]]
    output["candidateCount"] = len(compact)
    output["candidateOpponentCount"] = max(
        (max(x["recognized"], x["readablePrefixes"]) for x in hypotheses), default=0)
    # A second path considers ONLY physical record boundaries. A common
    # invalid byte is not enough: each of the 39 records must end on the
    # same control marker with no nonzero bytes before the next pointer.
    boundary_candidates = find_boundary_candidates(
        exe, hypotheses=hypotheses, records=records,
        pointers=pointers, text_base=text_base)
    output["boundaryTerminatorEvidence"] = compact_boundary_evidence(
        boundary_candidates)
    output["forensicEvidence"] = inspect_forensic_windows(
        exe, hypotheses=hypotheses, records=records, pointers=pointers,
        text_base=text_base)
    if len(isolated) + len(boundary_candidates) == 1:
        if isolated:
            row, opponents = isolated[0]
            output["state"] = "layout_independente_unico_estrutural"
            selected_evidence = "ff_terminado_39_ponteiros_unicos"
            start = row["startIndex"]
        else:
            boundary = boundary_candidates[0]
            output["state"] = "layout_terminador_alternativo_estrutural"
            opponents = [{"id": i + 1, "nome": name}
                         for i, name in enumerate(boundary["names"])]
            selected_evidence = "marcador_alternativo_e_38_fronteiras_fisicas"
            start = boundary["startIndex"]
        # Structural only: this does not verify in-game opponent ID order,
        # drop weights, fusion mapping, MIPS behavior or rank labels.
        output["selected"] = {
            "startIndex": start, "opponents": opponents, "count": OPP_COUNT,
            "evidence": selected_evidence,
            "validated": False, "inGameVerified": False
        }
        return output
    if len(isolated) + len(boundary_candidates) > 1:
        output["state"] = "layouts_completos_ambiguos"
    elif hypotheses:
        output["state"] = ("hipotese_terminador_alternativo"
                           if any(x["possibleDifferentTerminator"] for x in hypotheses)
                           else "tabelas_parciais_nao_verificadas")
    return output



def explain_opponent_blocker(report: dict) -> dict:
    """Explain rejection with evidence, never assert a specific encoding.

    This is safe for the UI: no ROM paths, actual opponent names, raw bytes,
    full hashes or executable names. A uniform invalid byte does NOT by
    itself prove that the mod uses an alternative string terminator.
    """
    state = report.get("state", "nao_localizado")
    candidates = report.get("candidates") or []
    best = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
    if state in ("layout_independente_unico_estrutural",
                 "layout_terminador_alternativo_estrutural"):
        return {"code": "nomes_estruturais", "reason":
                "39 nomes encontrados estruturalmente; ordem e IDs ainda dependem de prova em jogo."}
    if state == "layouts_completos_ambiguos":
        return {"code": "multiplos_blocos", "reason":
                "Mais de uma sequência completa de 39 nomes; não há base para escolher os IDs automaticamente."}
    if state == "hipotese_terminador_alternativo":
        deep = report.get("forensicEvidence")
        if isinstance(deep, dict) and deep.get("windows"):
            explanation = explain_forensic_failure(deep)
            if explanation["code"] not in ("sem_diagnostico_profundo",
                                            "delimitador_fisico_coerente"):
                return {"code": "fronteira_" + explanation["code"],
                        "reason": explanation["reason"] +
                                  " Evidência preservada para engenharia reversa."}
        terminator = next((x.get("possibleDifferentTerminator") for x in candidates
                           if isinstance(x, dict) and x.get("possibleDifferentTerminator")), None)
        suffix = f" (byte observado {terminator})" if terminator else ""
        return {"code": "terminador_incompativel", "reason":
                "Há nomes legíveis, mas o terminador padrão 0xFF não foi comprovado"
                + suffix + ". É necessária análise da fronteira física dos registros."}
    if best and best.get("recognized") == OPP_COUNT and not best.get("isolated"):
        return {"code": "bloco_nao_isolado", "reason":
                "39 nomes terminados foram lidos, mas a sequência não possui limites independentes comprovados."}
    if best and best.get("distinctPointers", 0) < OPP_COUNT:
        return {"code": "ponteiros_repetidos", "reason":
                "Há ponteiros compartilhados entre os candidatos; a correspondência de IDs ainda é ambígua."}
    if best and best.get("recognized", 0) == OPP_COUNT and best.get("distinctNames", 0) < 37:
        return {"code": "nomes_repetidos", "reason":
                "O conjunto tem nomes repetidos demais para garantir uma lista distinta de adversários."}
    if best:
        return {"code": "nomes_parciais", "reason":
                "Foram encontrados nomes candidatos, mas não 39 registros completos e independentes."}
    if state in ("executavel_ou_parametros_incompativeis",
                 "ponteiros_ou_glifos_incompativeis"):
        return {"code": "layout_incompativel", "reason":
                "O layout de ponteiros, texto ou glifos não pôde ser lido com segurança."}
    return {"code": "nenhuma_tabela_conclusiva", "reason":
            "A busca limitada não encontrou uma sequência de 39 nomes estruturalmente suficiente."}


def compact_opponent_evidence(report: dict) -> dict:
    """Preserve bounded metadata without copying 39 names into relatorio.json."""
    explanation = explain_opponent_blocker(report)
    return {
        "schema": 2, "state": report.get("state", "nao_localizado"),
        "reasonCode": explanation["code"],
        "reason": explanation["reason"],
        "candidateCount": report.get("candidateCount", 0),
        "candidateOpponentCount": report.get("candidateOpponentCount", 0),
        "candidates": [
            {k: v for k, v in row.items() if k != "samples"}
            for row in (report.get("candidates") or [])[:MAX_CANDIDATES]
            if isinstance(row, dict)
        ],
        "selectedStartIndex": (
            report["selected"]["startIndex"]
            if isinstance(report.get("selected"), dict) else None),
        "boundaryTerminatorEvidence": (report.get("boundaryTerminatorEvidence")
                                       if isinstance(report.get("boundaryTerminatorEvidence"), dict)
                                       else {"schema": 1, "candidateCount": 0,
                                             "candidates": []}),
        "forensicEvidence": (report.get("forensicEvidence")
                             if isinstance(report.get("forensicEvidence"), dict)
                             else {"schema": 1, "status": "nao_analisado",
                                   "windows": [], "validated": False}),
        "validated": False, "inGameVerified": False,
        "rankVerified": False, "dropsVerified": False
    }
