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

    def test_automatic_spoils_begins_at_101_and_tracks_actual_actions(self):
        """Poll get_rank without entering each metric; normal X15 score engine."""
        manual=self.bridge.calculate_spoils({
            "turns":0,"effective_attacks":0,"defense_wins":0,
            "face_down":0,"spells":0,"traps":0,"cards_used":0,
            "remaining_lp":8000,"fusions":0,"equips":0
        },"lp")
        self.assertEqual(manual["score"],101)
        self.assertEqual(manual["category"],"Z-POW")
        self.assertEqual(self.bridge.get_rank()["state"],"needs_lp_confirmation")
        self.bridge.confirm_rank_lp(8000)
        start=self.bridge.get_rank()
        self.assertEqual(start["score"],101)
        self.assertEqual(start["category"],"Z-POW")
        self.assertEqual(start["breakdown"]["spells"],2)
        self.counters["spells"]=1
        after_spell=self.bridge.get_rank()
        self.assertEqual(after_spell["score"],95)
        self.assertEqual(after_spell["breakdown"]["spells"],-4)
        self.counters["spells"]=4
        after_more=self.bridge.get_rank()
        self.assertEqual(after_more["score"],91)
        self.assertEqual(after_more["category"],"S-POW")
        self.counters["remaining_lp"]=7000
        after_damage=self.bridge.get_rank()
        self.assertEqual(after_damage["score"],89)
        self.assertEqual(after_damage["category"],"S-POW")
        self.assertFalse(after_damage["final"])

    def test_verified_lp_calibration_exposes_x15_result_marker_without_recalculating_rules(self):
        self.bridge.confirm_rank_lp(8000)
        before=self.bridge.get_rank()
        self.assertEqual(before["score"],101)
        self.assertEqual(before["category"],"Z-POW")
        self.assertEqual(before["rankSystem"],"x15")
        self.assertEqual(before["victorySource"],"projected_lp")
        self.assertEqual(before["victoryBonus"],2)

        # O assistente v10.5 lê 0xD8 como -40 assinado, nunca 216.
        self.reader.return_value["result_adjustment"]=-40
        final_marker=self.bridge.get_rank()
        self.assertEqual(final_marker["score"],59)
        self.assertEqual(final_marker["category"],"S-POW")
        self.assertEqual(final_marker["victoryBonus"],-40)
        self.assertEqual(final_marker["victorySource"],"ram_deckout")
        self.assertFalse(final_marker["final"])  # não prova resultado visual do jogo
        self.assertIn("deck-out",final_marker["status"])

        self.reader.return_value["result_adjustment"]=2
        lp_marker=self.bridge.get_rank()
        self.assertEqual(lp_marker["score"],101)
        self.assertEqual(lp_marker["victorySource"],"ram_lp")

        self.reader.return_value["result_adjustment"]=None
        predicted=self.bridge.get_rank()
        self.assertEqual(predicted["score"],101)
        self.assertEqual(predicted["victorySource"],"projected_lp")

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
        self.assertTrue(self.bridge.get_pending_rank_capture()["ready"])
        # Transição de recompensa preserva captura; iniciar OUTRO duelo a invalida.
        self.counters["turns"]=1
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

    def test_short_same_process_ram_gap_keeps_lp_confirmation_without_stale_score(self):
        self.bridge.confirm_rank_lp(8000)
        self.assertEqual(self.bridge.get_rank()["score"],101)
        previous=dict(self.reader.return_value)
        self.reader.return_value={"ready":False,"status":"Memória em transição",
                                  "pid":3456,"counters":None}
        missed=self.bridge.get_rank()
        self.assertEqual(missed["state"],"unavailable")
        self.assertIsNone(missed["score"])
        self.assertIn("temporariamente",missed["status"])
        self.assertIsNotNone(self.bridge._rank_calibration)
        self.reader.return_value=previous
        resumed=self.bridge.get_rank()
        self.assertTrue(resumed["ready"])
        self.assertEqual(resumed["score"],101)
        self.assertIsNone(self.bridge._rank_gap_started)

    def test_long_gap_and_other_pid_require_new_lp_confirmation(self):
        self.bridge.confirm_rank_lp(8000)
        previous=dict(self.reader.return_value)
        self.reader.return_value={"ready":False,"status":"Amostra instável",
                                  "pid":3456,"counters":None}
        self.bridge.get_rank()
        self.bridge._rank_gap_started-=3
        lost=self.bridge.get_rank()
        self.assertEqual(lost["state"],"unavailable")
        self.assertIsNone(self.bridge._rank_calibration)
        self.reader.return_value=previous
        self.assertEqual(self.bridge.get_rank()["state"],"needs_lp_confirmation")
        self.bridge.confirm_rank_lp(8000)
        self.reader.return_value={"ready":False,"status":"Outro ePSXe",
                                  "pid":9876,"counters":None}
        self.bridge.get_rank()
        self.assertIsNone(self.bridge._rank_calibration)
        self.reader.return_value=previous
        self.assertEqual(self.bridge.get_rank()["state"],"needs_lp_confirmation")

    def test_ram_gap_after_final_turn_preserves_capture_until_observation(self):
        self.bridge.confirm_rank_lp(8000)
        captured=self.bridge.capture_rank_prediction()
        self.reader.return_value={"ready":False,"status":"Tela de vitória",
                                  "pid":3456,"counters":None}
        self.assertEqual(self.bridge.get_rank()["state"],"unavailable")
        self.assertEqual(self.bridge.get_pending_rank_capture()["captureId"],captured["captureId"])
        self.bridge.record_duel_result(1,"Z-POW",1,101,"lp",captured["captureId"])
        self.assertEqual(self.bridge.get_rank_comparison()["matches"],1)

    def test_non_x15_compatible_binary_uses_original_ranks_not_x15_and_ignores_marker(self):
        """Classificação é por SHA da ISO; mesmo motor de score não autoriza Z."""
        from fm_rank_tables import (KNOWN_X15_SLUS_SHA256,
                                    KNOWN_X15_TABLE_SHA256,LEGACY_OFFSET,STRIDE)
        from dueltrace_rank_profile_live import x15_compatible_runtime
        sha="b"*64
        profile=fake_profile(sha)
        profile["exe_sha256"]=KNOWN_X15_SLUS_SHA256
        profile["rank_points"].update({
            "available":True,"structure_verified":True,
            "table_sha256":KNOWN_X15_TABLE_SHA256,
            "first_offset":LEGACY_OFFSET,"repeat_stride":STRIDE,
        })
        self.assertTrue(x15_compatible_runtime(profile))
        other_path=self.home/"profiles"/sha[:16]/"profile.json"
        atomic_json(other_path,profile)
        entries=self.catalog.list()
        entry={
            "sha256":sha,"source_path":str(self.home/"compatible.iso"),
            "file_name":"Remaster X15 nome parecido mas SHA diferente",
            "profile_path":str(other_path),
            "level":"conhecido_validado","approved":True,
            "features":supported_for_runtime(profile),
        }
        atomic_json(self.catalog.registry_file,{"schema":1,"entries":entries+[entry]})
        self.bridge.activate_mod(sha)
        self.reader.return_value["result_adjustment"]=-40
        self.bridge.confirm_rank_lp(8000)
        initial=self.bridge.get_rank()
        self.assertEqual(initial["score"],101)  # não aplicou byte X15 em outro mod
        self.assertEqual(initial["category"],"S-POW")
        self.assertEqual(initial["rankSystem"],"classic")
        self.assertEqual(initial["victorySource"],"projected_lp")
        self.counters["spells"]=7
        later=self.bridge.get_rank()
        self.assertEqual(later["score"],87)
        self.assertEqual(later["category"],"A-POW")

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
        candidate=self.bridge.get_rank()
        self.assertEqual(candidate["state"],"needs_lp_confirmation")
        self.assertEqual(candidate["rankSystem"],"classic")
        self.assertEqual(candidate["sourceMode"],"experimental")
        with self.assertRaises(ValueError):
            self.bridge.capture_rank_prediction()
        self.reader.assert_called()

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
