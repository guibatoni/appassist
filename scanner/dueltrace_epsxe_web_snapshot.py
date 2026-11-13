"""Allowlisted ePSXe duel snapshot for a future browser API.

This file contains NO HTTP server, client, ports, background tasks or
telemetry. It only converts already-validated DUELTRACE Windows results
into a minimal, read-only JSON-compatible data contract.

The browser must not receive RAM, process handles, addresses, ISO paths,
deck files, machine identifiers, ePSXe settings or an implied ROM match.
"""
from __future__ import annotations

import re

_ALLOWED_RANK = re.compile(r"^[A-Z0-9-]{1,16}$")


def make_web_snapshot(hand: dict, rank: dict | None=None, *, sequence: int=0) -> dict:
    if type(sequence) is not int or sequence<0 or sequence>2**53-1:
        raise ValueError("Sequência de evento inválida.")
    if not isinstance(hand,dict):
        raise TypeError("Resultado de mão inválido.")
    cards=hand.get("hand")
    ready=hand.get("ready") is True
    ids=[]
    if ready and isinstance(cards,list) and len(cards)==5:
        for item in cards:
            if not isinstance(item,dict) or type(item.get("id")) is not int:
                ids=[];break
            value=item["id"]
            if not 1<=value<=722:
                ids=[];break
            ids.append(value)
    # A single stale/partial hand must never turn into a live claim.
    hand_ready=len(ids)==5
    state=rank if isinstance(rank,dict) else {}
    rank_ready=state.get("ready") is True
    score=state.get("score")
    category=state.get("category")
    if (type(score) is not int or not -500<=score<=500
            or type(category) is not str or not _ALLOWED_RANK.fullmatch(category)):
        rank_ready=False
    return {
        "schema":1,
        "type":"dueltrace.epsxe.duel.snapshot",
        "emulator":"epsxe",
        "sequence":sequence,
        "hand":{"ready":hand_ready,"cardIds":ids if hand_ready else []},
        "rank":{
            "ready":rank_ready,
            "score":score if rank_ready else None,
            "category":category if rank_ready else None,
            "provisional":not (rank_ready and state.get("final") is True),
        },
        # The user-selected ISO and the ePSXe-loaded ISO are NOT verified to
        # be the same by the existing RAM reader. Never infer identity.
        "runningIsoConfirmed":False,
    }
