"""Análise exploratória de ocupação do campo, SOMENTE LEITURA.

Não identifica cartas no campo: apenas cruza transições de bytes entre
slot visualmente vazio, ocupado e removido, com controles opcionais.
Nunca exporta blocos brutos da RAM, nem valida endereços automaticamente.
"""
from __future__ import annotations

CHUNK_SIZE = 4096
HAND_START = 0xBFF484
HAND_END = HAND_START + 140
HYPOTHESIS_BASE = 0xBFF504
HYPOTHESIS_STRIDE = 28
MAX_RESULTS = 100


def _raw_at(chunks: dict[int, bytes] | None, address: int):
    if chunks is None:
        return None
    base = address & ~(CHUNK_SIZE - 1)
    part = chunks.get(base)
    idx = address - base
    if not isinstance(part, bytes) or len(part) != CHUNK_SIZE:
        return None
    return part[idx]


def _hypothetical_record(address: int, slot: int | None):
    if type(slot) is not int or not 1 <= slot <= 5:
        return False
    base = HYPOTHESIS_BASE + (slot - 1) * HYPOTHESIS_STRIDE
    return base <= address < base + HYPOTHESIS_STRIDE


def analyze_occupancy(
    before: dict[int, bytes], occupied: dict[int, bytes],
    removed: dict[int, bytes] | None,
    *, observed_slot: int | None,
    prepared: dict[int, bytes] | None = None,
    occupied_control: dict[int, bytes] | None = None,
    vacant_control: dict[int, bytes] | None = None,
) -> dict:
    """Seleciona *hipóteses* com transições de volta após remoção.

    Não confundir correlação com causalidade. Só considera endereços que
    mudaram na entrada E na saída. Controles estáveis são opcionais.
    Uma mudança no turno/combate pode gerar falsos positivos.
    """
    if type(observed_slot) is not int or not 1 <= observed_slot <= 5:
        raise ValueError("Informe um slot visual de 1 a 5 antes da análise")
    if vacant_control is not None and removed is None:
        raise ValueError("Controle de mesa vazia requer captura REMOVIDA")
    if removed is None:
        return {
            "status": "AGUARDANDO_REMOCAO",
            "scope": "DIFERENCAS_EXPLO­RATORIAS_DE_BYTES",
            "slot_observado_pelo_usuario": observed_slot,
            "occupied_control_recorded": occupied_control is not None,
            "vacant_control_recorded": False,
            "total_compared_bytes": 0,
            "matched_total": 0,
            "reversible_total": 0,
            "partial_total": 0,
            "candidate_limit": MAX_RESULTS,
            "candidates": [],
            "truncated": False,
            "field_slot_verified": False,
            "occupancy_verified": False,
        }

    count_compared = 0
    matched = 0
    reversible = 0
    partial = 0
    volatile_control = 0
    skipped_prepared_same = 0
    candidates = []

    for base in sorted(set(before) & set(occupied) & set(removed)):
        a, b, c = before[base], occupied[base], removed[base]
        if any(not isinstance(v, bytes) or len(v) != CHUNK_SIZE for v in (a, b, c)):
            continue
        for i in range(CHUNK_SIZE):
            address = base + i
            if HAND_START <= address < HAND_END:
                continue
            count_compared += 1
            empty, onfield, destroyed = a[i], b[i], c[i]
            if empty == onfield or onfield == destroyed:
                continue
            occupied_guard = _raw_at(occupied_control, address)
            empty_guard = _raw_at(vacant_control, address)
            if occupied_control is not None and occupied_guard != onfield:
                volatile_control += 1
                continue
            if vacant_control is not None and empty_guard != destroyed:
                volatile_control += 1
                continue
            pre = _raw_at(prepared, address)
            changed_only_before_set = pre is not None and pre == onfield
            if changed_only_before_set:
                skipped_prepared_same += 1
            reverted = empty == destroyed
            region = _hypothetical_record(address, observed_slot)
            # Priorização, não classificação validada.
            score = (
                (5 if reverted else 1)
                + (3 if region else 0)
                + (2 if prepared is not None and pre == empty else 0)
                + (1 if occupied_control is not None else 0)
                + (1 if vacant_control is not None else 0)
                - (4 if changed_only_before_set else 0)
            )
            row = {
                "address": f"0x{address:08X}",
                "u8_before_empty": empty,
                "u8_after_set": onfield,
                "u8_after_removal": destroyed,
                "u8_prepared": pre,
                "u8_stable_occupied": occupied_guard,
                "u8_stable_empty": empty_guard,
                "returns_to_baseline": reverted,
                "already_changed_during_preparation": changed_only_before_set,
                "near_hypothetical_record_for_reported_slot": region,
                "score_for_review_only": score,
                "field_slot_verified": False,
                "note": "Correlação de bytes; pode refletir turno, efeitos ou animação.",
            }
            matched += 1
            if reverted:
                reversible += 1
            else:
                partial += 1
            # Manter no máximo MAX_RESULTS hipóteses com maior prioridade,
            # sem exportar uma cópia de toda a memória.
            candidates.append(row)
            if len(candidates) > MAX_RESULTS * 4:
                candidates.sort(key=lambda r: (-r["score_for_review_only"], r["address"]))
                del candidates[MAX_RESULTS:]

    candidates.sort(key=lambda r: (-r["score_for_review_only"], r["address"]))
    return {
        "status": "HIPOTESES_PARA_REPETICAO" if matched else "SEM_TRANSICOES_CANDIDATAS",
        "scope": "DIFERENCAS_EXPLORATORIAS_DE_BYTES",
        "slot_observado_pelo_usuario": observed_slot,
        "occupied_control_recorded": occupied_control is not None,
        "vacant_control_recorded": vacant_control is not None,
        "total_compared_bytes": count_compared,
        "matched_total": matched,
        "reversible_total": reversible,
        "partial_total": partial,
        "discarded_due_to_unstable_controls": volatile_control,
        "potentially_preparation_related": skipped_prepared_same,
        "candidate_limit": MAX_RESULTS,
        "candidates": candidates[:MAX_RESULTS],
        "truncated": matched > MAX_RESULTS,
        "field_slot_verified": False,
        "occupancy_verified": False,
        "notes": [
            "Retornar ao valor anterior nao e prova de slot: turno/combate podem coincidir.",
            "Posicao, ocupacao e retirada informadas visualmente pelo jogador.",
            "Sem dump bruto; apenas enderecos e tres valores uint8 de candidatos.",
            "Repita com cartas diferentes, slots diferentes e controles sem acao.",
        ],
    }
