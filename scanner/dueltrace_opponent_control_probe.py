"""Read-only bounded audit of mixed 0xFD / 0xFF control bytes.

A PS1 text byte in the 0xF0..0xFE range may be a formatting command,
part of another coding scheme, or a terminator. Frequency is NOT proof.
Only aggregated counters leave the scanner; candidate IDs, names, absolute
offsets, raw bytes, and executable data remain unpublished.
"""
from __future__ import annotations

from collections import Counter

from dueltrace_name_boundaries import read_glyphs

OPP_COUNT = 39
MAX_RECORD_BYTES = 96
MAX_EXE_BYTES = 8 * 1024 * 1024
MAX_WINDOWS = 5


def audit_control_window(
        exe: bytes, *, start_index: int, records: dict, pointers: dict,
        text_base: int, glyph_base: int) -> dict:
    result = {
        "schema": 1, "state": "incompleto",
        "recordsExamined": 0, "distinctPointers": 0,
        "ffPresent": 0, "fdPresent": 0,
        "fdBeforeFf": 0, "fdWithoutFf": 0,
        "fdFollowedByGlyph": 0, "fdFollowedByZero": 0,
        "fdFollowedByControl": 0, "fdAtRecordEnd": 0,
        "fdWithGlyphBeforeFf": 0,
        "nonZeroAfterFf": 0, "nonZeroAfterFd": 0,
        "ffAfterFirstInvalid": 0, "interleavedOrTruncated": 0,
        "nonFfControlHistogram": {},
        "inGameVerified": False, "validated": False,
        "mayPromote": False, "dropsVerified": False, "ranksVerified": False,
    }
    if (not isinstance(exe, bytes) or not 0 < len(exe) <= MAX_EXE_BYTES
            or type(start_index) is not int or start_index < 0
            or type(text_base) is not int or text_base < 0
            or type(glyph_base) is not int or glyph_base < 0
            or not isinstance(records, dict) or not isinstance(pointers, dict)):
        result["state"] = "entrada_invalida"
        return result
    try:
        glyphs = read_glyphs(exe, glyph_base)
        indices = range(start_index, start_index + OPP_COUNT)
        positions = [text_base + pointers[i] for i in indices]
        parsed = [records[i] for i in indices]
    except (KeyError, ValueError, TypeError):
        result["state"] = "layout_nao_acessivel"
        return result
    if (any(not 0 <= pos < len(exe) for pos in positions)
            or any(not isinstance(row, dict) for row in parsed)):
        result["state"] = "ponteiros_ou_registros_invalidos"
        return result
    result["distinctPointers"] = len(set(positions))
    hist = Counter()
    for pos, record in zip(positions, parsed):
        span = record.get("spanBytes")
        if type(span) is not int or span <= 0:
            result["interleavedOrTruncated"] += 1
            continue
        start = pos + (3 if record.get("headerPresent") is True else 0)
        end = min(len(exe), pos + min(span, MAX_RECORD_BYTES))
        if not pos <= start < end:
            result["interleavedOrTruncated"] += 1
            continue
        if record.get("boundaryKnown") is True and record.get("boundaryReached") is not True:
            result["interleavedOrTruncated"] += 1
        raw = exe[start:end]
        result["recordsExamined"] += 1
        ff = raw.find(b"\xff")
        fd = raw.find(b"\xfd")
        invalid = record.get("firstInvalidOffset")
        if ff >= 0:
            result["ffPresent"] += 1
            if any(byte != 0 for byte in raw[ff + 1:]):
                result["nonZeroAfterFf"] += 1
            if type(invalid) is int and invalid < ff:
                result["ffAfterFirstInvalid"] += 1
        if fd >= 0:
            result["fdPresent"] += 1
            if ff >= 0 and fd < ff:
                result["fdBeforeFf"] += 1
            elif ff < 0:
                result["fdWithoutFf"] += 1
            if fd == len(raw) - 1:
                result["fdAtRecordEnd"] += 1
            else:
                after = raw[fd + 1]
                if after == 0:
                    result["fdFollowedByZero"] += 1
                elif after < len(glyphs) and glyphs[after]:
                    result["fdFollowedByGlyph"] += 1
                else:
                    result["fdFollowedByControl"] += 1
            if any(b not in (0, 0xff) for b in raw[fd + 1:]):
                result["nonZeroAfterFd"] += 1
            if ff > fd and any(
                b < len(glyphs) and bool(glyphs[b])
                for b in raw[fd + 1:ff]):
                result["fdWithGlyphBeforeFf"] += 1
        # Histogram known control range, not raw text or byte sequences.
        for byte in raw:
            if 0xF0 <= byte <= 0xFE:
                hist[f"0x{byte:02X}"] += 1
    result["nonFfControlHistogram"] = dict(hist.most_common(10))
    if result["recordsExamined"] != OPP_COUNT:
        result["state"] = "registros_parciais"
    elif result["fdPresent"] and result["ffPresent"]:
        result["state"] = "controles_mistos_necessitam_validacao"
    elif result["fdPresent"]:
        result["state"] = "fd_sem_terminador_comprovado"
    elif result["ffPresent"]:
        result["state"] = "ff_observado_nao_comprova_ids"
    else:
        result["state"] = "terminadores_desconhecidos"
    return result


def inspect_control_windows(
        exe: bytes, *, hypotheses: list, records: dict,
        pointers: dict, text_base: int, glyph_base: int) -> dict:
    result = {"schema": 1, "state": "sem_janelas",
              "windows": [], "validated": False, "inGameVerified": False,
              "mayPromote": False}
    if not isinstance(hypotheses, list):
        return result
    for row in hypotheses:
        if len(result["windows"]) >= MAX_WINDOWS:
            break
        start = row.get("startIndex") if isinstance(row, dict) else None
        if type(start) is not int:
            continue
        inspected = audit_control_window(
            exe, start_index=start, records=records, pointers=pointers,
            text_base=text_base, glyph_base=glyph_base)
        result["windows"].append(inspected)
    if result["windows"]:
        result["state"] = "janelas_auditadas"
    return result
