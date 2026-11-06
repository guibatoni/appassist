"""Correlate an observed duel with *unverified* 39-opponent matrix windows.

Pure read-only logic. Input comes from the currently analysed ISO and manually
recorded observations. A result is never a proof of opponent IDs, RANK rules
or the game's choice of a drop table. No gameplay profile is modified.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from dueltrace_mod_family_probe import (
    CARD_COUNT, OPPONENT_COUNT, MATRIX_BYTES, CODECS, decode_matrix,
)

MAX_OBSERVATIONS = 200
MAX_PLAYED_CARDS = 24
MAX_WINDOWS = 16
VALID_STATES = {
    "unique_structural_candidate",
    "single_family_unmapped_windows",
    "ambiguous_candidates",
}


def _empty(state: str) -> dict:
    return {
        "schema": 1,
        "status": state,
        "observationCount": 0,
        "windowCount": 0,
        "compatibleWindowCount": 0,
        "candidateWindowHint": None,
        "windows": [],
        "inGameVerified": False,
        "opponentIdsVerified": False,
        "rankGroupsVerified": False,
        "mayActivateDrops": False,
        "mayActivateRank": False,
        "note": (
            "Correlacao de observacoes declaradas: indices de oponentes, "
            "grupos de RANK e distribuicoes permanecem hipoteses."
        ),
    }


def _parse_observation(row: Any) -> dict | None:
    # Keep the validation explicit: bool is not an integer ID and non-list
    # input may not reach set(). Do not echo submitted values into reports.
    if not isinstance(row, dict) or row.get("source") != "manual_game_observation":
        return None
    slot, reward = row.get("opponent_slot"), row.get("reward_card_id")
    rank, played = row.get("observed_rank"), row.get("played_card_ids", [])
    if (type(slot) is not int or not 1 <= slot <= OPPONENT_COUNT
            or type(reward) is not int or not 1 <= reward <= CARD_COUNT
            or not isinstance(rank, str) or not 1 <= len(rank) <= 24
            or not rank.isascii()
            or not all(ch.isalnum() or ch in "-_" for ch in rank)
            or not isinstance(played, list) or len(played) > MAX_PLAYED_CARDS
            or not all(type(cid) is int and 1 <= cid <= CARD_COUNT
                       for cid in played)
            or len(set(played)) != len(played)):
        return None
    return {"slot": slot, "reward": reward, "rank": rank, "played": tuple(played)}


def _cluster_windows(blob: bytes, clusters: object) -> list[dict] | None:
    if not isinstance(clusters, list) or len(clusters) > 8:
        return None
    windows = []
    seen = set()
    for cluster in clusters:
        if not isinstance(cluster, dict):
            return None
        first = cluster.get("firstBlockOffset")
        count = cluster.get("consecutiveBlockCount")
        step = cluster.get("opponentStep")
        stride = cluster.get("matrixStride")
        codec = cluster.get("encoding")
        if (not all(type(n) is int for n in (first, count, step, stride))
                or first < 0 or first % 2
                or not OPPONENT_COUNT <= count <= 128
                or step % 2 or stride % 2 or stride < MATRIX_BYTES
                or step < stride * 3 + MATRIX_BYTES
                or codec not in CODECS
                or first + (count - 1) * step + 3 * stride + MATRIX_BYTES > len(blob)):
            return None
        for shift in range(count - OPPONENT_COUNT + 1):
            base = first + shift * step
            key = (base, step, stride, codec)
            if key not in seen:
                seen.add(key)
                windows.append({"base": base, "step": step,
                                "stride": stride, "codec": codec})
            if len(windows) > MAX_WINDOWS:
                return None
    return windows


def correlate_observed_duels(blob: bytes, family: dict,
                            observations: list[dict]) -> dict:
    """Test candidate 39-block windows using real, user-reported duel evidence.

    An absent reward from all three candidate groups or an absent played
    card in a candidate deck counts as a contradiction *under that model*.
    RANK labels are never assigned: intersection only finds possible
    structural group numbers for repeated observations with the same label.
    """
    result = _empty("invalid_input")
    if (not isinstance(blob, bytes) or len(blob) > 96 * 1024 * 1024
            or not isinstance(family, dict)
            or family.get("state") not in VALID_STATES
            or family.get("scanComplete") is not True
            or not isinstance(observations, list)
            or len(observations) > MAX_OBSERVATIONS):
        return result
    parsed = [_parse_observation(row) for row in observations]
    if any(row is None for row in parsed):
        result["status"] = "invalid_observation"
        return result
    windows = _cluster_windows(blob, family.get("clusters"))
    if windows is None or not windows:
        result["status"] = "unusable_family_layout"
        return result
    result["windowCount"] = len(windows)
    result["observationCount"] = len(parsed)
    if not parsed:
        result["status"] = "awaiting_independent_duels"
        return result

    for index, window in enumerate(windows):
        group_codec = lambda group: (
            "plain" if group == 0 else "x15_masked"
        ) if window["codec"] == "plain_deck_masked_drops" else window["codec"]
        deck_misses = 0
        reward_misses = 0
        masks_by_rank: dict[str, int] = defaultdict(lambda: 0b111)
        valid = True
        for row in parsed:
            offset = window["base"] + (row["slot"] - 1) * window["step"]
            deck = decode_matrix(blob, offset, group_codec(0))
            groups = [decode_matrix(
                blob, offset + g * window["stride"], group_codec(g))
                for g in range(1, 4)]
            if deck is None or any(weights is None for weights in groups):
                valid = False
                break
            deck_misses += sum(deck[cid - 1] == 0 for cid in row["played"])
            possible = sum(
                (1 << idx) for idx, weights in enumerate(groups)
                if weights[row["reward"] - 1] > 0
            )
            if possible == 0:
                reward_misses += 1
            masks_by_rank[row["rank"]] &= possible
        if not valid:
            result["status"] = "unusable_family_layout"
            result["windows"] = []
            return result
        conflicting_ranks = sum(mask == 0 for mask in masks_by_rank.values())
        compatible = (deck_misses == 0 and reward_misses == 0
                      and conflicting_ranks == 0)
        result["windows"].append({
            "index": index,
            "baseOffset": window["base"],
            "deckContradictions": deck_misses,
            "rewardContradictions": reward_misses,
            "sameRankGroupConflicts": conflicting_ranks,
            "compatibleUnderHypothesis": compatible,
            "candidateGroupsPerObservedRank": {
                rank: [g + 1 for g in range(3) if mask & (1 << g)]
                for rank, mask in sorted(masks_by_rank.items())
            },
            "inGameVerified": False,
            "mayActivateDrops": False,
            "mayActivateRank": False,
        })
    compatible = [row for row in result["windows"]
                  if row["compatibleUnderHypothesis"]]
    result["compatibleWindowCount"] = len(compatible)
    if len(compatible) == 1:
        result["candidateWindowHint"] = compatible[0]["index"]
        result["status"] = "single_window_suggested_not_verified"
    elif compatible:
        result["status"] = "multiple_windows_still_possible"
    else:
        result["status"] = "observations_conflict_with_all_windows"
    return result
