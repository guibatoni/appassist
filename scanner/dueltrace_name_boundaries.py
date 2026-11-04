"""Inspeção limitada de strings por glifos e ponteiros do executável PS1.

Os bytes são índices na tabela de glifos; não são strings Shift-JIS diretas.
Somente o terminador 0xFF do layout conhecido é interpretado. Outros bytes
e o último glifo legível são evidências, nunca correções automáticas.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter
import struct
import unicodedata

OPP_COUNT = 39
SAMPLE_IDS = (1, 2, 3, 10, 20, 30, 39)
MAX_NAME_BYTES = 128


def read_glyphs(sl: bytes, glyph_base: int) -> tuple[str, ...]:
    """Decodifica entradas individuais, sem deslocar índices inválidos."""
    if glyph_base < 0 or glyph_base + 93 * 4 > len(sl):
        raise ValueError("Tabela de glifos fora do executável")
    chars = []
    for i in range(93):
        value = struct.unpack_from("<H", sl, glyph_base + i * 4)[0]
        try:
            chars.append(value.to_bytes(2, "big").decode("shift_jis") if value else "")
        except UnicodeError:
            chars.append("")
    return tuple(chars)


def read_name_record(sl: bytes, *, position: int, glyphs: tuple[str, ...],
                     next_position: int | None = None,
                     max_bytes: int = MAX_NAME_BYTES) -> dict:
    """Lê sem consumir o texto do próximo ponteiro físico.

    Sem próximo ponteiro, limita-se ao arquivo e ao orçamento. Um prefixo
    legível não equivale a uma string terminada.
    """
    budget = max(0, min(int(max_bytes), 150))
    empty = {"readablePrefix": "", "recordStatus": "texto_fora_do_arquivo",
             "headerPresent": False, "headerHex": None, "bytesExamined": 0,
             "hasFF": False, "terminatorOffset": None,
             "ffBytePresent": False, "firstFFOffset": None,
             "boundaryKnown": False, "boundaryReached": False,
             "ambiguousBoundary": False,
             "spanBytes": 0,
             "firstInvalidHex": None, "firstInvalidOffset": None,
             "lastGlyphHex": None, "lastGlyph": None, "tailHex": "",
             "validated": False}
    if not 0 <= position < len(sl):
        return empty
    boundary = next_position if next_position is not None and position < next_position <= len(sl) else None
    end = min(len(sl), position + budget, boundary if boundary is not None else len(sl))
    header = sl[position:min(position + 2, end)] == b"\xf8\x0a"
    payload_start = position + (3 if header else 0)
    result = dict(empty, headerPresent=header,
                  headerHex=sl[position:min(position + 3, end)].hex(" ").upper() if header else None,
                  boundaryKnown=boundary is not None,
                  boundaryReached=boundary is not None and end == boundary,
                  spanBytes=end-position)
    if payload_start > end:
        result["recordStatus"] = "cabecalho_incompleto"
        return result
    raw = sl[payload_start:end]
    first_ff = raw.find(b"\xff")
    result.update(ffBytePresent=first_ff >= 0,
                  firstFFOffset=first_ff if first_ff >= 0 else None)
    decoded = []
    last_glyph = None
    for offset, value in enumerate(raw):
        result["bytesExamined"] = offset + 1
        if value == 0xFF:
            result.update(hasFF=True, terminatorOffset=offset,
                          recordStatus="ff_encontrado")
            break
        if value == 0:
            decoded.append(" ")
        elif value < len(glyphs) and glyphs[value]:
            decoded.append(glyphs[value])
            last_glyph = (value, glyphs[value])
        else:
            result.update(firstInvalidHex=f"0x{value:02X}",
                          firstInvalidOffset=offset, recordStatus="glifo_invalido")
            break
    else:
        result["recordStatus"] = (
            "sem_ff_antes_proximo" if boundary is not None and end == boundary else
            "fim_arquivo_sem_ff" if end == len(sl) else "limite_leitura_sem_ff")
    result["readablePrefix"] = unicodedata.normalize("NFKC", "".join(decoded)).strip()[:150]
    # Pode ser corrupção, outra codificação ou compartilhamento de sufixos.
    # Um FF de outra entrada não comprova qual dessas explicações é correta.
    result["ambiguousBoundary"] = result["recordStatus"] == "sem_ff_antes_proximo"
    result["tailHex"] = raw[-min(8, len(raw)):].hex(" ").upper()
    if last_glyph is not None:
        result["lastGlyphHex"] = f"0x{last_glyph[0]:02X}"
        result["lastGlyph"] = unicodedata.normalize("NFKC", last_glyph[1])
    return result


def read_name_table(sl: bytes, *, pointer_base: int, text_base: int,
                    glyph_base: int, indices: tuple[int, ...],
                    max_bytes: int = 150) -> dict[int, dict]:
    """Decodifica uma tabela finita, usando o próximo início físico conhecido.

    Ponteiros fora de ordem e aliases não autorizam uma string a consumir
    outro registro. Um alias também não comprova identidade entre IDs.
    """
    if min(pointer_base, text_base) < 0 or len(indices) > 2048:
        raise ValueError("Layout de nomes fora do orçamento")
    glyphs = read_glyphs(sl, glyph_base)
    positions = {}
    for index in indices:
        address = pointer_base + index * 2
        if index < 0 or address + 2 > len(sl):
            raise ValueError("Tabela de ponteiros fora do executável")
        positions[index] = text_base + struct.unpack_from("<H", sl, address)[0]
    physical = sorted(set(pos for pos in positions.values() if 0 <= pos < len(sl)))
    records = {}
    for index, pos in positions.items():
        following = bisect_right(physical, pos)
        boundary = physical[following] if following < len(physical) else None
        records[index] = read_name_record(sl, position=pos, glyphs=glyphs,
                                          next_position=boundary, max_bytes=max_bytes)
    return records


def inspect_opponent_name_boundaries(
        sl: bytes, *, pointer_base: int, text_base: int,
        glyph_base: int, pointer_index: int = 0x328) -> dict:
    """Audita os 39 registros e mantém sete amostras para a UI.

    O relatório local preserva cada registro, incluindo o 39º, para comparar
    com o jogo. Nenhum terminador alternativo é promovido por frequência.
    """
    limit = max(glyph_base + 93 * 4,
                pointer_base + (pointer_index + OPP_COUNT + 1) * 2)
    if min(pointer_base, text_base, glyph_base, pointer_index) < 0 or len(sl) < limit:
        return {"state": "executavel_incompleto", "samples": [], "records": [],
                "hasFFBeforeNext": 0, "noFFBeforeNext": 0,
                "commonEndByte": None, "commonEndByteCount": 0,
                "validated": False}
    glyphs = read_glyphs(sl, glyph_base)
    pointers = [struct.unpack_from("<H", sl, pointer_base + (pointer_index + number) * 2)[0]
                for number in range(1, OPP_COUNT + 1)]
    positions = [text_base + ptr for ptr in pointers]
    valid_positions = sorted(set(pos for pos in positions if 0 <= pos < len(sl)))
    multiplicities = Counter(positions)
    rows = []
    last_bytes = []
    first_invalid_bytes = []
    has_ff = no_ff = bounded = 0
    for number, (ptr, pos) in enumerate(zip(pointers, positions), 1):
        ordinal_next = positions[number] if number < OPP_COUNT else None
        following = bisect_right(valid_positions, pos)
        physical_next = valid_positions[following] if following < len(valid_positions) else None
        parsed = read_name_record(sl, position=pos, glyphs=glyphs, next_position=physical_next)
        in_bounds = 0 <= pos < len(sl)
        # Só afirmar ausência de FF quando todo o segmento foi inspecionado.
        # Presença de FF após um código inválido não equivale a decodificação.
        if in_bounds and parsed["boundaryReached"]:
            bounded += 1
            has_ff += parsed["ffBytePresent"]
            no_ff += not parsed["ffBytePresent"]
            if physical_next - pos <= MAX_NAME_BYTES:
                last_bytes.append(sl[physical_next - 1])
        if parsed["firstInvalidHex"]:
            first_invalid_bytes.append(parsed["firstInvalidHex"])
        rows.append(dict(parsed, id=number, pointer=ptr,
                         nextPointerDelta=ordinal_next-pos if ordinal_next is not None else None,
                         physicalBoundaryDelta=physical_next-pos if physical_next is not None else None,
                         sharedPointer=multiplicities[pos] > 1,
                         hasFFBeforeNext=parsed["ffBytePresent"] if in_bounds and parsed["boundaryReached"] else None,
                         endByteHex=f"0x{sl[physical_next - 1]:02X}" if in_bounds and physical_next is not None and physical_next-pos <= MAX_NAME_BYTES else None))
    common = Counter(last_bytes).most_common(1)
    byte, count = common[0] if common else (None, 0)
    invalid_common = Counter(first_invalid_bytes).most_common(1)
    invalid_byte, invalid_count = invalid_common[0] if invalid_common else (None, 0)
    return {"state": "limites_nao_validados", "examined": sum(0 <= p < len(sl) for p in positions),
            "hasFFBeforeNext": has_ff, "noFFBeforeNext": no_ff,
            "boundedRecords": bounded,
            "terminatedRecords": sum(row["hasFF"] for row in rows),
            "commonEndByte": f"0x{byte:02X}" if byte is not None else None,
            "commonEndByteCount": count,
            "commonFirstInvalidByte": invalid_byte, "commonFirstInvalidCount": invalid_count,
            "pointerAudit": {"outOfFile": sum(not 0 <= p < len(sl) for p in positions),
                             "sharedRecords": sum(multiplicities[p] > 1 for p in positions),
                             "nonIncreasingPairs": sum(b <= a for a, b in zip(positions, positions[1:]))},
            "statusCounts": dict(Counter(row["recordStatus"] for row in rows)),
            "records": rows,
            "samples": [row for row in rows if row["id"] in SAMPLE_IDS],
            "note": "Glifos, ponteiros e limites são evidências; sufixos preservados, IDs não validados.",
            "validated": False}
