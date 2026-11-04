"""Duelo real continua pendente; testes usam ISOs e RAM sintéticas."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))

from auto_mods import ModCatalog, atomic_json, supported_for_runtime
from dueltrace_web_bridge import DueltraceWebBridge
from dueltrace_web_security import ProtectedDesktopApi
from scanner_multiiso import X15_SHA
from test_dueltrace_drops import fake_profile


class CapturedRankTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home=Path(temp.name)
        self.sha=X15_SHA
        self.catalog=ModCatalog(self.home)
        profile=fake_profile(self.sha, ["Z-POW","S-POW","S-TEC"])
        self.profile_path=self.home/"profiles"/self.sha[:16]/"profile.json"
        atomic_json(self.profile_path,profile)
        entry={
            "sha256":self.sha,
            "source_path":str(self.home/"synthetic.iso"),
            "file_name":"X15 synthetic tests",
            "profile_path":str(self.profile_path),
            "level":"conhecido_validado","approved":True,
            "features":supported_for_runtime(profile),
        }
        atomic_json(self.catalog.registry_file,{"schema":1,"entries":[entry]})
        atomic_json(self.catalog.active_file,{"sha256":self.sha})
        self.counters={
            "turns":1,"effective_attacks":0,"defense_wins":0,
            "face_down":0,"spells":0,"traps":0,"fusions":0,"equips":0,
            "remaining_lp":8000,"cards_used":0,
        }
        self.reader=Mock(return_value={
            "ready":True,"status":"synthetic stable RAM",
            "pid":3456,"counters":self.counters,
        })
        self.bridge=DueltraceWebBridge(self.catalog,rank_reader=self.reader)

    def test_no_capture_before_lp_confirmation(self):
        with self.assertRaises(ValueError):
            self.bridge.capture_rank_prediction()
        self.assertFalse(self.bridge.get_pending_rank_capture()["ready"])
        self.assertEqual(self.bridge.get_rank_comparison()["total"],0)

    def test_capture_is_used_only_once_for_correct_iso_and_manual_result(self):
        self.assertEqual(self.bridge.confirm_rank_lp(8000)["score"],101)
        frozen=self.bridge.capture_rank_prediction()
        self.assertTrue(frozen["ready"])
        self.assertEqual(frozen["score"],101)
        self.assertEqual(frozen["category"],"Z-POW")
        self.counters["spells"]=4  # live estimator changes after capture
        self.bridge.get_rank()
        outcome=self.bridge.record_duel_result(1,"Z-POW",1,101,"lp",frozen["captureId"])
        self.assertEqual(outcome["observations"],1)
        result=self.bridge.get_rank_comparison()
        self.assertEqual(result["matches"],1)
        self.assertEqual(result["cases"][0]["projected_score"],101)
        self.assertEqual(result["cases"][0]["projected_rank"],"Z-POW")
        self.assertFalse(result["binding_unlocked"])
        self.assertFalse(self.bridge.get_pending_rank_capture()["ready"])
        with self.assertRaises(ValueError):
            self.bridge.record_duel_result(1,"Z-POW",1,101,"lp",frozen["captureId"])

    def test_manual_result_without_capture_does_not_auto_attach_ram(self):
        self.bridge.confirm_rank_lp(8000)
        self.bridge.get_rank()
        self.bridge.record_duel_result(1,"Z-POW",1,101,"lp")
        report=self.bridge.get_rank_comparison()
        self.assertEqual(report["missing_prediction"],1)
        self.assertEqual(report["matches"],0)

    def test_capture_expires_and_never_attaches_to_later_duel(self):
        self.bridge.confirm_rank_lp(8000)
        captured=self.bridge.capture_rank_prediction()
        self.bridge._rank_pending_capture["at"] -= 601
        with self.assertRaises(ValueError):
            self.bridge.record_duel_result(1,"Z-POW",1,101,"lp",captured["captureId"])
        self.assertFalse(self.bridge.get_pending_rank_capture()["ready"])
        self.assertEqual(self.bridge.get_rank_comparison()["total"],0)

    def test_new_duel_pid_change_and_lp_failure_invalidate_capture(self):
        self.bridge.confirm_rank_lp(8000)
        self.bridge.capture_rank_prediction()
        self.counters["turns"]=0
        self.assertEqual(self.bridge.get_rank()["state"],"needs_lp_confirmation")
        self.assertFalse(self.bridge.get_pending_rank_capture()["ready"])
        self.bridge.confirm_rank_lp(8000)
        self.bridge.capture_rank_prediction()
        self.reader.return_value["pid"]=9999
        self.assertEqual(self.bridge.get_rank()["state"],"needs_lp_confirmation")
        self.assertFalse(self.bridge.get_pending_rank_capture()["ready"])
        self.bridge.confirm_rank_lp(8000)
        self.bridge.capture_rank_prediction()
        self.counters["remaining_lp"]=7999
        self.assertEqual(self.bridge.confirm_rank_lp(8000)["state"],"lp_mismatch")
        self.assertFalse(self.bridge.get_pending_rank_capture()["ready"])

    def test_unsupported_mod_cannot_capture(self):
        other="a"*64
        profile=fake_profile(other)
        other_path=self.home/"profiles"/other[:16]/"profile.json"
        atomic_json(other_path,profile)
        entry={
            "sha256":other, "source_path":str(self.home/"mod.iso"),
            "file_name":"unsupported", "profile_path":str(other_path),
            "level":"conhecido_validado","approved":True,
            "features":supported_for_runtime(profile),
        }
        entries=self.catalog.list()
        atomic_json(self.catalog.registry_file,{"schema":1,"entries":entries+[entry]})
        self.bridge.activate_mod(other)
        self.assertEqual(self.bridge.get_rank()["state"],"unsupported")
        with self.assertRaises(ValueError):
            self.bridge.capture_rank_prediction()
        self.reader.assert_not_called()

    def test_capability_guards_capture_and_comparison(self):
        api=ProtectedDesktopApi(self.bridge,"t"*64)
        for action in ("capture_rank_prediction","get_pending_rank_capture","get_rank_comparison"):
            with self.subTest(action=action):
                with self.assertRaises(PermissionError):
                    getattr(api,action)("invalid")
        self.assertFalse(api.get_pending_rank_capture("t"*64)["ready"])
        self.assertEqual(api.get_rank_comparison("t"*64)["total"],0)


if __name__=="__main__":
    unittest.main()
