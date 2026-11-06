"""Read-only, conservative consistency review for sanitized Live Diagnostics.

This intentionally does NOT verify opponent identity, LP semantics, duel
boundaries, rewards, RANK groups, or fusion recipes. It emits aggregate
numbers only, for human review of what the existing probe actually recorded.
"""
from __future__ import annotations


def _valid_id(value, upper):
    return type(value) is int and 0 <= value <= upper


def _hand(value):
    if not isinstance(value, dict) or value.get("ready") is not True:
        return None
    ids = value.get("ids")
    if (not isinstance(ids, list) or len(ids) != 5
            or any(type(n) is not int or not 1 <= n <= 722 for n in ids)):
        return None
    return tuple(ids)


def _legacy_lp_fields(value):
    if not isinstance(value, dict) or value.get("ready") is not True:
        return None
    p, o = value.get("lpPlayer"), value.get("lpOpponent")
    if (type(p) is not int or type(o) is not int
            or not 1 <= p <= 32767 or not 1 <= o <= 32767):
        return None
    return (p, o)


def summarize_live_report(report: dict | None) -> dict:
    """Describe changes only; no causal claims about the GOG executable.

    LP fields come from legacy offsets. Their values may not be actual LP
    in a mod. A stable candidate ID can be an unrelated constant field.
    """
    empty = {
        "available": False,
        "eventCountExamined": 0,
        "distinctHands": 0,
        "distinctLegacyLpPairs": 0,
        "candidateIds": [],
        "candidateObservedInEvents": 0,
        "candidateStableDespiteHandAndLpFieldChanges": False,
        "rankSnapshotEvents": 0,
        "opponentIdentityVerified": False,
        "legacyLpSemanticsVerified": False,
        "dropMappingVerified": False,
        "fusionRecipesVerified": False,
        "status": "insufficient_observations",
    }
    if not isinstance(report, dict) or report.get("schema") != 1:
        return empty
    events = report.get("events")
    if not isinstance(events, list) or len(events) > 360:
        return empty
    hands, lp_fields, candidates = set(), set(), set()
    candidate_events = 0
    rank_events = 0
    handled = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        data = event.get("data")
        if not isinstance(data, dict):
            continue
        handled += 1
        hand = _hand(data.get("hand"))
        if hand is not None:
            hands.add(hand)
        opponent = data.get("opponent")
        if isinstance(opponent, dict) and opponent.get("ready") is True:
            oid = opponent.get("candidateId")
            if _valid_id(oid, 39):
                candidates.add(oid)
                candidate_events += 1
            pair = _legacy_lp_fields(opponent)
            if pair is not None:
                lp_fields.add(pair)
        rank = data.get("rank")
        if isinstance(rank, dict) and rank.get("ready") is True:
            rank_events += 1
    stable = (candidate_events >= 3 and len(candidates) == 1
              and len(hands) >= 2 and len(lp_fields) >= 2)
    return {
        **empty,
        "available": handled > 0,
        "eventCountExamined": handled,
        "distinctHands": len(hands),
        "distinctLegacyLpPairs": len(lp_fields),
        "candidateIds": sorted(candidates),
        "candidateObservedInEvents": candidate_events,
        "candidateStableDespiteHandAndLpFieldChanges": stable,
        "rankSnapshotEvents": rank_events,
        "status": ("stable_candidate_requires_independent_proof" if stable else
                   "insufficient_observations" if handled < 2 else
                   "observational_only"),
    }
