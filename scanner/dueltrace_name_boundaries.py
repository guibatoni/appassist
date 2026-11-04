"""Diagnóstico limitado dos limites dos nomes de oponentes no SLUS.

Se os nomes de cartas passam no layout antigo, mas todos os nomes de
oponentes falham, investigue um delimitador/código de controle diferente
ANTES de presumir que a tabela de ponteiros foi relocada.

É investigação, NÃO uma nova rotina de extração aprovada.
Nenhum dado é escrito de volta na imagem de jogo ou nos catálogos.
"""
from __future__ import annotations

from collections import Counter
import struct
import unicodedata

OPP_COUNT = 39
SAMPLE_IDS = (1, 2, 3, 10, 20, 30, 39)
MAX_NAME_BYTES = 128


def inspect_opponent_name_boundaries(
        sl: bytes, *, pointer_base: int, text_base: int,
        glyph_base: int, pointer_index: int = 0x328) -> dict:
    """Inspeciona segmentos até o ponteiro do próximo nome.

    Testa se 0xFF realmente aparece antes do próximo nome. Se o texto
    reconhecido preceder um código estranho, registra o primeiro byte
    ilegível. Não remove sufixos nem substitui caracteres no catálogo.
    """
    limit = max(glyph_base + 93 * 4,
                pointer_base + (pointer_index + OPP_COUNT + 1) * 2)
    if len(sl) < limit:
        return {
            "state": "executavel_incompleto", "samples": [],
            "hasFFBeforeNext": 0, "noFFBeforeNext": 0,
            "commonEndByte": None, "commonEndByteCount": 0,
            "validated": False,
        }
    try:
        codepoints = [struct.unpack_from("<H", sl, glyph_base + i * 4)[0]
                      for i in range(93)]
    except struct.error:
        return {"state": "glifos_indisponiveis", "samples": [],
                "validated": False}

    chars = []
    for value in codepoints:
        if not value:
            chars.append("")
        else:
            try:
                chars.append(value.to_bytes(2, "big").decode("shift_jis"))
            except UnicodeError:
                chars.append("")

    all_rows = []
    last_bytes = []
    first_invalid_bytes = []
    has_ff = 0
    no_ff = 0
    for number in range(1, OPP_COUNT + 1):
        index = pointer_index + number
        ptr = struct.unpack_from("<H", sl, pointer_base + index * 2)[0]
        pos = text_base + ptr
        if not (0 <= pos < len(sl)):
            continue
        starts_with_header = sl[pos:pos + 2] == b"\xf8\x0a"
        payload_start = pos + (3 if starts_with_header else 0)
        next_pos = None
        if number < OPP_COUNT:
            next_ptr = struct.unpack_from(
                "<H", sl, pointer_base + (index + 1) * 2)[0]
            candidate = text_base + next_ptr
            if pos < candidate <= len(sl) and candidate - pos <= MAX_NAME_BYTES:
                next_pos = candidate
        if next_pos is None:
            # Último registro: não inferir limite a partir de outro layout.
            sample = sl[payload_start:payload_start + MAX_NAME_BYTES]
        else:
            sample = sl[payload_start:next_pos]
        if not sample:
            continue

        found_ff = b"\xff" in sample
        if number < OPP_COUNT and next_pos is not None:
            if found_ff:
                has_ff += 1
            else:
                no_ff += 1
            last_bytes.append(sample[-1])

        decoded = []
        first_invalid = None
        terminator_offset = None
        for i, raw_byte in enumerate(sample):
            if raw_byte == 0xff:
                terminator_offset = i
                break
            if raw_byte == 0:
                decoded.append(" ")
            elif raw_byte < len(chars) and chars[raw_byte]:
                decoded.append(chars[raw_byte])
            else:
                first_invalid = (i, raw_byte)
                break
        if first_invalid:
            first_invalid_bytes.append(first_invalid[1])
        readable_prefix = unicodedata.normalize(
            "NFKC", "".join(decoded)).strip()[:70]
        all_rows.append({
            "id": number,
            "pointer": ptr,
            "nextPointerDelta": next_pos - pos if next_pos is not None else None,
            "headerPresent": starts_with_header,
            "hasFFBeforeNext": found_ff if next_pos is not None else None,
            "firstInvalidHex": f"0x{first_invalid[1]:02X}" if first_invalid else None,
            "firstInvalidOffset": first_invalid[0] if first_invalid else None,
            "endByteHex": f"0x{sample[-1]:02X}" if next_pos is not None else None,
            "tailHex": sample[-min(8, len(sample)):].hex(" ").upper(),
            "readablePrefix": readable_prefix,
            "validated": False,
        })

    common = Counter(last_bytes).most_common(1)
    common_byte, common_count = common[0] if common else (None, 0)
    invalid_common = Counter(first_invalid_bytes).most_common(1)
    invalid_byte, invalid_count = (
        invalid_common[0] if invalid_common else (None, 0))
    return {
        "state": "limites_nao_validados",
        "examined": len(all_rows),
        "hasFFBeforeNext": has_ff,
        "noFFBeforeNext": no_ff,
        "commonEndByte": (
            f"0x{common_byte:02X}" if common_byte is not None else None),
        "commonEndByteCount": common_count,
        "commonFirstInvalidByte": (
            f"0x{invalid_byte:02X}" if invalid_byte is not None else None),
        "commonFirstInvalidCount": invalid_count,
        "samples": [next(
            (row for row in all_rows if row["id"] == i), None)
            for i in SAMPLE_IDS
            if any(row["id"] == i for row in all_rows)],
        "note": "Inspeção de bytes e limites para revisão; não remove sufixos nem valida IDs.",
        "validated": False,
    }
