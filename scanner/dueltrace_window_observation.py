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


def _explore_unmapped_physical_blocks(blob: bytes, clusters: list,
                                      parsed: list[dict]) -> dict:
    """Read-only exploration: independent of the 39-name pointer-table order.

    A structural name position is *not* used to select physical block here.
    Every valid physical block from the same recognised cluster is checked.
    No candidate is labelled with an in-game opponent ID.
    """
    result = {
        "status": "hypotheses_only",
        "nameToBlockMappingVerified": False,
        "rankGroupsVerified": False,
        "mayActivateDrops": False,
        "mayActivateRank": False,
        "slots": [],
    }
    by_slot = defaultdict(list)
    for row in parsed:
        by_slot[row["slot"]].append(row)
    if not by_slot:
        return result

    if not isinstance(clusters, list) or len(clusters) > 8:
        result["status"] = "unusable_cluster_data"
        return result

    for slot in sorted(by_slot):
        candidates = []
        scanned = 0
        for cluster_index, cluster in enumerate(clusters):
            if not isinstance(cluster, dict):
                result["status"] = "unusable_cluster_data"
                return result
            first = cluster.get("firstBlockOffset")
            count = cluster.get("consecutiveBlockCount")
            step = cluster.get("opponentStep")
            stride = cluster.get("matrixStride")
            codec = cluster.get("encoding")
            if (not all(type(z) is int for z in (first, count, step, stride))
                    or first < 0 or first % 2
                    or not OPPONENT_COUNT <= count <= 128
                    or step % 2 or stride % 2 or stride < MATRIX_BYTES
                    or step < 3 * stride + MATRIX_BYTES
                    or codec not in CODECS
                    or first + (count - 1) * step + 3 * stride
                    + MATRIX_BYTES > len(blob)):
                result["status"] = "unusable_cluster_data"
                return result
            for physical_index in range(count):
                scanned += 1
                offset = first + physical_index * step
                codec_for = lambda g: (
                    "plain" if g == 0 else "x15_masked"
                ) if codec == "plain_deck_masked_drops" else codec
                deck = decode_matrix(blob, offset, codec_for(0))
                groups = [
                    decode_matrix(blob, offset + g * stride, codec_for(g))
                    for g in range(1, 4)
                ]
                if deck is None or any(g is None for g in groups):
                    continue
                if any(deck[cid - 1] == 0
                       for obs in by_slot[slot] for cid in obs["played"]):
                    continue
                masks_by_rank = defaultdict(lambda: 0b111)
                matches = True
                for obs in by_slot[slot]:
                    mask = sum(1 << g for g, weights in enumerate(groups)
                               if weights[obs["reward"] - 1] > 0)
                    if mask == 0:
                        matches = False
                        break
                    masks_by_rank[obs["rank"]] &= mask
                    if masks_by_rank[obs["rank"]] == 0:
                        matches = False
                        break
                if matches:
                    candidates.append({
                        "clusterIndex": cluster_index,
                        "physicalBlockIndex": physical_index,
                    })
        result["slots"].append({
            "structuralNamePosition": slot,
            "physicalBlocksExamined": scanned,
            "possiblePhysicalBlocks": len(candidates),
            "candidateSamples": candidates[:12],
            "mayActivateDrops": False,
            "inGameIdVerified": False,
        })
    return result


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

    result["unmappedPhysicalBlocks"] = _explore_unmapped_physical_blocks(
        blob, family.get("clusters"), parsed)

    for index, window in enumerate(windows):
        group_codec = lambda group: (
            "plain" if group == 0 else "x15_masked"
        ) if window["codec"] == "plain_deck_masked_drops" else window["codec"]
        deck_misses = 0
        reward_misses = 0
        masks_by_rank: dict[str, int] = defaultdict(lambda: 0b111)
        unassessable_ranks = set()
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
                unassessable_ranks.add(row["rank"])
            else:
                masks_by_rank[row["rank"]] &= possible
        if not valid:
            result["status"] = "unusable_family_layout"
            result["windows"] = []
            return result
        # A missing reward gives no evidence about WHICH RANK group it
        # belongs to. Counting that as a second independent conflict was
        # misleading in the GOG screenshot.
        conflicting_ranks = sum(
            mask == 0 for rank, mask in masks_by_rank.items()
            if rank not in unassessable_ranks)
        compatible = (deck_misses == 0 and reward_misses == 0
                      and conflicting_ranks == 0)
        result["windows"].append({
            "index": index,
            "baseOffset": window["base"],
            "deckContradictions": deck_misses,
            "rewardContradictions": reward_misses,
            "sameRankGroupConflicts": conflicting_ranks,
            "rankGroupNotAssessable": len(unassessable_ranks),
            "compatibleUnderHypothesis": compatible,
            "candidateGroupsPerObservedRank": {
                rank: ([] if rank in unassessable_ranks else
                       [g + 1 for g in range(3) if mask & (1 << g)])
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
