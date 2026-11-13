"""Background ePSXe live tracker: UI-independent, read-only regression tests."""
from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_background_live import BackgroundLiveTracker
from dueltrace_web_bridge import DueltraceWebBridge


class SyntheticBridge:
    """No ePSXe, BIOS, memory scan or network needed."""
    def __init__(self):
        self._lock=threading.RLock()
        self.sha="a"*64
        self.profile=True
        self.calls={"hand":0,"rank":0,"opponent":0,"deck":0}
        self.hand_ids=[461,16,635,10,123]
        self.hand_entered=threading.Event()

    def _active(self):
        return {"sha256":self.sha}, {}, {"rom_sha256":self.sha} if self.profile else None

    def _get_hand_direct(self):
        self.calls["hand"]+=1
        self.hand_entered.set()
        return {"ready":True,"hand":[{"id":cid} for cid in self.hand_ids],
                "pairs":[{"a":461,"b":16,"result":69}],"chains":[]}

    def _get_rank_auto_direct(self):
        self.calls["rank"]+=1
        return {"ready":True,"state":"provisional","score":95,
                "category":"Z-POW"}

    def _get_live_opponent_direct(self):
        self.calls["opponent"]+=1
        return {"ready":True,"runtimeOpponentId":9,
                "mayActivateDrops":False}

    def _get_confirmed_live_deck(self,sha):
        self.calls["deck"]+=1
        if sha!=self.sha:
            return None
        return {"ready":True,"deckIds":[461,16,635,10,123]*8}


class BackgroundLiveTests(unittest.TestCase):
    def test_independent_sampler_updates_cards_rank_opponent_and_fusions(self):
        bridge=SyntheticBridge()
        now=[10.0]
        worker=BackgroundLiveTracker(bridge,clock=lambda:now[0],detector=lambda:True)
        worker._started=True
        for kind in ("hand","rank","opponent","deck"):
            self.assertTrue(worker.sample_once(kind))
        self.assertEqual(worker.snapshot("hand",bridge.sha)["hand"][0]["id"],461)
        self.assertEqual(worker.snapshot("hand",bridge.sha)["pairs"][0]["result"],69)
        self.assertEqual(worker.snapshot("rank",bridge.sha)["score"],95)
        self.assertEqual(worker.snapshot("opponent",bridge.sha)["runtimeOpponentId"],9)
        self.assertEqual(worker.snapshot("deck",bridge.sha)["deckIds"][0],461)
        self.assertEqual(len(worker.snapshot("deck",bridge.sha)["deckIds"]),40)
        self.assertEqual(bridge.calls,{"hand":1,"rank":1,"opponent":1,"deck":1})

    def test_caches_are_defensive_copies_and_expire_instead_of_freezing(self):
        bridge=SyntheticBridge()
        now=[100.0]
        worker=BackgroundLiveTracker(bridge,clock=lambda:now[0],detector=lambda:True)
        self.assertTrue(worker.sample_once("hand"))
        # snapshot requires running worker; force its state for deterministic tests.
        worker._started=True
        value=worker.snapshot("hand",bridge.sha)
        self.assertIsNotNone(value)
        value["hand"][0]["id"]=722
        self.assertEqual(worker.snapshot("hand",bridge.sha)["hand"][0]["id"],461)
        now[0]+=4.1
        self.assertIsNone(worker.snapshot("hand",bridge.sha))
        worker.stop()

    def test_old_mod_state_is_never_reused_after_switch_or_removal(self):
        bridge=SyntheticBridge()
        worker=BackgroundLiveTracker(bridge,detector=lambda:True)
        worker.sample_once("hand")
        worker._started=True
        old=bridge.sha
        bridge.sha="b"*64
        self.assertIsNone(worker.snapshot("hand",bridge.sha))
        worker.sample_once("hand")
        self.assertIsNone(worker.snapshot("hand",old))
        self.assertEqual(worker.snapshot("hand",bridge.sha)["hand"][0]["id"],461)
        bridge.profile=False
        self.assertFalse(worker.sample_once("hand"))
        worker.invalidate()
        self.assertIsNone(worker.snapshot("hand",bridge.sha))
        worker.stop()

    def test_no_emulator_returns_offline_without_opening_ram_or_logging_events(self):
        bridge=SyntheticBridge()
        worker=BackgroundLiveTracker(bridge,detector=lambda:False)
        worker._started=True
        for kind in ("hand","rank","opponent","deck"):
            self.assertTrue(worker.sample_once(kind))
            self.assertFalse(worker.snapshot(kind,bridge.sha)["ready"])
        self.assertEqual(bridge.calls,{"hand":0,"rank":0,"opponent":0,"deck":0})
        worker.stop()

    def test_read_failure_does_not_publish_old_cards(self):
        bridge=SyntheticBridge()
        worker=BackgroundLiveTracker(bridge,detector=lambda:True)
        worker._started=True
        worker.sample_once("hand")
        bridge._get_hand_direct=Mock(side_effect=OSError("access denied"))
        worker.sample_once("hand")
        failed=worker.snapshot("hand",bridge.sha)
        self.assertFalse(failed["ready"])
        self.assertEqual(failed["hand"],[])
        worker.stop()

    def test_live_workers_start_before_visiting_any_tab_and_stop_cleanly(self):
        bridge=SyntheticBridge()
        worker=BackgroundLiveTracker(bridge,detector=lambda:True)
        self.assertTrue(worker.start())
        self.assertFalse(worker.start())
        self.assertTrue(bridge.hand_entered.wait(timeout=4.0))
        self.assertTrue(worker.running)
        worker.stop()
        self.assertFalse(worker.running)
        self.assertIsNone(worker.snapshot("hand",bridge.sha))

    def test_bridge_routes_use_shared_cache_without_extra_ram_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog=Mock()
            catalog.home=Path(tmp)
            sha="a"*64
            catalog.current.return_value={"sha256":sha}
            catalog.list.return_value=[{"sha256":sha,"file_name":"fixture.iso"}]
            catalog.profile_for.return_value={"rom_sha256":sha,
               "supported_features":{"cards":True,"fusions":True},
               "cards":[{"id":cid,"name":f"Card {cid}","atk":1000,"def":800}
                         for cid in (461,16,635,10,123)],
               "fusion_recipes":[]}
            app=DueltraceWebBridge(catalog)
            fake_hand=Mock(return_value={
                "ready":True,"hand":[{"id":461}],"pairs":[],"chains":[]})
            fake_rank=Mock(return_value={"ready":True,"score":95,
                                        "category":"Z-POW"})
            fake_opponent=Mock(return_value={"ready":True,"runtimeOpponentId":5})
            app._get_hand_direct=fake_hand
            app._get_rank_auto_direct=fake_rank
            app._get_live_opponent_direct=fake_opponent
            monitor=BackgroundLiveTracker(app,detector=lambda:True)
            app._background_live=monitor
            monitor._started=True
            for kind in ("hand","rank","opponent"):
                self.assertTrue(monitor.sample_once(kind))
            for _ in range(10):
                self.assertEqual(app.get_hand()["hand"][0]["id"],461)
                self.assertEqual(app.get_rank_auto()["score"],95)
                self.assertEqual(app.get_live_opponent()["runtimeOpponentId"],5)
            fake_hand.assert_called_once()
            fake_rank.assert_called_once()
            fake_opponent.assert_called_once()
            self.assertTrue(app.get_state()["backgroundLiveRunning"])
            monitor.stop()

    def test_decks_page_uses_background_state_but_saves_still_read_fresh_ram(self):
        source=(ROOT/"scanner/dueltrace_web_bridge.py").read_text(encoding="utf8")
        section=source[source.index("    def get_deck_library("):
                       source.index("    def save_current_deck(")]
        self.assertIn('self._background_live.snapshot("deck",sha)',section)
        save=source[source.index("    def save_current_deck("):
                    source.index("    def get_drops(")]
        self.assertIn('self._get_confirmed_live_deck(active["sha256"])',save)

    def test_desktop_bootstraps_sampler_before_webview_and_stops_on_exit(self):
        source=(ROOT/"scanner/dueltrace_web_desktop.py").read_text(encoding="utf8")
        self.assertIn("bridge.start_background_live()",source)
        self.assertIn("bridge.stop_background_live()",source)
        self.assertLess(source.index("bridge.start_background_live()"),
                        source.index("webview.start(debug=False"))
        self.assertGreater(source.index("bridge.stop_background_live()"),
                           source.index("webview.start(debug=False"))


if __name__=="__main__":
    unittest.main()
