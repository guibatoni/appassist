"""Auditoria conservadora de previsões de RANK contra duelos informados manualmente.

Não lê a RAM, não identifica a ISO carregada no emulador e NÃO habilita
bindings. Uma previsão "se vencer por LP" só pode ser comparada com
um relato de vitória por LP da mesma ISO registrada.
"""
from __future__ import annotations

import re

from dueltrace_rank_system import (
    available_ranks, rank_label_for_existing_score, rank_system,
)

MAX_DUELS = 500
MAX_DETAILS = 50
DUEL_ID = re.compile(r"[A-Za-z0-9_-]{8,100}\Z")

MATCHES = frozenset({"match"})
MISMATCHES = frozenset({
    "score_mismatch", "rank_mismatch", "score_and_rank_mismatch"
})
INVALID = frozenset({
    "invalid_observation", "observed_result_conflict",
    "invalid_snapshot", "duplicate_duel"
})


def compare_rank_observations(rom_sha256: str, observations: list) -> dict:
    """Compara relatos com snapshots, sem converter correlação em prova MIPS.

    O score numérico e a fórmula de pontuação NÃO são recalculados.
    Um resultado observado sem pontuação permite apenas checar a letra;
    deck-out/condições desconhecidas nunca validam projeção por LP.
    """
    if (type(rom_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", rom_sha256) is None):
        raise ValueError("SHA-256 da ISO inválido.")
    if not isinstance(observations, list):
        raise ValueError("Lista de duelos inválida.")

    ranks = available_ranks(rom_sha256)
    cases = []
    seen = set()
    for row in observations[-MAX_DUELS:]:
        if not isinstance(row, dict) or row.get("rom_sha256") != rom_sha256:
            continue
        duel_id = row.get("duel_id")
        safe_id = duel_id if type(duel_id) is str and DUEL_ID.fullmatch(duel_id) else None
        observed_rank = row.get("observed_rank")
        observed_points = row.get("observed_points")
        victory = row.get("victory_type")
        snap = row.get("rank_snapshot")
        case = {
            "duel_id": safe_id,
            "status": "invalid_observation",
            "observed_rank": observed_rank if type(observed_rank) is str and observed_rank in ranks else None,
            "observed_points": observed_points if type(observed_points) is int and 0 <= observed_points <= 300 else None,
            "projected_rank": None,
            "projected_score": None,
            "score_delta": None,
        }

        if safe_id is None:
            pass
        elif safe_id in seen:
            case["status"] = "duplicate_duel"
        elif (row.get("source") not in (None, "manual_game_observation")
              or type(observed_rank) is not str or observed_rank not in ranks
              or (observed_points is not None and
                  (type(observed_points) is not int or not 0 <= observed_points <= 300))
              or victory not in ("lp", "deckout", "other", "unknown")):
            pass
        elif (observed_points is not None and
              rank_label_for_existing_score(rom_sha256, observed_points) != observed_rank):
            case["status"] = "observed_result_conflict"
        elif victory != "lp":
            case["status"] = "not_lp_win"
        elif snap is None:
            case["status"] = "missing_prediction"
        elif (not isinstance(snap, dict)
              or snap.get("comparison_status") not in (None, "projection_not_final")
              or type(snap.get("projected_score")) is not int
              or not -10000 <= snap["projected_score"] <= 10000
              or type(snap.get("projected_rank")) is not str):
            case["status"] = "invalid_snapshot"
        else:
            score = snap["projected_score"]
            label = snap["projected_rank"]
            if rank_label_for_existing_score(rom_sha256, score) != label:
                case["status"] = "invalid_snapshot"
            else:
                case["projected_score"] = score
                case["projected_rank"] = label
                if observed_points is None:
                    case["status"] = ("rank_only_match" if label == observed_rank
                                      else "rank_only_mismatch")
                else:
                    same_score = score == observed_points
                    same_label = label == observed_rank
                    case["score_delta"] = observed_points - score
                    case["status"] = (
                        "match" if same_score and same_label else
                        "score_mismatch" if not same_score and same_label else
                        "rank_mismatch" if same_score and not same_label else
                        "score_and_rank_mismatch"
                    )
        if safe_id is not None:
            seen.add(safe_id)
        cases.append(case)

    total = len(cases)
    matches = sum(x["status"] in MATCHES for x in cases)
    mismatches = sum(x["status"] in MISMATCHES for x in cases)
    rank_only_matches = sum(x["status"] == "rank_only_match" for x in cases)
    rank_only_mismatches = sum(x["status"] == "rank_only_mismatch" for x in cases)
    invalid = sum(x["status"] in INVALID for x in cases)
    missing = sum(x["status"] == "missing_prediction" for x in cases)
    not_lp = sum(x["status"] == "not_lp_win" for x in cases)
    status = (
        "no_duels" if total == 0 else
        "differences_reported" if mismatches or rank_only_mismatches or invalid else
        "manual_matches_only" if matches or rank_only_matches else
        "insufficient_comparable_evidence"
    )
    return {
        "schema": "DUELTRACE-RANK-COMPARISON-1",
        "rom_sha256": rom_sha256,
        "rank_system": rank_system(rom_sha256),
        "status": status,
        "total": total,
        "fully_comparable": matches + mismatches,
        "matches": matches,
        "mismatches": mismatches,
        "rank_only_matches": rank_only_matches,
        "rank_only_mismatches": rank_only_mismatches,
        "invalid": invalid,
        "missing_prediction": missing,
        "not_lp_win": not_lp,
        "cases": cases[-MAX_DETAILS:],
        "runtime_verified": False,
        "rank_routine_confirmed": False,
        "binding_unlocked": False,
        "note": (
            "Comparacao offline de relatos manuais com previsoes provisórias. "
            "Nao confirma ISO em execucao, origem dos pontos, RAM, MIPS ou "
            "causalidade; nao habilita projecoes para mods sem binding validado."
        ),
    }
