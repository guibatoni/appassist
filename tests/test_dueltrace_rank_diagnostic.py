"""Diagnóstico RANK: sem extrapolar modelo X15 ou acessar memória do ePSXe."""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_rank_diagnostic import diagnose_rank_profile
from dueltrace_web_security import ProtectedDesktopApi
from scanner_multiiso import X15_SHA
from test_dueltrace_rank_profile_live import profile as verified_mod_profile

SHA="a"*64


class RankDiagnosticTests(unittest.TestCase):
    def test_no_iso_explains_instead_of_fake_projection(self):
        result=diagnose_rank_profile(None,None)
        self.assertEqual(result["code"],"no_active_iso")
        self.assertFalse(result["readyForLiveRead"])
        self.assertIsNone(result["score"])
        self.assertIsNone(result["projectedRank"])

    def test_unrecognized_mod_with_no_table_is_blocked(self):
        result=diagnose_rank_profile(SHA,{"rom_sha256":SHA})
        self.assertEqual(result["code"],"rank_table_missing")
        self.assertFalse(result["readyForLiveRead"])
        self.assertFalse(result["ramBindingVerified"])

    def test_static_mips_candidates_are_not_runtime_evidence(self):
        mod={"rom_sha256":SHA,
             "rank_points":{"available":True,"structure_verified":True},
             "rank_mips_evidence":{"candidates":[{"pc":"0x80010100"}]}}
        result=diagnose_rank_profile(SHA,mod)
        self.assertEqual(result["code"],"mips_candidates_only")
        self.assertEqual(result["mipsCandidates"],1)
        self.assertFalse(result["mipsRuntimeConfirmed"])
        self.assertFalse(result["readyForLiveRead"])

    def test_table_without_ram_binding_remains_unavailable(self):
        result=diagnose_rank_profile(SHA,{
            "rom_sha256":SHA,"rank_points":{"available":True,"structure_verified":True}
        })
        self.assertEqual(result["code"],"ram_binding_missing")
        self.assertFalse(result["readyForLiveRead"])

    def test_invalid_ram_binding_does_not_enable_live_rank(self):
        mod=verified_mod_profile()
        mod["rank_runtime_binding"]["verified_duels"]=1
        result=diagnose_rank_profile(SHA,mod)
        self.assertEqual(result["code"],"ram_binding_unverified")
        self.assertTrue(result["ramBindingPresent"])
        self.assertFalse(result["ramBindingVerified"])
        self.assertFalse(result["readyForLiveRead"])

    def test_verified_binding_is_accepted_without_dropping_safety_gate(self):
        mod=verified_mod_profile()
        result=diagnose_rank_profile(SHA,mod)
        self.assertEqual(result["code"],"verified_ram_binding")
        self.assertTrue(result["ramBindingVerified"])
        self.assertTrue(result["readyForLiveRead"])
        self.assertIsNone(result["score"])

    def test_known_x15_sha_is_distinct_from_similarly_named_mod(self):
        result=diagnose_rank_profile(X15_SHA,{"rom_sha256":X15_SHA})
        self.assertEqual(result["code"],"known_x15_sha")
        self.assertTrue(result["x15Exact"])
        self.assertTrue(result["readyForLiveRead"])
        self.assertEqual(result["rankSystem"],"x15")
        mod={"rom_sha256":SHA,"file_name":"Remaster X15 copy.iso"}
        similar=diagnose_rank_profile(SHA,mod)
        self.assertFalse(similar["readyForLiveRead"])
        self.assertEqual(similar["rankSystem"],"classic")

    def test_session_auth_required_and_diagnostic_never_reads_ram(self):
        bridge=Mock()
        bridge.get_rank_diagnostic.return_value=diagnose_rank_profile(SHA,{"rom_sha256":SHA})
        api=ProtectedDesktopApi(bridge,"x"*64)
        with self.assertRaises(PermissionError):
            api.get_rank_diagnostic("wrong")
        self.assertEqual(bridge.get_rank_diagnostic.call_count,0)
        result=api.get_rank_diagnostic("x"*64)
        self.assertEqual(result["code"],"rank_table_missing")
        bridge.get_rank_diagnostic.assert_called_once_with()
        bridge.get_rank.assert_not_called()


if __name__=="__main__":
    unittest.main()
