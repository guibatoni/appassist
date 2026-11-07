"""Regressão do RANK automático por SHA, ePSXe/PID e duelos.

Sem ROM real: a ponte recebe contadores sintéticos de um leitor RAM simulado.
A pontuação e os limiares são os mesmos do motor SPOILS existente.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from auto_mods import ModCatalog,atomic_json,supported_for_runtime
from dueltrace_web_bridge import DueltraceWebBridge
from dueltrace_web_security import ProtectedDesktopApi
from dueltrace_spoils_manual import calculate_manual_spoils
from scanner_multiiso import X15_SHA
from test_dueltrace_drops import fake_profile


class AutomaticRankTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        home=Path(temp.name)
        self.catalog=ModCatalog(home)
        self.sha=X15_SHA
        self.profile=fake_profile(self.sha,["Z-POW","S-POW","S-TEC"])
        profile_file=home/"profiles"/self.sha[:16]/"profile.json"
        atomic_json(profile_file,self.profile)
        self.entry={
            "sha256":self.sha,"profile_path":str(profile_file),
            "file_name":"X15 de teste","source_path":str(home/"test.iso"),
            "level":"conhecido_validado","approved":True,
            "features":supported_for_runtime(self.profile),
        }
        atomic_json(self.catalog.registry_file,{"schema":1,"entries":[self.entry]})
        atomic_json(self.catalog.active_file,{"sha256":self.sha})
        self.counters={
            "turns":1,"effective_attacks":0,"defense_wins":0,"face_down":0,
            "spells":0,"traps":0,"cards_used":0,"remaining_lp":8000,
            "fusions":0,"equips":0,
        }
        self.reader=Mock(return_value={
            "ready":True,"status":"Dois registros estáveis",
            "pid":1111,"counters":self.counters,
        })
        self.bridge=DueltraceWebBridge(self.catalog,rank_reader=self.reader)

    def test_two_independent_polls_enable_rank_without_lp_click(self):
        first=self.bridge.get_rank_auto()
        self.assertEqual(first["state"],"auto_calibrating")
        self.assertIsNone(first["score"])
        self.assertFalse(first["autoCalibrated"])
        self.assertEqual(first["validationProgress"],1)
        second=self.bridge.get_rank_auto()
        self.assertTrue(second["ready"])
        self.assertTrue(second["autoCalibrated"])
        self.assertEqual(second["calibrationMode"],"automatic_provisional")
        self.assertEqual((second["score"],second["category"]),(101,"Z-POW"))
        self.assertEqual(second["sourceMode"],"verified")
        self.assertFalse(second["final"])
        self.assertEqual(second["score"],
                         calculate_manual_spoils(self.counters,"lp",self.sha)["score"])
        self.counters["spells"]=1
        update=self.bridge.get_rank_auto()
        self.assertEqual(update["score"],95)
        self.assertTrue(update["autoCalibrated"])
        self.assertEqual(update["category"],"Z-POW")
        self.assertEqual(update["breakdown"]["spells"],-4)

    def test_changed_lp_resets_consensus_and_pid_cannot_be_reused(self):
        self.assertEqual(self.bridge.get_rank_auto()["state"],"auto_calibrating")
        self.counters["remaining_lp"]=7000
        self.assertEqual(self.bridge.get_rank_auto()["validationProgress"],1)
        ready=self.bridge.get_rank_auto()
        self.assertTrue(ready["ready"])
        self.assertEqual(ready["candidateLp"],7000)
        self.reader.return_value["pid"]=2222
        first_other=self.bridge.get_rank_auto()
        self.assertEqual(first_other["state"],"auto_calibrating")
        self.assertIsNone(first_other["score"])
        self.assertTrue(self.bridge.get_rank_auto()["ready"])
        self.assertEqual(self.bridge._rank_calibration["pid"],2222)

    def test_new_duel_requires_new_consensus_without_old_score(self):
        self.bridge.get_rank_auto()
        self.assertTrue(self.bridge.get_rank_auto()["ready"])
        self.counters["turns"]=0
        between=self.bridge.get_rank_auto()
        self.assertEqual(between["state"],"auto_calibrating")
        self.assertIsNone(between["score"])
        self.counters["turns"]=1
        self.assertEqual(self.bridge.get_rank_auto()["validationProgress"],1)
        self.assertTrue(self.bridge.get_rank_auto()["ready"])

    def test_short_ram_gap_never_renders_stale_score(self):
        self.bridge.get_rank_auto()
        self.assertTrue(self.bridge.get_rank_auto()["ready"])
        previous=self.reader.return_value
        self.reader.return_value={"ready":False,"status":"RAM em transição",
                                  "pid":1111,"counters":None}
        state=self.bridge.get_rank_auto()
        self.assertFalse(state["ready"])
        self.assertIsNone(state["score"])
        self.reader.return_value=previous
        self.assertTrue(self.bridge.get_rank_auto()["ready"])

    def test_unverified_iso_never_reads_ram_without_opt_in(self):
        unknown="a"*64
        foreign=fake_profile(unknown)
        profile_file=self.catalog.home/"profiles"/unknown[:16]/"profile.json"
        atomic_json(profile_file,foreign)
        entry={**self.entry,"sha256":unknown,"profile_path":str(profile_file)}
        atomic_json(self.catalog.registry_file,{"schema":1,
                                                 "entries":[self.entry,entry]})
        atomic_json(self.catalog.active_file,{"sha256":unknown})
        self.reader.reset_mock()
        self.assertEqual(self.bridge.get_rank()["state"],"unsupported")
        self.reader.assert_not_called()
        # A interface Alpha inicia somente após detectar um duelo plausível
        # e ainda exige consenso de LP e duas alterações reais.
        self.assertEqual(self.bridge.get_rank_auto()["state"],"auto_calibrating")
        self.assertEqual(self.bridge._rank_experimental_sha,unknown)
        self.assertTrue(self.reader.called)
        pending=self.bridge.get_rank_auto()
        self.assertEqual(pending["state"],"needs_ram_validation")
        self.assertEqual(pending["validationProgress"],0)
        self.counters["effective_attacks"]=1
        self.assertEqual(self.bridge.get_rank_auto()["validationProgress"],1)
        self.counters["turns"]=2
        candidate=self.bridge.get_rank_auto()
        self.assertTrue(candidate["ready"])
        self.assertTrue(candidate["autoCalibrated"])
        self.assertEqual(candidate["sourceMode"],"experimental")
        self.assertEqual(candidate["rankSystem"],"classic")
        self.assertIsNone(self.bridge._rank_last_snapshot)
        with self.assertRaises(ValueError):
            self.bridge.capture_rank_prediction()
        self.bridge.set_rank_experimental(False)
        self.assertEqual(self.bridge.get_rank()["state"],"unsupported")
        self.assertEqual(self.bridge.get_rank_auto()["state"],"auto_calibrating")

    def test_calibration_button_restarts_known_iso_without_changing_formula(self):
        self.bridge.get_rank_auto()
        self.assertTrue(self.bridge.get_rank_auto()["ready"])
        self.assertEqual(self.bridge.get_rank_auto()["score"],101)
        result=self.bridge.calibrate_rank()
        self.assertTrue(result["started"])
        self.assertIsNone(self.bridge._rank_calibration)
        self.assertIsNone(self.bridge._rank_auto_probe)
        self.assertIsNone(self.bridge._rank_experimental_sha)
        first=self.bridge.get_rank_auto()
        self.assertEqual(first["state"],"auto_calibrating")
        self.assertIsNone(first["score"])
        second=self.bridge.get_rank_auto()
        self.assertTrue(second["ready"])
        self.assertEqual((second["score"],second["category"]),(101,"Z-POW"))

    def test_calibration_uses_existing_opt_in_for_unmapped_iso(self):
        unknown="b"*64
        foreign=fake_profile(unknown)
        profile_file=self.catalog.home/"profiles"/unknown[:16]/"profile.json"
        atomic_json(profile_file,foreign)
        entry={**self.entry,"sha256":unknown,"profile_path":str(profile_file)}
        atomic_json(self.catalog.registry_file,{"schema":1,"entries":[self.entry,entry]})
        atomic_json(self.catalog.active_file,{"sha256":unknown})
        self.reader.reset_mock()
        self.assertEqual(self.bridge.get_rank()["state"],"unsupported")
        self.reader.assert_not_called()
        # O botão desapareceu da UI; endpoint manual é mantido para legado.
        self.assertEqual(self.bridge.get_rank_auto()["state"],"auto_calibrating")
        result=self.bridge.calibrate_rank()
        self.assertTrue(result["started"])
        self.assertEqual(self.bridge._rank_experimental_sha,unknown)
        self.assertEqual(self.bridge.get_rank_auto()["state"],"auto_calibrating")
        observing=self.bridge.get_rank_auto()
        self.assertEqual(observing["state"],"needs_ram_validation")
        self.assertEqual(observing["validationProgress"],0)
        self.counters["effective_attacks"]=1
        self.assertEqual(self.bridge.get_rank_auto()["validationProgress"],1)
        self.counters["turns"]=2
        visible=self.bridge.get_rank_auto()
        self.assertTrue(visible["ready"])
        self.assertEqual(visible["sourceMode"],"experimental")
        self.assertEqual(visible["rankSystem"],"classic")
        self.assertIsNone(self.bridge._rank_last_snapshot)

    def test_calibration_is_protected_and_rejects_missing_active_iso(self):
        api=ProtectedDesktopApi(self.bridge,"v"*64)
        with self.assertRaises(PermissionError):
            api.calibrate_rank("invalid")
        self.assertTrue(api.calibrate_rank("v"*64)["started"])
        self.catalog.active_file.unlink()
        with self.assertRaises(ValueError):
            api.calibrate_rank("v"*64)
        self.assertIsNone(self.bridge._rank_experimental_sha)

    def test_auto_endpoint_requires_local_token_and_manual_remains_compatible(self):
        api=ProtectedDesktopApi(self.bridge,"v"*64)
        with self.assertRaises(PermissionError):
            api.get_rank_auto("invalid")
        self.assertEqual(api.get_rank_auto("v"*64)["state"],"auto_calibrating")
        self.assertTrue(api.get_rank_auto("v"*64)["ready"])
        self.assertEqual(self.bridge.get_rank()["score"],101)
        self.assertEqual(self.bridge.calculate_spoils(self.counters,"lp")["score"],101)


if __name__=="__main__":
    unittest.main()
