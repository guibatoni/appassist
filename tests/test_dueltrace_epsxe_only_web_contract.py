"""ePSXe-only rollback and future web snapshot privacy contracts."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_epsxe_web_snapshot import make_web_snapshot
from dueltrace_web_bridge import DueltraceWebBridge


class EpsxeOnlyRollbackTests(unittest.TestCase):
    def test_no_pcsx_redux_modules_present_in_new_source(self):
        scanner=ROOT/"scanner"
        self.assertFalse((scanner/"dueltrace_pcsx_redux.py").exists())
        self.assertFalse((scanner/"pcsx_redux_launcher.py").exists())
        self.assertFalse((ROOT/"web/components/desktop/emulator-settings.tsx").exists())
        for path in (
            scanner/"dueltrace_web_bridge.py",
            scanner/"dueltrace_web_security.py",
            scanner/"dueltrace_web_desktop.py",
            ROOT/"web/lib/desktop.ts",
            ROOT/"web/components/desktop/settings-page.tsx",
        ):
            with self.subTest(path=path):
                code=path.read_text(encoding="utf8").lower()
                self.assertNotIn("pcsx-redux",code)
                self.assertNotIn("pcsx_redux",code)

    def test_epsxe_reader_and_launcher_are_restored(self):
        bridge=(ROOT/"scanner/dueltrace_web_bridge.py").read_text("utf8")
        self.assertIn("read_hand_from_epsxe",bridge)
        self.assertIn("launch_epsxe",bridge)
        self.assertIn("configure_epsxe",bridge)

    def test_windows_bridge_keeps_epsxe_reader_injection(self):
        catalog=Mock()
        with __import__("tempfile").TemporaryDirectory() as tmp:
            catalog.home=Path(tmp)
            catalog.current.return_value={}
            catalog.list.return_value=[]
            catalog.profile_for.return_value=None
            reader=Mock(return_value={"ready":True,"hand_ids":[1,2,3,4,5]})
            app=DueltraceWebBridge(catalog,ram_reader=reader)
            self.assertIs(app._ram_reader,reader)
            self.assertTrue(callable(app.configure_epsxe))
            self.assertTrue(callable(app.start_game))

    def test_snapshot_exports_only_five_ids_and_guards_rank_provenance(self):
        hand={"ready":True,"status":"C:/private/personal.iso",
              "pid":456,"rawRam":b"secret",
              "hand":[{"id":i,"name":f"User {i}","path":"C:/secret"} for i in (461,16,635,10,123)]}
        rank={"ready":True,"score":95,"category":"Z-POW","final":False,
              "pid":456,"rawBytes":[12,13],"filePath":"C:/private"}
        event=make_web_snapshot(hand,rank,sequence=9)
        self.assertEqual(event["hand"]["cardIds"],[461,16,635,10,123])
        self.assertEqual(event["rank"]["category"],"Z-POW")
        self.assertTrue(event["rank"]["provisional"])
        self.assertFalse(event["runningIsoConfirmed"])
        self.assertEqual(set(event),
                         {"schema","type","emulator","sequence","hand","rank",
                          "runningIsoConfirmed"})
        serialized=__import__("json").dumps(event)
        for secret in ("C:/","pid","raw","User","secret"):
            self.assertNotIn(secret,serialized)

    def test_snapshot_never_approves_invalid_or_stale_data(self):
        for cards in ([],[{"id":1}],[{"id":1}]*4,[{"id":0}]*5,
                      [{"id":"1"}]*5,[{"id":True}]*5):
            with self.subTest(cards=cards):
                event=make_web_snapshot({"ready":True,"hand":cards},
                                        {"ready":True,"score":95,
                                         "category":"S-POW"})
                self.assertFalse(event["hand"]["ready"])
                self.assertEqual(event["hand"]["cardIds"],[])
        event=make_web_snapshot({"ready":False,"hand":[{"id":i} for i in range(1,6)]},
                                {"ready":True,"score":99,
                                 "category":"S-POW","final":True})
        self.assertFalse(event["hand"]["ready"])
        self.assertFalse(event["rank"]["provisional"])
        for bad in (True,4.5,-1,2**53):
            with self.subTest(sequence=bad):
                with self.assertRaises(ValueError):
                    make_web_snapshot({"ready":False},sequence=bad)
        forged=make_web_snapshot({"ready":True,"hand":[{"id":i} for i in range(1,6)]},
                                  {"ready":True,"score":"95",
                                   "category":"S-POW"})
        self.assertFalse(forged["rank"]["ready"])
        self.assertIsNone(forged["rank"]["score"])


if __name__=="__main__":
    unittest.main()
