"""Discover 39 independent names using an inline FD u16 FF suffix.

The two-byte field is *not* interpreted as a ROM jump or an opponent ID.
This generic pattern requires a single 39-record run, 39 distinct names and
pointers, a two-byte field equal to base + encoded glyph count for EVERY
record, and FF immediately after it. Never promotes drops, RANK, or fusions.
"""
from __future__ import annotations

import struct
import unicodedata

OPP_COUNT = 39
MAX_NAME_BYTES = 64
MAX_EXE_BYTES = 8 * 1024 * 1024


def _glyphs(exe: bytes, base: int) -> tuple[str, ...] | None:
    if not isinstance(exe, bytes) or base < 0 or base + 93 * 4 > len(exe):
        return None
    chars = []
    try:
        for i in range(93):
            value = struct.unpack_from("<H", exe, base + i * 4)[0]
            chars.append(value.to_bytes(2, "big").decode("shift_jis")
                         if value else " ")
    except (UnicodeError, struct.error):
        return None
    return tuple(chars)


def _record(exe: bytes, start: int, glyphs: tuple[str, ...]):
    if not 0 <= start < len(exe):
        return None
    chars = []
    for count in range(MAX_NAME_BYTES):
        pos = start + count
        if pos + 3 >= len(exe):
            return None
        token = exe[pos]
        if token == 0xFD:
            if count < 3 or count > 60 or exe[pos + 3] != 0xFF:
                return None
            name = unicodedata.normalize("NFKC", "".join(chars)).strip()
            if (not 3 <= len(name) <= 60
                    or sum(ch.isalnum() for ch in name) < 3
                    or not any(ch.isalpha() for ch in name)
                    or any(ord(ch) < 32 for ch in name)):
                return None
            field = struct.unpack_from("<H", exe, pos + 1)[0]
            base = field - count
            return (name, base) if base >= 0 else None
        if token >= len(glyphs) or not glyphs[token]:
            return None
        chars.append(glyphs[token])
    return None


def probe_inline_fd_names(
        exe: bytes, *, pointer_base: int, text_base: int,
        glyph_base: int, start_min: int = 723,
        start_max: int = 1152) -> dict:
    """Find *unique* structural candidate; never assume its in-game IDs."""
    report = {"schema": 1, "state": "nao_encontrado",
              "candidateCount": 0, "selected": None, "candidates": [],
              "validated": False, "inGameVerified": False,
              "mayActivate": False}
    if (not isinstance(exe, bytes) or len(exe) > MAX_EXE_BYTES
            or not all(type(x) is int and x >= 0 for x in
                       (pointer_base, text_base, glyph_base,
                        start_min, start_max))
            or start_max < start_min or start_max - start_min > 2000
            or pointer_base + (start_max + OPP_COUNT) * 2 > len(exe)):
        report["state"] = "entrada_invalida"
        return report
    glyphs = _glyphs(exe, glyph_base)
    if glyphs is None:
        report["state"] = "glifos_invalidos"
        return report
    cache = {}
    for i in range(start_min, start_max + OPP_COUNT):
        pointer = struct.unpack_from("<H", exe, pointer_base + 2 * i)[0]
        cache[i] = (pointer, _record(exe, text_base + pointer, glyphs))
    for start in range(start_min, start_max + 1):
        rows = [cache[i] for i in range(start, start + OPP_COUNT)]
        if any(record is None for _, record in rows):
            continue
        if len({pointer for pointer, _ in rows}) != OPP_COUNT:
            continue
        fields = {record[1] for _, record in rows}
        names = [record[0] for _, record in rows]
        if len(fields) != 1 or len(set(names)) != OPP_COUNT:
            continue
        entry = {"startIndex": start, "count": OPP_COUNT,
                 "sharedFieldBase": fields.pop(),
                 "allHaveFDSuffix": True, "allHaveFFAfterSuffix": True,
                 "distinctPointers": OPP_COUNT, "distinctNames": OPP_COUNT,
                 "validated": False, "inGameVerified": False}
        report["candidates"].append(entry)
        if len(report["candidates"]) == 1:
            report["selected"] = {
                "startIndex": start, "count": OPP_COUNT,
                "opponents": [{"id": index + 1, "nome": label}
                              for index, label in enumerate(names)],
                "evidence": "fd_len_affine_39_distinct_ending_ff",
                "validated": False, "inGameVerified": False}
    report["candidateCount"] = len(report["candidates"])
    if len(report["candidates"]) == 1:
        report["state"] = "layout_fd_inline_unico_estrutural"
    elif report["candidates"]:
        report["state"] = "layouts_fd_inline_ambiguos"
        report["selected"] = None
    return report
