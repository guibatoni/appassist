"""Always-on, LOCAL ePSXe live sampling for DUELTRACE Windows.

Sampling belongs to the Python desktop process, not to any React route.
The browser tabs and native pop-outs consume the same bounded cached
results. No sockets, no cloud uploads and no RAM writes. Only the already
validated bridge methods are sampled. Private diagnostics remain opt-in.
"""
from __future__ import annotations

from copy import deepcopy
from threading import Event, RLock, Thread
from time import monotonic


HAND_INTERVAL = 1.25
RANK_INTERVAL = 0.95
OPPONENT_INTERVAL = 4.5
MAX_AGE = {"hand": 4.0, "rank": 3.0, "opponent": 10.0, "deck": 10.0}


def epsxe_running() -> bool:
    """Fast, bounded process-presence check; never reads memory itself."""
    try:
        from dueltrace_live_hand import discover_epsxe_pids
        return bool(discover_epsxe_pids())
    except (OSError, RuntimeError, ValueError, AttributeError):
        return False


class BackgroundLiveTracker:
    """Single shared sampler per Windows bridge, independent of UI pages.

    The main worker samples the hand and RANK. Opponent probing is slower and
    separate, so an expensive exploratory probe cannot stop hand updates.
    """
    def __init__(self, bridge, *, clock=monotonic, detector=epsxe_running):
        self.bridge = bridge
        self.clock = clock
        self.detector = detector
        self._lock = RLock()
        self._stop = Event()
        self._threads = []
        self._cache = {}
        self._started = False

    @property
    def running(self) -> bool:
        with self._lock:
            return self._started and not self._stop.is_set()

    def start(self):
        with self._lock:
            if self._started and not self._stop.is_set():
                return False
            self._stop.clear()
            self._started = True
            self._cache.clear()
            self._threads = [
                Thread(target=self._loop_core, daemon=True,
                       name="dueltrace-live-hand-rank"),
                Thread(target=self._loop_opponent, daemon=True,
                       name="dueltrace-live-opponent"),
            ]
            for worker in self._threads:
                worker.start()
            return True

    def stop(self):
        self._stop.set()
        for worker in self._threads:
            if worker.is_alive():
                worker.join(timeout=2.0)
        with self._lock:
            self._started = False
            self._cache.clear()

    def _active_sha(self):
        with self.bridge._lock:
            active, _entry, profile = self.bridge._active()
            sha = active.get("sha256") if isinstance(active, dict) and profile else None
            return sha if type(sha) is str and len(sha) == 64 else None

    def snapshot(self, kind: str, active_sha: str | None):
        """No stale values after mod switches, ePSXe loss or slow probes."""
        if kind not in MAX_AGE or not active_sha or not self.running:
            return None
        with self._lock:
            entry = self._cache.get(kind)
            if (not entry or entry["sha"] != active_sha
                    or self.clock() - entry["at"] > MAX_AGE[kind]):
                return None
            return deepcopy(entry["value"])

    def invalidate(self, kind=None):
        with self._lock:
            if kind is None:
                self._cache.clear()
            elif kind in MAX_AGE:
                self._cache.pop(kind, None)

    def sample_once(self, kind: str):
        """Deterministic step for tests and both background workers."""
        if kind not in MAX_AGE:
            raise ValueError("Fluxo ao vivo inválido.")
        try:
            sha = self._active_sha()
        except (OSError, RuntimeError, ValueError, TypeError, KeyError):
            self.invalidate()
            return False
        if not sha:
            self.invalidate()
            return False
        try:
            present = self.detector()
        except (OSError, RuntimeError, ValueError):
            present = False
        if not present:
            empty = {
                "hand": {"ready": False, "status": "ePSXe não encontrado",
                         "hand": [], "pairs": [], "chains": []},
                "rank": {"ready": False, "state": "unavailable",
                         "status": "ePSXe não encontrado",
                         "score": None, "category": None},
                "opponent": {"ready": False, "status": "no_epsxe",
                             "runtimeOpponentId": None},
                "deck": {"ready": False, "deckIds": []},
            }
            value = empty[kind]
        else:
            try:
                readers = {
                    "hand": self.bridge._get_hand_direct,
                    "rank": self.bridge._get_rank_auto_direct,
                    "opponent": self.bridge._get_live_opponent_direct,
                    # Only the already-confirmed active deck of a game
                    # launched by DUELTRACE. No Memory Card writes.
                    "deck": lambda: self.bridge._get_confirmed_live_deck(sha),
                }
                value = readers[kind]()
                if kind == "deck" and value is None:
                    value = {"ready": False, "deckIds": []}
                if not isinstance(value, dict):
                    raise ValueError("Leitura de RAM inválida.")
            except (OSError, RuntimeError, ValueError, TypeError, KeyError,
                    AttributeError, ImportError, OverflowError):
                value = {"ready": False, "status": "Leitura temporariamente indisponível"}
                if kind == "hand":
                    value.update(hand=[], pairs=[], chains=[])
                elif kind == "rank":
                    value.update(state="unavailable", score=None, category=None)
                elif kind == "opponent":
                    value.update(runtimeOpponentId=None)
                else:
                    value.update(deckIds=[])
        # The active ISO can change while the RAM reader is busy. Never
        # publish a result derived from the old profile into a new tab.
        try:
            still_active = sha == self._active_sha()
        except (OSError, RuntimeError, ValueError, TypeError, KeyError):
            still_active = False
        if not still_active or self._stop.is_set():
            self.invalidate()
            return False
        with self._lock:
            if self._cache and any(x["sha"] != sha for x in self._cache.values()):
                self._cache.clear()
            self._cache[kind] = {"sha": sha, "at": self.clock(),
                                  "value": deepcopy(value)}
        return True

    def _loop_core(self):
        # First sample starts immediately, before any user opens 'Início'.
        while not self._stop.is_set():
            start = self.clock()
            try:
                self.sample_once("hand")
                if self._stop.is_set():
                    break
                self.sample_once("rank")
            except Exception:
                # An unexpected scan failure must not kill the always-on
                # worker and leave a ready-looking snapshot frozen forever.
                self.invalidate()
            self._stop.wait(max(0.1, min(HAND_INTERVAL, RANK_INTERVAL) -
                                (self.clock() - start)))

    def _loop_opponent(self):
        while not self._stop.is_set():
            start = self.clock()
            try:
                self.sample_once("opponent")
                if not self._stop.is_set():
                    self.sample_once("deck")
            except Exception:
                # A slow or incompatible opponent/deck probe cannot erase
                # a validated hand or RANK snapshot from the core worker.
                self.invalidate("opponent")
                self.invalidate("deck")
            self._stop.wait(max(0.3, OPPONENT_INTERVAL -
                                (self.clock() - start)))
