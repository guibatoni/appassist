"""DUELTRACE Windows bridge integration with PCSX-Redux (mocked emulators).

The new adapter must not change the ePSXe path or make unsupported rank
readers fall back to the Windows host address on PCSX-Redux.
"""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from auto_mods import load_json
from dueltrace_web_bridge import DueltraceWebBridge
from dueltrace_pcsx_redux import X15_RANK_OFFSET,HAND_OFFSET
from dueltrace_live_hand import HAND_ADDRESS
from dueltrace_rank_live import CANDIDATE_RANK_ADDRESS


class EmulatorBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)
        self.catalog=Mock()
        self.catalog.home=self.home
        self.sha="a"*64
        self.catalog.current.return_value={"sha256":self.sha}
        self.entry={"sha256":self.sha,"file_name":"Mod.iso",
                    "profile_path":str(self.home/"mod-profile.json")}
        self.catalog.list.return_value=[self.entry]
        self.profile={
            "rom_sha256":self.sha,
            "supported_features":{"cards":True,"fusions":False},
            "cards":[{"id":i,"name":f"Carta {i}","atk":1000,"def":1000}
                     for i in (1,2,3,4,5)],
            "fusion_recipes":[],
        }
        self.catalog.profile_for.return_value=self.profile
        self.bridge=DueltraceWebBridge(self.catalog)

    def test_real_ps1_rank_offset_not_host_pointer(self):
        self.assertEqual(
            X15_RANK_OFFSET,
            CANDIDATE_RANK_ADDRESS-(HAND_ADDRESS-HAND_OFFSET))

    def test_emulator_mode_persists_without_erasing_other_preferences(self):
        path=self.bridge.settings_path
        from auto_mods import atomic_json
        atomic_json(path,{"language":"pt-BR","epsxe_executable":"C:/Games/ePSXe.exe"})
        with patch("dueltrace_web_bridge.redux_connection_status",
                   return_value={"available":True,"running":True,"status":"ready"}):
            result=self.bridge.set_emulator("pcsx-redux",8080)
            self.assertEqual(result["active"],"pcsx-redux")
            self.assertEqual(result["port"],8080)
            self.assertTrue(result["reduxAvailable"])
        settings=load_json(path,{})
        self.assertEqual(settings["emulator_mode"],"pcsx-redux")
        self.assertEqual(settings["language"],"pt-BR")
        self.assertIn("epsxe_executable",settings)
        for mode,port in (("unknown",8080),("pcsx-redux",80),
                          ("auto",65536),("epsxe","8080")):
            with self.subTest(mode=mode,port=port):
                with self.assertRaises(ValueError):
                    self.bridge.set_emulator(mode,port)

    def test_hand_is_sourced_from_redux_when_selected(self):
        with patch("dueltrace_web_bridge.redux_connection_status",
                   return_value={"available":True,"running":True,"status":"ready"}), \
             patch("dueltrace_web_bridge.read_hand_from_redux",
                   return_value={"ready":True,"hand_ids":[1,2,3,4,5],
                                 "status":"Redux pronto"}) as read:
            self.bridge.set_emulator("pcsx-redux",8080)
            with patch.object(self.bridge,"_fusion_index",return_value={}):
                result=self.bridge.get_hand()
        self.assertTrue(result["ready"])
        self.assertEqual([c["id"] for c in result["hand"]],[1,2,3,4,5])
        self.assertIn("Redux",result["status"])
        read.assert_called_once_with(preferred_pid=None,port=8080)

    def test_epsxe_reader_injection_still_used_unchanged(self):
        fake=Mock(return_value={"ready":True,"hand_ids":[1,2,3,4,5],
                                "status":"ePSXe confirmado"})
        self.bridge=DueltraceWebBridge(self.catalog,ram_reader=fake)
        with patch("dueltrace_web_bridge.redux_connection_status",
                   return_value={"available":True,"running":True,"status":"ready"}), \
             patch("dueltrace_web_bridge.read_hand_from_redux") as redux:
            self.bridge.set_emulator("pcsx-redux",8080)
            with patch.object(self.bridge,"_fusion_index",return_value={}):
                result=self.bridge.get_hand()
        self.assertTrue(result["ready"])
        redux.assert_not_called()
        fake.assert_called_once_with(preferred_pid=None)

    def test_unknown_iso_rank_cannot_use_pcsx_host_address(self):
        with patch("dueltrace_web_bridge.redux_connection_status",
                   return_value={"available":True,"running":True,"status":"ready"}), \
             patch("dueltrace_web_bridge.read_rank_candidate_redux") as reader:
            self.bridge.set_emulator("pcsx-redux",8080)
            result=self.bridge.get_rank()
        self.assertFalse(result["ready"])
        self.assertEqual(result["state"],"unsupported")
        reader.assert_not_called()

    def test_pcsx_file_picker_validates_executable_before_saving(self):
        choices=iter([["/missing/pcsx-redux.exe"]])
        self.bridge._file_picker=lambda kind: next(choices)
        with self.assertRaises(FileNotFoundError):
            self.bridge.configure_pcsx_redux()
        self.assertFalse(self.bridge.settings_path.exists())


if __name__=="__main__":
    unittest.main()
