"""Leitura conservadora de evidências MIPS R3000 no executável PS-X EXE.

Este analisador não emula o SLUS, não executa código do mod e não presume
que uma rotina encontrada calcule o RANK. Identifica pequenos trechos com
operações coerentes com leitura de tabelas, comparação e soma de pontos,
registrando PCs/offsets reproduzíveis para futura inspeção em ePSXe.
"""
from __future__ import annotations

import hashlib
import struct

MAX_EXE_BYTES = 12 * 1024 * 1024
HEADER_BYTES = 0x800
MAX_WINDOWS = 15
WINDOW_INSTRUCTIONS = 56
MIN_SCORE = 8


def _unavailable(reason: str, *, sha256: str | None = None) -> dict:
    return {"status": reason, "available": False,
            "source": "DATA/SLUS_014.11", "exe_sha256": sha256,
            "execution_confirmed": False, "rank_routine_confirmed": False,
            "candidates": [], "candidate_count": 0,
            "note": "A inspeção estática não comprova a execução de uma rotina de RANK."}


def _metrics(words: tuple[int, ...]) -> dict[str, int]:
    counts = {"halfword_loads": 0, "branches": 0, "additions": 0,
              "index_shifts": 0, "constant_highs": 0,
              "immediate_compares": 0, "register_compares": 0}
    bases = set()
    for word in words:
        op = word >> 26
        rs = (word >> 21) & 31
        rt = (word >> 16) & 31
        funct = word & 63
        shift = (word >> 6) & 31
        if op in (0x21, 0x25):   # lh / lhu
            counts["halfword_loads"] += 1
            bases.add(rs)
        elif op in (4,5,6,7):   # beq/bne/blez/bgtz
            counts["branches"] += 1
        elif op == 0 and funct in (0x20,0x21,0x22,0x23):
            counts["additions"] += 1
        elif op in (8,9):      # addi/addiu
            counts["additions"] += 1
        elif op == 0 and funct in (0x2a,0x2b):
            counts["register_compares"] += 1
        elif op in (10,11):    # slti/sltiu
            counts["immediate_compares"] += 1
        elif op == 0 and funct == 0 and shift in (1,2,3,4) and rt:
            counts["index_shifts"] += 1
        elif op == 15 and rt:  # lui
            counts["constant_highs"] += 1
    counts["unique_read_bases"] = len(bases)
    return counts


def _evidence_score(counts: dict[str, int]) -> int:
    # Os padrões isolados aparecem frequentemente em qualquer código MIPS.
    # Exigir várias famílias diferentes reduz falsos candidatos.
    if (counts["halfword_loads"] < 2 or counts["branches"] < 2
            or counts["additions"] < 2
            or not (counts["register_compares"] or counts["immediate_compares"])):
        return 0
    return (min(4, counts["halfword_loads"])*2
            + min(4, counts["branches"])
            + min(4, counts["additions"])
            + min(2, counts["index_shifts"])
            + min(2, counts["constant_highs"])
            + min(2, counts["register_compares"] + counts["immediate_compares"]))


def inspect_mips_rank_routines(exe: bytes, *, max_candidates: int = 6) -> dict:
    """Localiza *candidatos*, nunca comprova que o SLUS usa o RANK do WA."""
    if not isinstance(exe, bytes) or not 0 < len(exe) <= MAX_EXE_BYTES:
        return _unavailable("invalid_executable")
    digest = hashlib.sha256(exe).hexdigest()
    if exe[:8] != b"PS-X EXE" or len(exe) < HEADER_BYTES+64:
        return _unavailable("not_psx_executable", sha256=digest)
    entry, load, length = struct.unpack_from("<III", exe, 0x10)
    if not (0x80000000 <= load < 0x80200000 and length
            and length % 4 == 0 and length <= 2 * 1024 * 1024
            and HEADER_BYTES + length <= len(exe)):
        return _unavailable("invalid_exe_mapping", sha256=digest)
    if not (load <= entry < load + length):
        return _unavailable("invalid_entry_point", sha256=digest)
    code = exe[HEADER_BYTES:HEADER_BYTES + length]
    words = tuple(w[0] for w in struct.iter_unpack("<I", code))
    # Janelas 56 instruções com sobreposição de 50%, limitadas a 6.
    candidates = []
    step = WINDOW_INSTRUCTIONS // 2
    for index in range(0, max(0, len(words) - WINDOW_INSTRUCTIONS + 1), step):
        sample = words[index:index + WINDOW_INSTRUCTIONS]
        features = _metrics(sample)
        score = _evidence_score(features)
        if score < MIN_SCORE:
            continue
        candidates.append({
            "pc": f"0x{load + index * 4:08X}",
            "file_offset": HEADER_BYTES + index * 4,
            "score": score, "features": features,
        })
    candidates.sort(key=lambda x: (-x["score"], x["file_offset"]))
    # Evita várias janelas que retratam a mesma sequência.
    selected = []
    for item in candidates:
        if any(abs(item["file_offset"] - other["file_offset"])
               < (WINDOW_INSTRUCTIONS // 2) * 4 for other in selected):
            continue
        selected.append(item)
        if len(selected) == max(1, min(MAX_WINDOWS, max_candidates)):
            break
    return {
        "status": "mips_patterns_found" if selected else "no_mips_rank_pattern",
        "available": True, "source": "DATA/SLUS_014.11",
        "exe_sha256": digest,
        "entry_pc": f"0x{entry:08X}", "load_address": f"0x{load:08X}",
        "execution_confirmed": False, "rank_routine_confirmed": False,
        "candidates": selected, "candidate_count": len(candidates),
        "note": "Endereços são candidatos heurísticos. Confirmar acesso à tabela "
                "de RANK durante o duelo em um depurador ePSXe/PS1 antes de "
                "atribuir regras ou classe de RANK a este mod.",
    }
