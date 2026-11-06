"""Safe probe for non-FF, physically bounded opponent name records.

This module never edits the ISO or infers drop/RANK mappings. The only
eligible alternative terminators are control bytes 0xF0..0xFE, and every
candidate must have 39 unique pointers with unambiguous physical boundaries.
Ordinal table order may differ from physical address order; aliases remain
in quarantine without assigning an opponent ID.
The result is *structural* evidence only; IDs require validation in game.
"""
from __future__ import annotations

from collections import Counter

OPP_COUNT = 39
MAX_PHYSICAL_SPAN = 96
MAX_ZERO_PADDING = 16
MIN_LAST_PADDING = 8


def inspect_boundary_window(exe: bytes, *, start_index: int, records: dict,
                            pointers: dict, text_base: int) -> dict:
    """Read a complete candidate using actual next-record byte positions.

    Fail closed on shared pointers, a missing glyph prefix,
    mixed/embedded control bytes, excessive padding, or unknown terminal.
    """
    result = {
        "startIndex": start_index, "status": "incompleto",
        "eligible": False, "terminator": None, "verifiedBoundaries": 0,
        "distinctNames": 0, "names": [],
        "ordinalPointerInversions": 0, "physicalOrderRemapped": False,
        "validated": False, "inGameVerified": False,
        "dropsVerified": False, "rankVerified": False,
    }
    if (not isinstance(exe, bytes) or not isinstance(start_index, int)
            or not isinstance(text_base, int) or text_base < 0
            or not isinstance(records, dict) or not isinstance(pointers, dict)):
        return result
    ids = tuple(range(start_index, start_index + OPP_COUNT))
    try:
        positions = [text_base + pointers[i] for i in ids]
        observed = [records[i] for i in ids]
    except (KeyError, TypeError):
        return result
    if any(not 0 <= pos < len(exe) for pos in positions):
        result["status"] = "ponteiros_fora_do_arquivo"
        return result
    if len(set(positions)) != OPP_COUNT:
        # Reusing an offset may be legal for some games, but it does not
        # prove which ordinal IDs are aliases. Retain diagnostic evidence.
        result["status"] = "ponteiros_repetidos"
        return result
    inversions = sum(right <= left for left, right in zip(positions, positions[1:]))
    result["ordinalPointerInversions"] = inversions
    result["physicalOrderRemapped"] = bool(inversions)

    # Parse the SAME 39 pointer-table entries by *physical* position.
    # Their names are returned in original index order, NEVER in physical
    # sorted order. The index-to-pointer mapping is preserved.
    physical_order = sorted(range(OPP_COUNT), key=lambda ordinal: positions[ordinal])
    names_by_ordinal = [""] * OPP_COUNT
    terminals = []
    bounded = 0
    for offset, ordinal in enumerate(physical_order):
        pos = positions[ordinal]
        record = observed[ordinal]
        if not isinstance(record, dict):
            return result
        name = record.get("readablePrefix")
        first_invalid = record.get("firstInvalidHex")
        first_offset = record.get("firstInvalidOffset")
        if (record.get("recordStatus") != "glifo_invalido"
                or record.get("hasFF") is not False
                or not isinstance(name, str) or not 3 <= len(name) <= 60
                or not any(char.isalpha() for char in name)
                or not isinstance(first_offset, int) or first_offset < 3
                or not isinstance(first_invalid, str)):
            result["status"] = "nomes_ou_codificacao_nao_conclusivos"
            return result
        try:
            term = int(first_invalid, 16)
        except ValueError:
            return result
        if not 0xF0 <= term <= 0xFE:
            result["status"] = "marcador_nao_suportado"
            return result
        payload_start = pos + (3 if record.get("headerPresent") else 0)
        marker_pos = payload_start + first_offset
        if marker_pos >= len(exe) or exe[marker_pos] != term:
            result["status"] = "marcador_nao_reproduzivel"
            return result
        if offset < OPP_COUNT - 1:
            following = positions[physical_order[offset + 1]]
            if not 0 < following - pos <= MAX_PHYSICAL_SPAN:
                result["status"] = "fronteira_fisica_fora_do_limite"
                return result
            if marker_pos >= following:
                result["status"] = "marcador_alem_da_fronteira"
                return result
            # read_name_table already located the nearest physical pointer
            # across its entire inspected range; do not skip an interleaved
            # record that could belong to another structure.
            if (record.get("boundaryKnown") is True and
                    record.get("spanBytes") != following - pos):
                result["status"] = "ponteiro_intercalado"
                return result
            pad = exe[marker_pos + 1:following]
            if len(pad) > MAX_ZERO_PADDING or any(pad):
                result["status"] = "dados_apos_marcador"
                return result
            bounded += 1
        else:
            # The last record may have no following pointer. Demand a short
            # all-zero tail, never consume or guess a later record boundary.
            end = marker_pos + 1 + MIN_LAST_PADDING
            if end > len(exe) or any(exe[marker_pos + 1:end]):
                result["status"] = "ultimo_registro_sem_limite_seguro"
                return result
        terminals.append(term)
        names_by_ordinal[ordinal] = name
    result["verifiedBoundaries"] = bounded
    result["distinctNames"] = len(set(names_by_ordinal))
    if len(set(terminals)) != 1:
        result["status"] = "marcadores_inconsistentes"
        return result
    result["terminator"] = f"0x{terminals[0]:02X}"
    if result["distinctNames"] < 37:
        result["status"] = "nomes_repetidos"
        return result
    result.update(status="delimitador_fisico_coerente",
                  eligible=True, names=names_by_ordinal)
    return result


def find_boundary_candidates(exe: bytes, *, hypotheses: list, records: dict,
                             pointers: dict, text_base: int,
                             max_records: int = 430) -> list[dict]:
    """Return only unique structurally complete windows, bounded by budget."""
    chosen = []
    for row in hypotheses[:max_records]:
        if not isinstance(row, dict) or row.get("readablePrefixes") != OPP_COUNT:
            continue
        if row.get("distinctPointers") != OPP_COUNT or not row.get("isolated"):
            continue
        start = row.get("startIndex")
        if type(start) is not int:
            continue
        candidate = inspect_boundary_window(
            exe, start_index=start, records=records,
            pointers=pointers, text_base=text_base)
        if candidate["eligible"]:
            chosen.append(candidate)
    return chosen


def compact_boundary_evidence(candidates: list[dict]) -> dict:
    """Only metadata; names and raw executable bytes remain in quarantine."""
    return {"schema": 1,
            "candidateCount": len(candidates),
            "candidates": [{
                "startIndex": x["startIndex"],
                "terminator": x["terminator"],
                "verifiedBoundaries": x["verifiedBoundaries"],
                "distinctNames": x["distinctNames"],
                "status": x["status"],
                "physicalOrderRemapped": x["physicalOrderRemapped"],
                "ordinalPointerInversions": x["ordinalPointerInversions"],
                "validated": False
            } for x in candidates[:8]],
            "inGameVerified": False, "dropsVerified": False,
            "rankVerified": False}
