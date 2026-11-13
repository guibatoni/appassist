"""Regression: pywebview file filter parser and multiple PCSX-Redux processes.

Bug observed on Windows: 'Executável PCSX-Redux (*.exe) is not a valid file
filter'. The upstream pywebview parser accepts word chars + spaces in the
description, not the dash in 'PCSX-Redux'.
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from dueltrace_web_desktop import FILE_PICKER_FILTERS
from dueltrace_web_bridge import DueltraceWebBridge
from dueltrace_pcsx_redux import connection_status

# Exact grammar from pywebview.util.parse_file_type in pywebview 6.x.
PYWEBVIEW_FILTER = re.compile(
    r'^([\w ]+)\((\*(?:\.(?:\w+|\*))*(?:;\*(?:\.(?:\w+|\*))*)*)\)$'
)


class ReduxWindowsPickerAndProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        catalog=Mock()
        catalog.home=Path(self.temp.name)
        catalog.current.return_value={"sha256":"a"*64}
        catalog.list.return_value=[{"sha256":"a"*64,"file_name":"fixture.iso",
                                    "profile_path":str(catalog.home/"profile.json")}]
        catalog.profile_for.return_value={
            "rom_sha256":"a"*64,
            "supported_features":{"cards":True,"fusions":False},
            "cards":[{"id":i,"name":f"Card {i}","atk":1,"def":1}
                     for i in (1,2,3,4,5)],
            "fusion_recipes":[],
        }
        self.bridge=DueltraceWebBridge(catalog)

    def test_every_native_file_filter_accepts_upstream_pywebview_grammar(self):
        self.assertEqual(set(FILE_PICKER_FILTERS),
                         {"memory_card","iso","trace","epsxe","pcsx_redux","rank_report"})
        for kind,filters in FILE_PICKER_FILTERS.items():
            for f in filters:
                with self.subTest(kind=kind,filter=f):
                    self.assertIsNotNone(PYWEBVIEW_FILTER.fullmatch(f))
        self.assertEqual(FILE_PICKER_FILTERS["pcsx_redux"],
                         ("Executavel PCSX Redux (*.exe)",))
        self.assertIsNone(PYWEBVIEW_FILTER.fullmatch(
            "Executável PCSX-Redux (*.exe)"))

    def test_http_reachable_with_multiple_pids_is_not_falsely_offline(self):
        def fetch(path,*,port,limit):
            self.assertEqual(path,"/api/v1/execution-flow")
            return b'{"running":true}'
        result=connection_status(fetch=fetch,pids=[140,141])
        self.assertFalse(result["available"])
        self.assertTrue(result["httpReachable"])
        self.assertIn("várias",result["status"])
        self.assertEqual(result["port"],8080)

    def test_process_choice_is_validated_and_never_saved(self):
        fake_http={"available":False,"httpReachable":False,
                   "running":False,"status":"API HTTP não encontrada"}
        with patch("dueltrace_web_bridge.discover_redux_pids",
                   return_value=[120,121]), \
             patch("dueltrace_web_bridge.redux_connection_status",
                   return_value=fake_http):
            self.bridge.set_emulator("pcsx-redux",8080)
            initial=self.bridge.get_emulator_status()
            self.assertEqual(initial["reduxPids"],[120,121])
            self.assertIsNone(initial["selectedReduxPid"])
            with self.assertRaises(ValueError):
                self.bridge.select_redux_process(119)
            with self.assertRaises(ValueError):
                self.bridge.select_redux_process("120")
            with self.assertRaises(ValueError):
                self.bridge.select_redux_process(True)
            active=self.bridge.select_redux_process(121)
            self.assertEqual(active["selectedReduxPid"],121)
            self.assertIn("121",active["status"])
            self.assertNotIn("redux_selected_pid",
                self.bridge.settings_path.read_text(encoding="utf8"))
            self.assertIsNone(self.bridge.select_redux_process(None)["selectedReduxPid"])

    def test_selected_pid_uses_host_only_when_multiple_instances(self):
        status={"available":False,"httpReachable":True,
                "running":True,"status":"API presente, associação ambígua"}
        with patch("dueltrace_web_bridge.discover_redux_pids",
                   return_value=[120,121]), \
             patch("dueltrace_web_bridge.redux_connection_status",
                   return_value=status), \
             patch("dueltrace_web_bridge.read_hand_from_redux_host",
                   return_value={"ready":True,"pid":121,"hand_ids":[1,2,3,4,5],
                                 "status":"Mão confirmada"}) as host, \
             patch("dueltrace_web_bridge.read_hand_from_redux") as http:
            self.bridge.set_emulator("pcsx-redux",8080)
            self.bridge.select_redux_process(121)
            with patch.object(self.bridge,"_fusion_index",return_value={}):
                result=self.bridge.get_hand()
        self.assertTrue(result["ready"])
        self.assertEqual(len(result["hand"]),5)
        host.assert_called_once_with(preferred_pid=121,pids=[120,121])
        http.assert_not_called()

    def test_stale_selected_pid_is_cleared_and_invalid_for_reads(self):
        http={"available":False,"httpReachable":False,
              "running":False,"status":"API indisponível"}
        with patch("dueltrace_web_bridge.redux_connection_status",return_value=http):
            with patch("dueltrace_web_bridge.discover_redux_pids",
                       return_value=[11,12]):
                self.bridge.set_emulator("pcsx-redux",8080)
                self.bridge.select_redux_process(12)
            with patch("dueltrace_web_bridge.discover_redux_pids",
                       return_value=[11]):
                result=self.bridge.get_emulator_status()
                self.assertIsNone(result["selectedReduxPid"])
                self.assertIsNone(self.bridge._redux_selected_pid)


if __name__=="__main__":
    unittest.main()
