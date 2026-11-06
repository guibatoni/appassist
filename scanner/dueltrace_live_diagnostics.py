"""Opt-in, local-only DUELTRACE live diagnostics: safe event aggregation.

No network, no external uploads, no ROM bytes, no RAM dumps, no host paths,
no process identifiers, no secrets. Snapshots are sanitised through strict
allowlists before recording. Sampling is orchestrated by the desktop bridge.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import threading
from uuid import uuid4
from pathlib import Path

from auto_mods import atomic_json

MAX_EVENTS = 360
MAX_EXPORT_BYTES = 140000
SAFE_SHA = re.compile(r"^[a-f0-9]{64}$")
SAFE_REASON = re.compile(r"^[a-z0-9_]{1,48}$")


def _number(value, low, high):
    return value if type(value) is int and low <= value <= high else None


def _flag(value):
    return value is True


def _enum(value, allowed):
    return value if type(value) is str and value in allowed else "unknown"


OPPONENT_STATES = {
    "runtime_id_candidate", "ram_mapping_not_validated",
    "no_epsxe", "windows_only", "multiple_epsxe_processes",
    "preferred_epsxe_missing", "read_access_denied", "unavailable",
    "activate_mod", "runtime_probe_unavailable", "ambiguous_ram_mapping",
    "invalid_pid", "too_many_candidates", "ready",
}
RANK_STATES = {
    "provisional", "unavailable", "unsupported", "needs_lp_confirmation",
    "auto_calibrating", "needs_ram_validation", "ready", "unknown",
}
MEMORY_FAILURES = (
    "unreadableFields", "opponentIdOutOfRange",
    "implausibleLifePoints", "implausibleHandIndices",
    "implausibleDrawHistory", "unstableSamples",
    "validatedHandAnchors", "validatedSamples",
)


def sanitise_sample(hand, opponent, rank):
    """Strictly project allowed numeric and enum fields; discard everything else."""
    hand = hand if isinstance(hand, dict) else {}
    opponent = opponent if isinstance(opponent, dict) else {}
    rank = rank if isinstance(rank, dict) else {}
    hand_cards = []
    if hand.get("ready") is True and isinstance(hand.get("hand"), list):
        for row in hand["hand"][:6]:
            cid = row.get("id") if isinstance(row, dict) else None
            if _number(cid, 1, 722) is not None:
                hand_cards.append(cid)
    if len(hand_cards) != 5:
        hand_cards = []
    breakdown = opponent.get("validationBreakdown")
    breakdown = breakdown if isinstance(breakdown, dict) else {}
    return {
        "hand": {
            "ready": len(hand_cards) == 5,
            "ids": hand_cards,
        },
        "opponent": {
            "ready": _flag(opponent.get("ready")),
            "status": _enum(opponent.get("status"), OPPONENT_STATES),
            "candidateId": _number(opponent.get("runtimeOpponentId"), 0, 39),
            "mappingMethod": _enum(opponent.get("validationMethod"), {
                "known_hand_anchor", "legacy_draw_history"}),
            "handAnchorValidated": (
                opponent.get("ready") is True
                and opponent.get("validationMethod") == "known_hand_anchor"
            ),
            "lpPlayer": _number(opponent.get("playerLP"), 1, 32767),
            "lpOpponent": _number(opponent.get("opponentLP"), 1, 32767),
            "memoryRegionsExamined": _number(opponent.get("memoryRegionsExamined"), 0, 100000),
            "candidateBasesExamined": _number(opponent.get("candidateBasesExamined"), 0, 1000),
            # Hand-derived host mapping is evidence only, not opponent ID proof.
            "knownHandAnchorAtHint": _flag(opponent.get("knownHandAnchorAtHint")),
            "hintRejectionCounts": {
                key: _number(
                    (opponent.get("hintValidationBreakdown") or {}).get(key),
                    0, 100000) or 0
                for key in MEMORY_FAILURES
            } if isinstance(opponent.get("hintValidationBreakdown"), dict) else {
                key: 0 for key in MEMORY_FAILURES
            },
            "rejectionCounts": {
                key: _number(breakdown.get(key), 0, 100000) or 0
                for key in MEMORY_FAILURES
            },
        },
        "rank": {
            "ready": _flag(rank.get("ready")),
            "state": _enum(rank.get("state"), RANK_STATES),
            "scoreCandidate": _number(rank.get("score"), -1000, 10000)
                              if rank.get("ready") is True else None,
            "categoryCandidate": _enum(rank.get("category"), {
                "S-POW", "A-POW", "B-POW", "C-POW", "D-POW",
                "D-TEC", "C-TEC", "B-TEC", "A-TEC", "S-TEC",
                "Z-POW", "S-TEC", "S-POW", "unknown"}),
            "modelVerified": False,
        },
    }


class LiveDiagnosticsRecorder:
    """A single, explicitly initiated local session for one registered ROM.

    Duplicate identical snapshots are compressed into a sample counter. No
    remote sync, file path or arbitrary user content appears in exports.
    """
    def __init__(self, directory: Path, sha: str):
        if type(sha) is not str or SAFE_SHA.fullmatch(sha) is None:
            raise ValueError("Invalid ROM fingerprint")
        self._directory = Path(directory)
        self._sha = sha
        self._fingerprint = sha[:12]
        # Never overwrite a previous evidence session when the app restarts.
        self._session_id = uuid4().hex[:16]
        self._lock = threading.RLock()
        self._events = []
        self._last = None
        self._samples = 0
        self._running = True
        self._started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._last_observation = None

    @property
    def sha(self):
        return self._sha

    @property
    def session_id(self):
        """Random, path-safe identifier, not a PID or local file path."""
        return self._session_id

    @property
    def running(self):
        with self._lock:
            return self._running

    def stop(self):
        with self._lock:
            self._running = False
            self._persist()

    def observe(self, hand, opponent, rank, sha):
        if sha != self._sha:
            self.stop()
            return False
        sample = sanitise_sample(hand, opponent, rank)
        with self._lock:
            if not self._running:
                return False
            self._samples += 1
            self._last_observation = datetime.now(timezone.utc).isoformat(timespec="seconds")
            if sample != self._last:
                self._last = sample
                self._events.append({
                    "sample": self._samples,
                    "atUTC": self._last_observation,
                    "data": sample,
                })
                self._events = self._events[-MAX_EVENTS:]
                self._persist()
            return True

    def _persist(self):
        self._directory.mkdir(parents=True, exist_ok=True)
        # Full SHA prevents two different ISOs with the same visible prefix
        # from sharing a diagnostics file.
        atomic_json(self._directory / (
            self._sha + "_" + self._session_id + ".json"), self.report())

    def report(self):
        with self._lock:
            changes = self._events
            hand_ok = sum(bool(e["data"]["hand"]["ready"]) for e in changes)
            opponent_ok = sum(bool(e["data"]["opponent"]["ready"]) for e in changes)
            failures = {}
            for event in changes:
                state = event["data"]["opponent"]["status"]
                failures[state] = failures.get(state, 0) + 1
            # Change-events are NOT independent matches to a named ROM
            # opponent. This is a strictly descriptive session summary.
            readable = [
                event["data"]["opponent"] for event in changes
                if event["data"]["opponent"]["ready"]
                and event["data"]["opponent"]["candidateId"] is not None
            ]
            candidates = sorted({event["candidateId"] for event in readable})
            lp_pairs = {
                (event["lpPlayer"], event["lpOpponent"])
                for event in readable
                if event["lpPlayer"] is not None
                and event["lpOpponent"] is not None
            }
            return {
                "schema": 1,
                "subject": "DUELTRACE Live Diagnostics",
                "romFingerprint": self._fingerprint,
                "running": self._running,
                "startedAtUTC": self._started,
                "lastObservedAtUTC": self._last_observation,
                "sampleCount": self._samples,
                "changeCount": len(changes),
                "handReadableChanges": hand_ok,
                "opponentReadableChanges": opponent_ok,
                "opponentStatuses": failures,
                "candidateEvents": len(readable),
                "candidateIdsObserved": candidates,
                "candidateIdStableAcrossReadableChanges": (
                    len(readable) >= 2 and len(candidates) == 1
                ),
                "handAnchorValidatedChanges": sum(
                    bool(item["handAnchorValidated"]) for item in readable
                ),
                "distinctLpPairsInReadableChanges": len(lp_pairs),
                "events": list(changes),
                "verifiedOpponentMapping": False,
                "verifiedRankGroups": False,
                "mayActivateDrops": False,
                "mayActivateRank": False,
                "networkTransmission": False,
                "note": (
                    "All RAM IDs, RANK labels and weights are provisional. "
                    "Observations alone do not associate ROM blocks with opponents."
                ),
            }

    def export_json(self):
        # Export contains only the same allowlisted data saved locally.
        payload = json.dumps(self.report(), ensure_ascii=False, indent=2)
        if len(payload.encode("utf-8")) > MAX_EXPORT_BYTES:
            # Return a bounded tail, preserving provenance of the session.
            with self._lock:
                events = list(self._events)
                while events:
                    report = self.report()
                    report["events"] = events
                    report["exportTruncated"] = True
                    payload = json.dumps(report, ensure_ascii=False, indent=2)
                    if len(payload.encode("utf-8")) <= MAX_EXPORT_BYTES:
                        return payload
                    events = events[10:]
            raise RuntimeError("Live diagnostics export could not fit limit")
        return payload
