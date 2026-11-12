"""Regressões para integrar a interface v0 ao motor real sem dados fictícios."""
from __future__ import annotations

import functools
import http.server
import http.client
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from auto_mods import ModCatalog, atomic_json, supported_for_runtime
from dueltrace_web_bridge import DueltraceWebBridge
from dueltrace_web_desktop import local_handler, trusted_window_url
from dueltrace_web_security import ProtectedDesktopApi
from scanner_multiiso import X15_SHA


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)
        self.catalog=ModCatalog(self.home)
        self.sha="a"*64
        self.analysis=self.home/"analises"/"synthetic"
        self.analysis.mkdir(parents=True)
        self.profile_path=self.home/"profiles"/self.sha[:16]/"profile.json"
        self.profile={
            "rom_sha256":self.sha,
            "scan_result_dir":str(self.analysis),
            "supported_features":{"cards":True,"art":True,"fusions":True,"composed_cards":True},
            "verified":{"cartas":"verificado"},
            "graphic_assets":{"frames":6,"composed_cards":7},
            "cards":[
                {"id":1,"name":"Carta comprovada","atk":1250,"def":1000,
                 "level":7,"description_text":"Descrição verificada",
                 "description_source":"SLUS_014.11:0x1B11F4",
                 "effect_text":"Texto inventado sem fonte"},
                {"id":2,"name":"Outra carta","atk":300,"def":800,
                 "effect_text":"Efeito com fonte","effect_source":"ROM-offset-auditado"},
                {"id":3,"name":"Terceira","atk":100,"def":200},
                {"id":4,"name":"Quarta","atk":300,"def":400},
                {"id":5,"name":"Quinta","atk":500,"def":600},
                {"id":7,"name":"Fusão","atk":2800,"def":2400},
                {"id":8,"name":"Fusão avançada","atk":3200,"def":2400},
            ],
            "fusion_recipes":[
                {"a":1,"b":2,"result":7,
                 "validation":"extraida_sete_bancos_consistentes"},
                {"a":7,"b":3,"result":8,
                 "validation":"observada_manualmente_no_jogo"},
            ],
        }
        atomic_json(self.profile_path,self.profile)
        self.entry={
            "sha256":self.sha,"source_path":str(self.home/"rom.iso"),
            "file_name":"Local Test.iso","profile_path":str(self.profile_path),
            "level":"conhecido_validado","approved":True,
            "features":supported_for_runtime(self.profile),
        }
        atomic_json(self.catalog.registry_file,{"schema":1,"entries":[self.entry]})
        atomic_json(self.catalog.active_file,{"sha256":self.sha})
        self.reader=Mock(return_value={
            "ready":True,"status":"Mão de teste","hand_ids":[1,2,3,4,5]})
        self.bridge=DueltraceWebBridge(self.catalog,ram_reader=self.reader)

    def test_alpha_fusions_extend_same_iso_without_overriding_curated_pairs(self):
        # Curated 1+2=7 and 7+3=8 survive. Unknown 2+3=8 is additive.
        # The contradictory 1+2=8 must NOT enter suggestions.
        candidates={"fusions":[
            {"a":1,"b":2,"result":8,"validation":"alpha_seven_matching_iso_banks"},
            {"a":1,"b":2,"result":7,"validation":"alpha_seven_matching_iso_banks"},
            {"a":2,"b":3,"result":8,"validation":"alpha_seven_matching_iso_banks"},
        ]}
        with patch.object(self.bridge,"_alpha_bundle",return_value=candidates):
            recipes,provisional=self.bridge._combined_fusion_recipes(
                self.sha,self.entry,self.profile)
            self.assertTrue(provisional)
            self.assertEqual(len(recipes),3)
            self.assertNotIn((1,2,8),[(r["a"],r["b"],r["result"]) for r in recipes])
            data=self.bridge.get_fusions("",0,50)
        self.assertTrue(data["provisional"])
        self.assertEqual(data["total"],3)
        self.assertTrue(all("nameResult" in r for r in data["rows"]))

    def test_card_fusions_match_exact_material_id_and_show_result_atk(self):
        candidates={"fusions":[
            {"a":2,"b":3,"result":8,"validation":"alpha_seven_matching_iso_banks"},
            {"a":1,"b":2,"result":8,"validation":"alpha_seven_matching_iso_banks"},
            {"a":2,"b":3,"result":8,"validation":"alpha_seven_matching_iso_banks"},
            {"a":7,"b":3,"result":8,"validation":"alpha_seven_matching_iso_banks"},
        ]}
        with patch.object(self.bridge,"_alpha_bundle",return_value=candidates):
            data=self.bridge.get_card_fusions(2,sort="atk")
            self.assertEqual(data["romSha"],self.sha)
            self.assertEqual(data["cardId"],2)
            self.assertTrue(data["available"])
            self.assertEqual(data["total"],2)
            # The curated 1+2=7 takes precedence over contradictory 1+2=8.
            self.assertEqual([r["resultId"] for r in data["rows"]],[8,7])
            self.assertEqual([r["atk"] for r in data["rows"]],[3200,2800])
            self.assertEqual([r["partnerId"] for r in data["rows"]],[3,1])
            self.assertFalse(any("source_path" in r for r in data["rows"]))
            second=self.bridge.get_card_fusions(2,offset=1,limit=1,sort="atk")
            self.assertEqual(second["total"],2)
            self.assertEqual(second["rows"][0]["resultId"],7)
            by_name=self.bridge.get_card_fusions(2,sort="name")
            self.assertEqual([r["resultId"] for r in by_name["rows"]],[7,8])
            no_material=self.bridge.get_card_fusions(5)
            self.assertEqual(no_material["rows"],[])
        self.assertEqual(data["provisional"],True)

    def test_card_fusion_bridge_rejects_invalid_inputs_and_enforces_token(self):
        for invalid in (0,-1,723,"2",True,None,{},[]):
            with self.subTest(card_id=invalid),self.assertRaises(ValueError):
                self.bridge.get_card_fusions(invalid)
        for invalid in (-1,1.5,"0",True):
            with self.subTest(offset=invalid),self.assertRaises(ValueError):
                self.bridge.get_card_fusions(2,offset=invalid)
        for invalid in (0,51,-1,"8"):
            with self.subTest(limit=invalid),self.assertRaises(ValueError):
                self.bridge.get_card_fusions(2,limit=invalid)
        with self.assertRaises(ValueError):
            self.bridge.get_card_fusions(2,sort="unknown")
        private=ProtectedDesktopApi(self.bridge,"k"*64)
        with self.assertRaises(PermissionError):
            private.get_card_fusions("invalid",2)
        data=private.get_card_fusions("k"*64,2)
        self.assertEqual(data["cardId"],2)
        self.assertEqual(data["romSha"],self.sha)

    def test_hide_fusion_preference_is_persisted_without_changing_emulator_settings(self):
        self.assertTrue(self.bridge.get_alpha_preferences()["fusionTipsVisible"])
        self.assertFalse(self.bridge.set_alpha_preferences(False)["fusionTipsVisible"])
        self.assertFalse(self.bridge.get_alpha_preferences()["fusionTipsVisible"])
        self.assertTrue(self.bridge.set_alpha_preferences(True)["fusionTipsVisible"])
        for invalid in (None,0,1,"false",{},[]):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                self.bridge.set_alpha_preferences(invalid)
        protected=ProtectedDesktopApi(self.bridge,"x"*64)
        with self.assertRaises(PermissionError):
            protected.set_alpha_preferences("unauthorized",False)
        self.assertTrue(protected.get_alpha_preferences("x"*64)["fusionTipsVisible"])

    def test_state_uses_local_profile_and_never_fabricates_effect(self):
        snapshot=self.bridge.get_state()
        self.assertEqual(snapshot["activeName"],"Local Test.iso")
        self.assertEqual(snapshot["fusionCount"],2)
        self.assertEqual(snapshot["cards"][0]["name"],"Carta comprovada")
        self.assertIsNone(snapshot["cards"][0]["effect"])
        self.assertEqual(snapshot["cards"][0]["description"],"Descrição verificada")
        self.assertEqual(snapshot["cards"][0]["level"],7)
        self.assertEqual(snapshot["cards"][0]["atk"],1250)
        self.assertEqual(snapshot["cards"][0]["def"],1000)
        self.assertEqual(snapshot["mods"][0]["frameStyles"],6)
        self.assertEqual(snapshot["mods"][0]["framedCards"],7)
        self.assertEqual(snapshot["cards"][0]["descriptionSource"],"SLUS_014.11:0x1B11F4")
        self.assertEqual(snapshot["cards"][1]["effect"],"Efeito com fonte")
        self.assertEqual(snapshot["cards"][1]["effectSource"],"ROM-offset-auditado")
        self.assertNotIn("source_path",str(snapshot))

    def test_forensic_private_upload_requires_explicit_action_and_current_sha(self):
        protected=ProtectedDesktopApi(self.bridge,"x"*64)
        image=self.home/"rom.iso"
        image.write_bytes(b"synthetic local ROM file")
        report={"schema":1,"romFingerprint":self.sha[:12],
                "exactSha256Matched":True,"fileSizeBytes":image.stat().st_size}
        target=self.home/"iso_forensics"/(self.sha+".json")
        atomic_json(target,report)
        sync=Mock()
        sync.upload_forensic.return_value={
            "synced":True,"fingerprint":self.sha[:12],
            "kind":"iso_forensic_audit"}
        self.bridge._private_evidence_sync=sync
        with self.assertRaises(PermissionError):
            protected.upload_iso_forensic("not-authorized",self.sha)
        sync.upload_forensic.assert_not_called()
        with patch("scanner_multiiso.sha256",return_value="b"*64):
            with self.assertRaises(ValueError):
                protected.upload_iso_forensic("x"*64,self.sha)
        sync.upload_forensic.assert_not_called()
        with patch("scanner_multiiso.sha256",return_value=self.sha):
            result=protected.upload_iso_forensic("x"*64,self.sha)
        self.assertTrue(result["synced"])
        sync.upload_forensic.assert_called_once_with(report)

    def test_iso_forensic_lab_requires_auth_and_persists_only_safe_summary(self):
        import json
        protected=ProtectedDesktopApi(self.bridge,"x"*64)
        with self.assertRaises(PermissionError):
            protected.audit_mod_iso("not-authorized", self.sha)
        with self.assertRaises(ValueError):
            protected.audit_mod_iso("x"*64,"../secret")
        iso=self.home/"rom.iso"
        iso.write_bytes(b"test fake ISO content")
        sample={
            "schema":1,"subject":"DUELTRACE ISO Forensic Lab",
            "romFingerprint":self.sha[:12],
            "exactSha256Matched":True,
            "cards":{"count":722},
            "opponents":{"count":39,"inGameIdentityVerified":False},
            "mayActivateDrops":False,"networkTransmission":False,
        }
        with patch("dueltrace_iso_forensic_lab.inspect_iso",
                   return_value=sample) as probe:
            response=protected.audit_mod_iso("x"*64,self.sha)
            probe.assert_called_once_with(iso.resolve(),self.sha)
        self.assertEqual(response["cards"]["count"],722)
        saved=self.home/"iso_forensics"/(self.sha+".json")
        self.assertTrue(saved.is_file())
        self.assertEqual(json.loads(saved.read_text())["cards"]["count"],722)
        self.assertFalse((self.home/"live_diagnostics"/"private_sync_settings.json").exists())
        self.assertFalse(response["networkTransmission"])
        self.assertNotIn(str(iso),str(response))

    def test_compare_registered_isos_is_local_authorized_and_read_only(self):
        protected = ProtectedDesktopApi(self.bridge, "x"*64)
        with self.assertRaises(PermissionError):
            protected.compare_mod_layouts("bad-token", self.sha)
        import json
        self.analysis.joinpath("relatorio.json").write_text(json.dumps({
            "sha256": self.sha, "cartas": 722, "oponentes": 39,
            "tabelas_drops": 117, "opponent_identification": "verificado",
            "tipo_setor": 2352, "arquivo": "PRIVATE_REFERENCE.iso",
        }), encoding="utf-8")
        other_sha = "b"*64
        other_analysis = self.home/"analises"/"gog"
        other_analysis.mkdir(parents=True)
        other_profile_path = self.home/"profiles"/other_sha[:16]/"profile.json"
        other_profile = {"rom_sha256":other_sha,
                         "scan_result_dir":str(other_analysis),
                         "supported_features":{}, "cards":[]}
        atomic_json(other_profile_path,other_profile)
        atomic_json(other_analysis/"relatorio.json",{
            "sha256":other_sha,"cartas":722,"oponentes":39,
            "tabelas_drops":117,"tipo_setor":2352,
            "opponent_identification":"extraidos_estruturalmente",
            "independent_opponent_discovery":{
                "inlineFdEvidence":{"unique39RecordRun":True}},
            "mod_family_evidence":{"clusters":[{
                "consecutiveBlockCount":40,"possible39BlockWindows":2}]},
            "arquivo":"PRIVATE_GOG_MOD.iso",
        })
        atomic_json(self.catalog.registry_file,{"schema":1,"entries":[
            self.entry,{"sha256":other_sha,
                        "profile_path":str(other_profile_path),"approved":False,
                        "features":{},"level":"parcial_revisar"}]})
        result=protected.compare_mod_layouts("x"*64,self.sha)
        self.assertEqual(result["comparedProfiles"],1)
        self.assertEqual(result["skippedProfiles"],0)
        self.assertEqual(result["compared"][0]["romFingerprint"],"b"*12)
        difference_stages={item["stage"] for item in result["compared"][0]["differences"]}
        self.assertIn("opponents",difference_stages)
        self.assertIn("resources",difference_stages)
        serialized=json.dumps(result)
        self.assertNotIn("PRIVATE_",serialized)
        self.assertNotIn(str(self.home),serialized)
        self.assertFalse(result["automaticallyActivatesFeatures"])
        self.assertFalse(result["compared"][0]["inGameValidated"])

    def test_opt_in_live_diagnostics_sampling_and_sanitized_export(self):
        import json
        from time import monotonic
        protected=ProtectedDesktopApi(self.bridge,"x"*64)
        with self.assertRaises(PermissionError):
            protected.start_live_diagnostics("wrong")
        with self.assertRaises(PermissionError):
            protected.export_live_diagnostics("wrong")
        self.assertFalse(protected.get_live_diagnostics_status("x"*64)["running"])
        with patch("dueltrace_web_bridge.threading.Thread") as mock_thread:
            started=protected.start_live_diagnostics("x"*64)
            self.assertTrue(started["running"])
            mock_thread.return_value.start.assert_called_once()
            self.assertFalse(started["networkTransmission"])
            with patch.object(self.bridge,"get_hand",return_value={
                        "ready":True,"hand":[
                            {"id":1,"name":"PRIVATE_ROM_NAME"},
                            {"id":2},{"id":3},{"id":4},{"id":5}],
                        "status":"PRIVATE_PATH",
                    }), patch.object(self.bridge,"get_live_opponent",return_value={
                        "ready":False,"status":"ram_mapping_not_validated",
                        "memoryRegionsExamined":927,
                        "validationBreakdown":{
                            "implausibleDrawHistory":27,
                            "rawBytes":"SECRET_RAM_DATA",
                        },
                        "privateHostAddress":"0xDEADBEEF",
                    }):
                self.bridge._rank_last_snapshot={
                    "rom_sha256":self.sha,"monotonic_at":monotonic(),
                    "score":86,"category":"A-POW",
                    "rawData":"PRIVATE_RANK_DUMP",
                }
                self.assertTrue(self.bridge._collect_live_diagnostics_once(
                    self.bridge._live_diagnostics))
                self.assertTrue(self.bridge._collect_live_diagnostics_once(
                    self.bridge._live_diagnostics))
            status=protected.get_live_diagnostics_status("x"*64)
            self.assertEqual(status["sampleCount"],2)
            self.assertEqual(status["changeCount"],1)
            exported=protected.export_live_diagnostics("x"*64)
            data=json.loads(exported)
            self.assertEqual(data["events"][0]["data"]["hand"]["ids"],[1,2,3,4,5])
            self.assertEqual(data["events"][0]["data"]["rank"]["scoreCandidate"],86)
            self.assertEqual(
                data["events"][0]["data"]["opponent"]["rejectionCounts"]
                ["implausibleDrawHistory"],27)
            for forbidden in (
                "PRIVATE_ROM_NAME","PRIVATE_PATH","PRIVATE_RANK_DUMP",
                "SECRET_RAM_DATA","0xDEADBEEF","Local Test.iso"):
                self.assertNotIn(forbidden,exported)
            self.assertFalse(data["networkTransmission"])
            self.assertFalse(data["mayActivateDrops"])
            self.assertFalse(data["mayActivateRank"])
            self.assertFalse(protected.stop_live_diagnostics("x"*64)["running"])
            self.assertFalse(
                self.bridge._collect_live_diagnostics_once(self.bridge._live_diagnostics))

    def test_private_evidence_sync_requires_capability_and_explicit_consent(self):
        from dueltrace_private_evidence_sync import EvidenceSyncError
        protected=ProtectedDesktopApi(self.bridge,"x"*64)
        fake=Mock()
        fake.status.return_value={
            "enabled":False,"repository":None,"lastSyncedAtUTC":None,
            "lastError":None,"remoteIsChatGPTConnection":False}
        fake.configure.return_value={
            "enabled":True,"repository":"tester/private-evidence",
            "lastSyncedAtUTC":None,"lastError":None,
            "remoteIsChatGPTConnection":False}
        fake.disable.return_value=fake.status.return_value
        self.bridge._private_evidence_sync=fake
        with self.assertRaises(PermissionError):
            protected.configure_private_evidence_sync(
                "wrong","tester/private-evidence","secret",True)
        with self.assertRaises(PermissionError):
            protected.disable_private_evidence_sync("wrong")
        with self.assertRaises(PermissionError):
            protected.get_private_evidence_sync_status("wrong")
        self.assertFalse(protected.get_private_evidence_sync_status("x"*64)["enabled"])
        configured=protected.configure_private_evidence_sync(
            "x"*64,"tester/private-evidence","secret",True)
        self.assertTrue(configured["enabled"])
        fake.configure.assert_called_once_with(
            "tester/private-evidence","secret",True)
        self.assertNotIn("secret",str(configured))
        self.assertFalse(protected.disable_private_evidence_sync("x"*64)["enabled"])

    def test_live_opponent_probe_requires_token_and_never_promotes(self):
        native={"ready":True,"status":"runtime_id_candidate",
                "runtimeOpponentId":11,
                "mappingValidatedByIndependentFields":True,
                "runtimeIdVerifiedForMod":False,
                "opponentNameVerified":False,
                "romIdentityVerified":False,
                "mayActivateDrops":False,"mayActivateRank":False}
        protected=ProtectedDesktopApi(self.bridge,"x"*64)
        with self.assertRaises(PermissionError):
            protected.get_live_opponent("wrong")
        with patch("dueltrace_live_opponent.probe_live_opponent",return_value=native) as probe:
            result=protected.get_live_opponent("x"*64)
            probe.assert_called_once()
            self.assertEqual(result["runtimeOpponentId"],11)
            self.assertFalse(result["romIdentityVerified"])
            self.assertFalse(result["mayActivateDrops"])
            self.assertFalse(result["opponentNameVerified"])
            self.assertFalse(result["mayActivateRank"])
            self.assertEqual(self.catalog.current()["sha256"],self.sha)

    def test_runtime_ids_auto_log_only_for_matching_launched_session(self):
        from auto_mods import load_json
        self.bridge._process=Mock()
        self.bridge._process.pid=4242
        self.bridge._process.poll.return_value=None
        self.bridge._launched_rom_sha=self.sha
        path=self.home/"runtime_opponent_observations"/(self.sha+".json")
        provisional={
            "ready":True,"status":"runtime_id_candidate",
            "runtimeOpponentId":11,
            "runtimeIdVerifiedForMod":False,
            "romIdentityVerified":False,
            "opponentNameVerified":False,
            "mayActivateDrops":False,"mayActivateRank":False,
        }
        with patch("dueltrace_live_opponent.probe_live_opponent",return_value=provisional):
            first=self.bridge.get_live_opponent()
            second=self.bridge.get_live_opponent()
        self.assertTrue(first["autoLogged"])
        self.assertFalse(second["autoLogged"])
        saved=load_json(path,{})
        self.assertEqual(len(saved["events"]),1)
        self.assertEqual(saved["events"][0]["opponentRuntimeId"],11)
        self.assertFalse(saved["verifiedForGame"])
        self.assertNotIn("memory",str(saved).casefold())
        self.bridge._launched_rom_sha="b"*64
        different={**provisional,"runtimeOpponentId":12}
        with patch("dueltrace_live_opponent.probe_live_opponent",return_value=different):
            ignored=self.bridge.get_live_opponent()
        self.assertFalse(ignored["autoLogged"])
        self.assertEqual(len(load_json(path,{})["events"]),1)

    def test_family_summary_exposes_only_structural_counts(self):
        # A 40-block family has two possible 39-opponent windows, NOT
        # verified 40 opponents or unlocked drop tables.
        meta = {
            "scan_parser_revision":29,
            "mod_family_evidence":{
                "state":"single_family_unmapped_windows",
                "candidateCount":2, "scanComplete":True,
                "ambiguous39BlockWindows":True,
                "clusters":[{
                    "consecutiveBlockCount":40,
                    "possible39BlockWindows":2,
                    "resource":"/private/rom.bin",
                    "rawBytes":"NEVER_EXPOSE_BIN",
                }],
                "privateFile":"PRIVATE_ISO_NAME",
            },
        }
        atomic_json(self.analysis/"relatorio.json",meta)
        mod = self.bridge.get_state()["mods"][0]
        family = mod["modFamilyEvidence"]
        self.assertEqual(family["scanRevision"],29)
        self.assertEqual(family["consecutiveBlocks"],40)
        self.assertEqual(family["structuralMatrices"],160)
        self.assertEqual(family["possible39Windows"],2)
        self.assertTrue(family["ambiguous"])
        self.assertFalse(family["inGameVerified"])
        self.assertFalse(family["mayActivateDrops"])
        self.assertFalse(family["mayActivateRank"])
        self.assertNotIn("NEVER_EXPOSE_BIN",str(mod))
        self.assertNotIn("PRIVATE_ISO_NAME",str(mod))
        self.assertNotIn("/private/rom.bin",str(mod))
        self.assertEqual(mod["dropEntries"],0)

    def test_family_summary_rejects_old_revision_and_outside_folder(self):
        meta = {"scan_parser_revision":28,"mod_family_evidence":{
            "state":"unique_structural_candidate","candidateCount":1,
            "clusters":[{"consecutiveBlockCount":39,"possible39BlockWindows":1}]}}
        atomic_json(self.analysis/"relatorio.json",meta)
        self.assertIsNone(self.bridge.get_state()["mods"][0]["modFamilyEvidence"])
        meta["scan_parser_revision"]=29
        atomic_json(self.analysis/"relatorio.json",meta)
        self.assertEqual(
            self.bridge.get_state()["mods"][0]["modFamilyEvidence"]["consecutiveBlocks"],39)
        outside=self.home/"private"/"analysis"
        outside.mkdir(parents=True)
        atomic_json(outside/"relatorio.json",meta)
        self.profile["scan_result_dir"]=str(outside)
        atomic_json(self.profile_path,self.profile)
        self.assertIsNone(self.bridge.get_state()["mods"][0]["modFamilyEvidence"])

    def test_window_duel_evidence_can_be_recorded_without_activating_drops(self):
        import struct
        from dueltrace_mod_family_probe import MATRIX_BYTES
        from unittest.mock import patch
        base, step, stride = 0x2000, 0x1800, 0x5b4
        data = bytearray(base + 40*step)
        for i in range(40):
            offset=base+i*step
            for g in range(4):
                arr=[0]*722
                a=(i*19+g*37)%722
                arr[a] = 100
                arr[(a+210)%722]=300
                arr[(a+410)%722]=1648
                struct.pack_into("<722H",data,offset+g*stride,*arr)
            data[offset+4*stride:offset+4*stride+200]=b"\xA5"*200
            data[offset+4*stride+200:offset+step]=b"\xff"*104
        blob=bytes(data)
        family={
            "state":"single_family_unmapped_windows",
            "candidateCount":2,"scanComplete":True,
            "clusters":[{
                "firstBlockOffset":base,
                "consecutiveBlockCount":40,
                "opponentStep":step,"matrixStride":stride,
                "encoding":"plain",
            }],
        }
        self.profile["supported_features"]["opponents"]=True
        self.profile["verified"]["oponentes"]="extraidos_estruturalmente"
        self.profile["opponents"]=[{"id":i, "name":f"Adversário {i}"}
                                   for i in range(1,40)]
        present = {row["id"] for row in self.profile["cards"]}
        self.profile["cards"].extend(
            {"id": i, "name":f"Carta validada {i}", "atk":i*2,"def":i*3}
            for i in range(1,723) if i not in present)
        atomic_json(self.profile_path,self.profile)
        choices=self.bridge.get_state()["mods"][0]["structuralOpponentChoices"]
        self.assertEqual(len(choices),39)
        self.assertEqual(choices[0],{"slot":1,"name":"Adversário 1"})
        atomic_json(self.analysis/"relatorio.json",{
            "sha256":self.sha,"scan_parser_revision":29,
            "mod_family_audit":{"resourcesScanned":[{
                "resource":"G0SD/MOD_DATA.BIN", "weightFamily":family,
            }]},
        })
        source=self.home/"rom.iso"
        source.write_bytes(b"synthetic ISO data for mocked Disc")
        class Disc:
            def __init__(self,path):
                self.files={"G0SD/MOD_DATA.BIN":(4,len(blob))}
            def get(self,name):
                if name != "G0SD/MOD_DATA.BIN":
                    raise AssertionError("Unexpected resource")
                return blob
            def close(self):pass
        protected=ProtectedDesktopApi(self.bridge,"x"*64)
        with self.assertRaises(PermissionError):
            protected.record_window_observation("wrong",self.sha,1,"S-POW",38,[1])
        with patch("scanner_multiiso.sha256",return_value=self.sha), patch(
                "scanner_multiiso.Disc",Disc):
            with self.assertRaises(PermissionError):
                protected.get_candidate_matrix("wrong",self.sha,0,1,"38",0,10)
            preview=protected.get_candidate_matrix(
                "x"*64,self.sha,0,1,"38",0,10)
            self.assertTrue(preview["available"])
            self.assertEqual(preview["blockCount"],40)
            self.assertEqual(preview["rows"][0]["id"],38)
            self.assertEqual(preview["rows"][0]["weight"],100)
            self.assertFalse(preview["mayActivateDrops"])
            self.assertFalse(preview["rankGroupLabelsVerified"])
            suggested=protected.get_candidate_matrix("x"*64,self.sha,-1,1)
            self.assertTrue(suggested["available"])
            self.assertTrue(suggested["autoSelected"])
            result=protected.record_window_observation(
                "x"*64,self.sha,1,"S-POW",38,[1])
            self.assertEqual(result["observationCount"],1)
            self.assertEqual(result["analysis"]["candidateWindowHint"],0)
            self.assertEqual(result["analysis"]["compatibleWindowCount"],1)
            self.assertFalse(result["mayActivateDrops"])
            self.assertFalse(result["mayActivateRank"])
            self.assertFalse(result["inGameVerified"])
            self.assertEqual(
                protected.get_window_observations("x"*64,self.sha)
                ["observationCount"],1)
            saved=protected.get_window_observations("x"*64,self.sha)
            self.assertEqual(saved["entries"],[{
                "index":1,"opponentSlot":1,"rank":"S-POW",
                "rewardCardId":38,"playedCardIds":[1],
            }])
            self.assertEqual(saved["analysis"]["windows"][1]["deckContradictions"],1)
            # A second record must be visible; undo only removes the last,
            # then recomputes the original single-duel correlation.
            duplicate=protected.record_window_observation(
                "x"*64,self.sha,1,"S-POW",38,[1])
            self.assertEqual(duplicate["observationCount"],2)
            with self.assertRaises(PermissionError):
                protected.undo_last_window_observation("wrong",self.sha)
            undone=protected.undo_last_window_observation("x"*64,self.sha)
            self.assertEqual(undone["observationCount"],1)
            self.assertEqual(undone["analysis"]["candidateWindowHint"],0)
            self.assertEqual(undone["entries"],saved["entries"])
            undone_empty=protected.undo_last_window_observation("x"*64,self.sha)
            self.assertEqual(undone_empty["observationCount"],0)
            self.assertEqual(undone_empty["analysis"]["windowCount"],2)
            self.assertEqual(undone_empty["analysis"]["status"],"awaiting_independent_duels")
            with self.assertRaises(ValueError):
                protected.undo_last_window_observation("x"*64,self.sha)
            restored=protected.record_window_observation(
                "x"*64,self.sha,1,"S-POW",38,[1])
            self.assertEqual(restored["observationCount"],1)
            with self.assertRaises(ValueError):
                protected.record_window_observation(
                    "x"*64,self.sha,0,"S-POW",38,[1])
            with self.assertRaises(ValueError):
                protected.record_window_observation(
                    "x"*64,self.sha,1,"S-POW",38,[1,1])
        self.assertFalse(self.catalog.profile_for(self.entry)
                         .get("supported_features",{}).get("drops",False))
        self.assertNotIn("rom.iso",str(result))
        self.assertNotIn("MOD_DATA.BIN",str(result))
        self.assertNotIn("source_path",str(result))
        self.assertFalse((self.home/"rank_observations"/(self.sha+".json")).exists())
        # Regression for the REAL GOG scan path: scanner revision 29
        # stores mod_family_evidence on selected WA resources, NOT audit.
        import hashlib
        obs_path=self.home/"window_observations"/(self.sha+".json")
        obs_path.unlink()
        direct_meta={
            "sha256":self.sha, "scan_parser_revision":29,
            "mod_family_evidence":family,
            "wa_resource_selection":{"source":"G0SD/MOD_DATA.BIN"},
            "hash_wa":hashlib.sha256(blob).hexdigest(),
        }
        atomic_json(self.analysis/"relatorio.json",direct_meta)
        with patch("scanner_multiiso.sha256",return_value=self.sha),patch(
                "scanner_multiiso.Disc",Disc):
            second=protected.record_window_observation(
                "x"*64,self.sha,1,"B-POW",38,[1])
            self.assertEqual(second["observationCount"],1)
            self.assertEqual(second["analysis"]["windowCount"],2)
            self.assertFalse(second["mayActivateDrops"])
            obs_path.unlink()
            direct_meta["hash_wa"]="0"*64
            atomic_json(self.analysis/"relatorio.json",direct_meta)
            with self.assertRaisesRegex(ValueError,"Contêiner mudou"):
                protected.record_window_observation(
                    "x"*64,self.sha,1,"B-POW",38,[1])
            self.assertFalse(obs_path.exists())
            direct_meta["hash_wa"]=hashlib.sha256(blob).hexdigest()
            direct_meta["wa_resource_selection"]["source"]="G0SD/OTHER.BIN"
            atomic_json(self.analysis/"relatorio.json",direct_meta)
            with self.assertRaisesRegex(ValueError,"Contêiner original não encontrado"):
                protected.record_window_observation(
                    "x"*64,self.sha,1,"B-POW",38,[1])
            self.assertFalse(obs_path.exists())
        # Never leak names from unrelated mods or arbitrary profile IDs.
        self.profile["opponents"][0]["id"]=999
        atomic_json(self.profile_path,self.profile)
        self.assertEqual(self.bridge.get_state()["mods"][0]["structuralOpponentChoices"],[])


    def test_drops_from_active_iso_are_paged_and_authenticated(self):
        groups=["TABELA_1_RANK_DESCONHECIDO","TABELA_2_RANK_DESCONHECIDO",
                "TABELA_3_RANK_DESCONHECIDO"]
        known_card_ids={card["id"] for card in self.profile["cards"]}
        self.profile["cards"].extend(
            {"id":cid,"name":f"Carta sintética {cid}","atk":1000,"def":800}
            for cid in range(1,723) if cid not in known_card_ids)
        self.profile["cards"].sort(key=lambda card:card["id"])
        self.profile["supported_features"]["drops"]=True
        self.profile["verified"]["tabelas_drops"]="verificado"
        self.profile["verified"]["oponentes"]="verificado"
        self.profile["drop_group_labels"]=groups
        self.profile["opponents"]=[{"id":i,"name":f"Adversário {i}"} for i in range(1,40)]
        self.profile["drops"]=[
            {"opponent_id":i,"group":group,"card_id":j+1,"weight":2048,
             "source_offset":0xE9B000+(i-1)*0x1800+(j+1)*0x5B4}
            for i in range(1,40) for j,group in enumerate(groups)]
        atomic_json(self.profile_path,self.profile)
        page=self.bridge.get_drops(2,groups[1],"",0,20)
        self.assertTrue(page["available"])
        self.assertEqual(page["total"],1)
        self.assertEqual(page["rows"][0]["opponentName"],"Adversário 2")
        self.assertEqual(page["rows"][0]["cardId"],2)
        self.assertEqual(page["rows"][0]["chancePercent"],100.0)
        self.assertNotIn("source_path",str(page))
        protected=ProtectedDesktopApi(self.bridge,"x"*64)
        with self.assertRaises(PermissionError):
            protected.get_drops("not-authorized",2,groups[1],"",0,20)
        self.assertEqual(protected.get_drops("x"*64,2,groups[1],"",0,20)["total"],1)
        by_card=self.bridge.get_card_drop_sources(2)
        self.assertTrue(by_card["available"])
        self.assertEqual(by_card["cardId"],2)
        self.assertEqual(by_card["romSha"],self.sha)
        self.assertEqual(by_card["total"],39)
        self.assertEqual(len(by_card["rows"]),39)
        self.assertTrue(all(r["cardId"]==2 for r in by_card["rows"]))
        with self.assertRaises(PermissionError):
            protected.get_card_drop_sources("invalid",2)
        self.assertEqual(protected.get_card_drop_sources("x"*64,2)["total"],39)
        with self.assertRaises(PermissionError):
            protected.record_duel_result("invalid",2,"Z-POW",2,95)
        evidence=protected.record_duel_result("x"*64,2,"S-POW",2,95)
        self.assertEqual(evidence["observations"],1)
        evidence=protected.record_duel_result("x"*64,3,"A-POW",2,94)
        self.assertEqual(evidence["observations"],2)
        self.assertEqual(evidence["suspectedMappings"]["S/A POW"]["group"],groups[1])
        self.assertEqual(protected.get_duel_evidence("x"*64)["observations"],2)

    def test_offline_rank_report_saved_only_as_json_and_never_overwritten(self):
        import json
        report_path=self.home/"auditoria-rank.json"
        self.profile["token"]="PRIVATE_TOKEN_SHOULD_NOT_APPEAR"
        atomic_json(self.profile_path,self.profile)
        self.bridge._file_picker=lambda kind: [str(report_path)] if kind=="rank_report" else []
        protected=ProtectedDesktopApi(self.bridge,"x"*64)
        with self.assertRaises(PermissionError):
            protected.export_rank_audit("wrong")
        result=protected.export_rank_audit("x"*64)
        self.assertFalse(result["cancelled"])
        saved=json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["rom_sha256"],self.sha)
        self.assertNotIn("PRIVATE_TOKEN",report_path.read_text(encoding="utf-8"))
        self.assertNotIn(str(self.home),report_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["report_sha256"],result["reportSha256"])
        with self.assertRaises(FileExistsError):
            self.bridge.export_rank_audit()
        self.assertEqual(json.loads(report_path.read_text(encoding="utf-8")),saved)

    def test_live_hand_uses_existing_fusion_engine(self):
        result=self.bridge.get_hand()
        self.assertTrue(result["ready"])
        self.assertEqual(len(result["hand"]),5)
        self.assertEqual(result["pairs"][0]["result"],7)
        self.assertEqual(result["chains"][0]["result"],8)
        self.reader.assert_called_once_with(preferred_pid=None)

    def test_dashboard_fusions_are_cached_until_hand_changes(self):
        """Painel atualiza a mão em 1,5 s sem recalcular cadeias idênticas."""
        from dueltrace_web_bridge import plan_fusion_chains as real_planner
        with patch("dueltrace_web_bridge.plan_fusion_chains",wraps=real_planner) as planner:
            first=self.bridge.get_hand()
            second=self.bridge.get_hand()
            self.assertEqual(first["hand"],second["hand"])
            self.assertEqual(first["pairs"],second["pairs"])
            self.assertEqual(first["chains"],second["chains"])
            self.assertEqual(planner.call_count,1)
            self.reader.return_value={
                "ready":True,"status":"Nova mão","hand_ids":[1,2,3,4,7]}
            changed=self.bridge.get_hand()
            self.assertTrue(changed["ready"])
            self.assertEqual(changed["hand"][4]["id"],7)
            self.assertEqual(planner.call_count,2)
            self.bridge.get_hand()
            self.assertEqual(planner.call_count,2)

    def test_manual_rank_available_when_ram_is_unverified(self):
        """O painel manual não exige RAM nem aceita score de ISO trocada."""
        from dueltrace_spoils_manual import calculate_manual_spoils
        counters={
            "turns":5,"effective_attacks":1,"defense_wins":0,
            "face_down":3,"spells":0,"traps":0,"cards_used":13,
            "remaining_lp":9500,"fusions":3,"equips":0,
        }
        self.bridge._rank_reader=Mock(side_effect=AssertionError("RAM não deve ser lida"))
        self.bridge._rank_mod_reader=Mock(side_effect=AssertionError("RAM não deve ser lida"))
        observed=self.bridge.calculate_spoils(counters,"lp")
        self.assertEqual(observed["score"],76)
        self.assertEqual(observed["category"],"B-POW")
        self.assertEqual(observed["rankSystem"],"classic")
        self.assertFalse(observed["verifiedInEmulator"])
        self.assertEqual(observed,calculate_manual_spoils(counters,"lp",self.sha))
        protected=ProtectedDesktopApi(self.bridge,"x"*64)
        with self.assertRaises(PermissionError):
            protected.calculate_spoils("invalid",counters,"lp")
        self.assertEqual(protected.calculate_spoils("x"*64,counters,"lp"),observed)
        self.bridge._rank_reader.assert_not_called()
        self.bridge._rank_mod_reader.assert_not_called()

    def test_manual_rank_without_active_iso_uses_explicit_reference_not_a_fake_mod(self):
        counters={
            "turns":5,"effective_attacks":1,"defense_wins":0,
            "face_down":3,"spells":0,"traps":0,"cards_used":13,
            "remaining_lp":9500,"fusions":3,"equips":0,
        }
        self.catalog.active_file.unlink()
        self.bridge._rank_reader=Mock(side_effect=AssertionError("RAM não deve ser lida"))
        classic=self.bridge.calculate_spoils(counters,"lp","classic")
        x15=self.bridge.calculate_spoils(counters,"lp","x15")
        self.assertEqual((classic["score"],classic["category"]),(76,"B-POW"))
        self.assertEqual((x15["score"],x15["category"]),(76,"S-POW"))
        self.assertTrue(classic["referenceOnly"])
        self.assertTrue(x15["referenceOnly"])
        self.assertIn("sem ISO",classic["note"])
        with self.assertRaises(ValueError):
            self.bridge.calculate_spoils(counters,"lp","invalid")
        self.bridge._rank_reader.assert_not_called()

    def test_unverified_iso_requires_explicit_opt_in_and_two_real_ram_transitions(self):
        counters={
            "turns":1,"effective_attacks":0,"defense_wins":0,
            "face_down":0,"spells":0,"traps":0,"cards_used":0,
            "remaining_lp":8000,"fusions":0,"equips":0,
        }
        self.bridge._rank_reader=Mock(return_value={
            "ready":True,"status":"Candidato antigo legível",
            "pid":4321,"counters":counters})
        self.assertEqual(self.bridge.get_rank()["state"],"unsupported")
        self.bridge._rank_reader.assert_not_called()
        protected=ProtectedDesktopApi(self.bridge,"x"*64)
        with self.assertRaises(PermissionError):
            protected.set_rank_experimental("invalid",True)
        with self.assertRaises(ValueError):
            protected.set_rank_experimental("x"*64,"sim")
        self.assertTrue(protected.set_rank_experimental("x"*64,True)["enabled"])
        first=protected.get_rank("x"*64)
        self.assertEqual(first["state"],"needs_lp_confirmation")
        self.assertIsNone(first["score"])
        self.assertEqual(first["sourceMode"],"experimental")
        confirmed=protected.confirm_rank_lp("x"*64,8000)
        self.assertEqual(confirmed["state"],"needs_ram_validation")
        self.assertEqual(confirmed["validationProgress"],0)
        counters["effective_attacks"]=1
        progress=protected.get_rank("x"*64)
        self.assertEqual(progress["state"],"needs_ram_validation")
        self.assertEqual(progress["validationProgress"],1)
        counters["turns"]=2
        calculated=protected.get_rank("x"*64)
        self.assertTrue(calculated["ready"])
        self.assertEqual(calculated["sourceMode"],"experimental")
        self.assertEqual(calculated["rankSystem"],"classic")
        self.assertIsInstance(calculated["score"],int)
        self.assertIsNone(self.bridge._rank_last_snapshot)
        with self.assertRaises(ValueError):
            self.bridge.capture_rank_prediction()
        self.assertFalse(protected.set_rank_experimental("x"*64,False)["enabled"])
        self.assertEqual(protected.get_rank("x"*64)["state"],"unsupported")

    def test_experimental_rank_cannot_survive_mod_activation(self):
        self.assertTrue(self.bridge.set_rank_experimental(True)["enabled"])
        self.assertEqual(self.bridge._rank_experimental_sha,self.sha)
        self.bridge.activate_mod(self.sha,False)
        self.assertIsNone(self.bridge._rank_experimental_sha)
        self.assertEqual(self.bridge.get_rank()["state"],"unsupported")

    def test_unmapped_rank_never_reads_presumed_legacy_address(self):
        reader=Mock(return_value={"ready":True,"pid":1234,
                                  "counters":{"remaining_lp":8000}})
        self.bridge._rank_reader=reader
        self.bridge._rank_mod_reader=Mock()
        state=self.bridge.get_rank()
        self.assertFalse(state["ready"])
        self.assertEqual(state["state"],"unsupported")
        self.assertEqual(state["rankSystem"],"classic")
        self.assertIsNone(state["score"])
        self.assertIsNone(state["category"])
        self.assertIsNone(state["counters"])
        reader.assert_not_called()
        self.bridge._rank_mod_reader.assert_not_called()

    def test_hand_error_does_not_keep_previous_cards(self):
        self.bridge.get_hand()
        self.reader.return_value={"ready":False,"status":"Sem ePSXe",
                                  "hand_ids":None}
        result=self.bridge.get_hand()
        self.assertFalse(result["ready"])
        self.assertEqual(result["hand"],[])
        self.assertEqual(result["pairs"],[])
        self.assertEqual(result["chains"],[])

    def test_fusions_are_paginated_and_source_labeled(self):
        first=self.bridge.get_fusions("",0,1)
        self.assertEqual(first["total"],2)
        self.assertEqual(len(first["rows"]),1)
        self.assertEqual(self.bridge.get_fusions("Fusão avançada",0,20)["total"],1)
        with self.assertRaises(ValueError):
            self.bridge.get_fusions("",0,100000)

    def test_fusion_searches_material_effect_and_description_without_other_mods(self):
        self.profile["cards"][0]["effect_text"]="Poder da floresta antiga"
        self.profile["cards"][0]["effect_source"]="SLUS:test"
        self.profile["cards"][1]["description_text"]="Espírito do relâmpago"
        self.profile["cards"][5]["description_text"]="Flor lunar secreta"
        atomic_json(self.profile_path,self.profile)
        self.assertEqual(self.bridge.get_fusions("floresta antiga",0,20)["total"],1)
        self.assertEqual(self.bridge.get_fusions("RELÂMPAGO",0,20)["total"],1)
        self.assertEqual(self.bridge.get_fusions("flor lunar secreta",0,20)["total"],2)
        self.assertEqual(self.bridge.get_fusions("carta ausente",0,20)["total"],0)

    def test_fusions_can_search_only_result_or_either_material(self):
        # Perfil sintético: 1 + 2 -> 7 e 7 + 3 -> 8.
        result=self.bridge.get_fusions("Fusão avançada",0,20,
                                      search_scope="result")
        self.assertEqual(result["total"],1)
        self.assertEqual(result["rows"][0]["result"],8)
        self.assertEqual(self.bridge.get_fusions("Fusão avançada",0,20,
                         search_scope="material")["total"],0)

        materials=self.bridge.get_fusions("Carta comprovada",0,20,
                                          search_scope="material")
        self.assertEqual(materials["total"],1)
        self.assertEqual(materials["rows"][0]["result"],7)
        self.assertEqual(self.bridge.get_fusions("Carta comprovada",0,20,
                         search_scope="result")["total"],0)

        # Material A e B são equivalentes; IDs não vazam de outro papel.
        self.assertEqual(self.bridge.get_fusions("Outra carta",0,20,
                         search_scope="material")["total"],1)
        self.assertEqual(self.bridge.get_fusions("#7",0,20,
                         search_scope="material")["rows"][0]["result"],8)
        self.assertEqual(self.bridge.get_fusions("7",0,20,
                         search_scope="result")["rows"][0]["result"],7)
        self.assertEqual(self.bridge.get_fusions("#7",0,20,
                         search_scope="result")["total"],1)
        # ID que só existe como resultado não deve entrar no filtro de material.
        self.assertEqual(self.bridge.get_fusions("#8",0,20,
                         search_scope="result")["total"],1)
        self.assertEqual(self.bridge.get_fusions("#8",0,20,
                         search_scope="material")["total"],0)
        protected=ProtectedDesktopApi(self.bridge,"s"*64)
        self.assertEqual(protected.get_fusions("s"*64,"#7",0,20,
                         "id","","material")["rows"][0]["result"],8)
        with self.assertRaises(PermissionError):
            protected.get_fusions("bad","#7",0,20,"id","","material")

        # Resultado e material com o mesmo nome devem continuar distintos.
        self.assertEqual(self.bridge.get_fusions("FUSÃO",0,20,
                         search_scope="result")["total"],2)
        self.assertEqual(self.bridge.get_fusions("fusao",0,20,
                         search_scope="result")["total"],2)
        self.assertEqual(self.bridge.get_fusions("FUSÃO",0,20,
                         search_scope="material")["total"],1)
        self.assertEqual(self.bridge.get_fusions("",0,20,
                         search_scope="result")["total"],2)
        self.assertEqual(self.bridge.get_fusions("",0,20,
                         search_scope="material")["total"],2)

    def test_fusion_scope_filters_before_pagination_and_preserves_sort(self):
        self.assertEqual(self.bridge.get_fusions("Fusão",0,1,
                         search_scope="result")["total"],2)
        page=self.bridge.get_fusions("Fusão",1,1,"id","", "result")
        self.assertEqual(page["total"],2)
        self.assertEqual(len(page["rows"]),1)
        self.assertEqual(page["rows"][0]["result"],8)
        self.assertEqual(self.bridge.get_fusions("Fusão",0,20,
                         search_scope="material")["total"],1)
        self.assertEqual(self.bridge.get_fusions("Fusão",0,20,
                         search_scope="result")["total"],2)
        for bad in (None,0,True,[],{}, "all,material", "any", "RESULT"):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                self.bridge.get_fusions("",0,20,search_scope=bad)

    def test_scope_search_does_not_match_descriptions_of_other_roles(self):
        self.profile["cards"][0]["description_text"]="Vento luminosa"
        self.profile["cards"][0]["description_source"]="SLUS:test"
        atomic_json(self.profile_path,self.profile)
        # A busca geral legada mantém descrição, mas pesquisa específica
        # evita confundir descrição/efeito com nome da carta selecionada.
        self.assertEqual(self.bridge.get_fusions("Vento luminosa",0,20,
                         search_scope="all")["total"],1)
        self.assertEqual(self.bridge.get_fusions("Vento luminosa",0,20,
                         search_scope="result")["total"],0)
        self.assertEqual(self.bridge.get_fusions("Vento luminosa",0,20,
                         search_scope="material")["total"],0)

    def test_fusions_sort_type_filter_and_page_stay_consistent(self):
        self.profile["cards"][5]["type_label"]="Dragão"
        self.profile["cards"][6]["type_label"]="Mago"
        atomic_json(self.profile_path,self.profile)
        sorted_rows=self.bridge.get_fusions("",0,1,"atk")
        self.assertEqual(sorted_rows["total"],2)
        self.assertEqual(sorted_rows["rows"][0]["result"],8)
        self.assertEqual(self.bridge.get_fusions("",1,1,"atk")["rows"][0]["result"],7)
        selected=self.bridge.get_fusions("",0,20,"name","Dragão")
        self.assertEqual(selected["total"],1)
        self.assertEqual(selected["rows"][0]["result"],7)
        with self.assertRaises(ValueError):
            self.bridge.get_fusions("",0,20,"nonsense")

    def test_import_emulator_mips_log_is_local_and_sha_scoped(self):
        self.profile["rank_mips_evidence"]={
            "available":True,
            "candidates":[{"pc":"0x80012040","score":12,"file_offset":0x840}]}
        atomic_json(self.profile_path,self.profile)
        trace=self.home/"meu-duelo.log"
        trace.write_text("\n".join(
            [f"PC=0x{0x80012000+(i%17)*4:08X}" for i in range(120)]
            + ["PC=0x80012040 PHASE=DUEL OP=LBU "
               "ADDR=0x8009B361 VALUE=0x05"] * 5))
        self.bridge._file_picker=lambda kind: [str(trace)] if kind=="trace" else []
        response=self.bridge.import_rank_trace()
        self.assertFalse(response["cancelled"])
        self.assertTrue(response["executionEvidence"])
        self.assertFalse(response["rankRoutineConfirmed"])
        self.assertTrue(response["opponentFieldEvidence"]["available"])
        self.assertEqual(response["opponentFieldEvidence"]["legacyFieldReadEvents"],5)
        self.assertFalse(response["opponentFieldEvidence"]["opponentIdentityVerified"])
        self.assertFalse(response["opponentFieldEvidence"]["mayActivateDrops"])
        self.assertEqual(self.bridge.get_rank_trace_status()["records"],1)
        self.assertNotIn(str(trace),str(self.bridge.get_rank_trace_status()))
        trace.unlink()

    def test_partial_profile_needs_manual_acknowledgement(self):
        self.entry["level"]="parcial_revisar"
        atomic_json(self.catalog.registry_file,{"schema":1,"entries":[self.entry]})
        with self.assertRaises(PermissionError):
            self.bridge.activate_mod(self.sha,False)
        self.assertEqual(self.bridge.activate_mod(self.sha,True)["activeSha"],self.sha)

    def test_unknown_iso_lp_confirmation_cannot_authorize_memory_reads(self):
        reader=Mock()
        self.bridge._rank_reader=reader
        self.bridge._rank_mod_reader=Mock()
        for lp in (8000,10000):
            with self.subTest(lp=lp):
                result=self.bridge.confirm_rank_lp(lp)
                self.assertEqual(result["state"],"unsupported")
                self.assertFalse(result["ready"])
                self.assertIsNone(result["score"])
        reader.assert_not_called()
        self.bridge._rank_mod_reader.assert_not_called()
        self.assertIsNone(self.bridge._rank_calibration)
        with self.assertRaises(ValueError):
            self.bridge.capture_rank_prediction()
        reader.assert_not_called()

    def test_unmapped_iso_clears_previous_duel_and_capture(self):
        self.bridge._rank_reader=Mock()
        self.bridge._rank_mod_reader=Mock()
        for name in ("_rank_calibration","_rank_legacy_trial","_rank_lp_session",
                     "_rank_last_turns","_rank_last_snapshot","_rank_pending_capture"):
            setattr(self.bridge,name,{"sha":self.sha,"pid":1234})
        self.bridge._rank_gap_started=1
        self.assertEqual(self.bridge.get_rank()["state"],"unsupported")
        for name in ("_rank_calibration","_rank_legacy_trial","_rank_gap_started",
                     "_rank_lp_session","_rank_last_turns","_rank_last_snapshot",
                     "_rank_pending_capture"):
            self.assertIsNone(getattr(self.bridge,name),name)
        self.bridge._rank_reader.assert_not_called()
        self.bridge._rank_mod_reader.assert_not_called()

    def test_unverified_binding_never_falls_back_to_known_address(self):
        from test_dueltrace_rank_profile_live import profile as valid_profile
        self.profile=valid_profile()
        self.profile["rank_runtime_binding"]["verified_duels"]=1
        atomic_json(self.profile_path,self.profile)
        self.bridge._rank_reader=Mock()
        self.bridge._rank_mod_reader=Mock()
        self.assertEqual(self.bridge.get_rank()["state"],"unsupported")
        self.bridge._rank_reader.assert_not_called()
        self.bridge._rank_mod_reader.assert_not_called()

    def test_matching_binding_for_another_iso_does_not_authorize_active_sha(self):
        from test_dueltrace_rank_profile_live import profile as valid_profile
        foreign=valid_profile()
        foreign["rom_sha256"]="e"*64
        foreign["rank_runtime_binding"]["rom_sha256"]="e"*64
        self.bridge._active=Mock(return_value=({"sha256":self.sha},self.entry,foreign))
        self.bridge._rank_reader=Mock()
        self.bridge._rank_mod_reader=Mock()
        self.assertEqual(self.bridge.get_rank()["state"],"unsupported")
        self.bridge._rank_reader.assert_not_called()
        self.bridge._rank_mod_reader.assert_not_called()

    def test_any_mod_can_project_only_after_own_verified_ram_binding(self):
        sha=self.sha  # Não é X15
        self.profile["exe_sha256"]="b"*64
        self.profile["rank_points"]={
            "available":True,"table_sha256":"c"*64,
            "rules":{
                "criterion_01":[{"below":5,"points":12},{"below":32767,"points":-3}],
                "criterion_02":[{"below":7000,"points":0},{"below":32767,"points":4}],
            },
        }
        self.profile["rank_runtime_binding"]={
            "rom_sha256":sha,"exe_sha256":"b"*64,"table_sha256":"c"*64,
            "validation_method":"independent_duel_trace","verified_duels":2,
            "record_address":0xB41990,"record_length":32,
            "criterion_offsets":{
                "criterion_01":{"type":"u8","offset":1},
                "criterion_02":{"type":"u16le","offset":20},
            },
            "life_points_criterion":"criterion_02",
            "turns_criterion":"criterion_01","base_points":50,
            "victory_bonuses":{"lp":2},
            "rank_bands":[
                {"label":"Z-POW","minimum":65},
                {"label":"S-POW","minimum":50},
                {"label":"S-TEC","minimum":-100},
            ],
        }
        atomic_json(self.profile_path,self.profile)
        counters={"criterion_01":1,"criterion_02":8000}
        reader=Mock(return_value={
            "ready":True,"status":"Contadores verificados","pid":1234,
            "counters":counters})
        self.bridge._rank_mod_reader=reader
        self.bridge._rank_reader=Mock()
        before=self.bridge.get_rank()
        self.assertEqual(before["state"],"needs_lp_confirmation")
        self.assertEqual(before["candidateLp"],8000)
        self.assertFalse(before["ready"])
        self.assertEqual(self.bridge.confirm_rank_lp(9000)["state"],"lp_mismatch")
        result=self.bridge.confirm_rank_lp(8000)
        self.assertTrue(result["ready"])
        self.assertFalse(result["final"])
        self.assertEqual(result["score"],68)
        self.assertEqual(result["category"],"C-POW")
        self.assertEqual(result["rankSystem"],"classic")
        self.assertEqual(self.bridge._rank_last_snapshot["category"],"C-POW")
        self.bridge._rank_reader.assert_not_called()
        reader.assert_called()
        counters["criterion_01"]=0
        self.assertEqual(self.bridge.get_rank()["state"],"needs_lp_confirmation")

    def test_identical_executable_and_rank_table_are_not_a_ram_binding(self):
        from fm_rank_tables import (
            KNOWN_X15_SLUS_SHA256,KNOWN_X15_TABLE_SHA256,LEGACY_OFFSET,STRIDE
        )
        self.profile["exe_sha256"]=KNOWN_X15_SLUS_SHA256
        self.profile["rank_points"]={
            "available":True,"structure_verified":True,
            "table_sha256":KNOWN_X15_TABLE_SHA256,
            "first_offset":LEGACY_OFFSET,"repeat_stride":STRIDE,
        }
        atomic_json(self.profile_path,self.profile)
        self.bridge._rank_reader=Mock()
        self.bridge._rank_mod_reader=Mock()
        self.assertEqual(self.bridge.get_rank()["state"],"unsupported")
        self.assertEqual(self.bridge.confirm_rank_lp(8000)["state"],"unsupported")
        self.bridge._rank_reader.assert_not_called()
        self.bridge._rank_mod_reader.assert_not_called()
        diagnostic=self.bridge.get_rank_diagnostic()
        self.assertTrue(diagnostic["x15CompatibleBinary"])
        self.assertFalse(diagnostic["readyForLiveRead"])
        self.assertEqual(diagnostic["code"],"runtime_binding_required")

    def test_rank_requires_lp_confirmation_and_resets_on_new_duel(self):
        sha=X15_SHA
        path=self.home/"profiles"/sha[:16]/"profile.json"
        profile={**self.profile,"rom_sha256":sha}
        atomic_json(path,profile)
        entry={**self.entry,"sha256":sha,"profile_path":str(path)}
        atomic_json(self.catalog.registry_file,{"schema":1,"entries":[entry]})
        atomic_json(self.catalog.active_file,{"sha256":sha})
        counters={"turns":1,"effective_attacks":0,"defense_wins":0,"face_down":0,
                  "spells":0,"traps":0,"fusions":0,"equips":0,
                  "remaining_lp":8000,"cards_used":0}
        reader=Mock(return_value={"ready":True,"status":"Candidato estável",
                                  "pid":1234,"counters":counters})
        self.bridge._rank_reader=reader
        before=self.bridge.get_rank()
        self.assertEqual(before["state"],"needs_lp_confirmation")
        self.assertIsNone(before["score"])
        bad=self.bridge.confirm_rank_lp(5000)
        self.assertEqual(bad["state"],"lp_mismatch")
        self.assertIsNone(bad["score"])
        with self.assertRaises(ValueError):
            self.bridge.confirm_rank_lp(-1)
        calibrated=self.bridge.confirm_rank_lp(8000)
        self.assertTrue(calibrated["ready"])
        self.assertFalse(calibrated["final"])
        self.assertEqual(calibrated["category"],"Z-POW")
        self.assertEqual(calibrated["rankSystem"],"x15")
        self.assertEqual(self.bridge._rank_last_snapshot["category"],"Z-POW")
        counters["turns"]=2
        self.assertTrue(self.bridge.get_rank()["ready"])
        counters["turns"]=0  # reinício da partida
        self.assertEqual(self.bridge.get_rank()["state"],"needs_lp_confirmation")
        self.bridge.confirm_rank_lp(8000)
        reader.return_value={"ready":False,"status":"Emulador fechado",
                             "pid":1234,"counters":None}
        disconnected=self.bridge.get_rank()
        self.assertIsNone(disconnected["score"])
        self.assertEqual(disconnected["state"],"unavailable")

    def test_native_api_requires_capability_for_all_privileged_calls(self):
        secret="S"*43
        protected=ProtectedDesktopApi(self.bridge,secret)
        for method,params in (
            ("get_state",()),
            ("check_updates",()),
            ("open_updates_page",()),
            ("get_hand",()),
            ("get_fusions",("",0,10)),
            ("get_drops",(0,"","",0,10)),
            ("get_card_drop_sources",(1,)),
            ("get_duel_evidence",()),
            ("get_rank_trace_status",()),
            ("export_rank_audit",()),
            ("import_rank_trace",()),
            ("record_duel_result",(1,"Z-POW",1,None)),
            ("get_rank",()),
            ("confirm_rank_lp",(8000,)),
            ("activate_mod",(self.sha,False)),
            ("import_iso",()),
            ("configure_epsxe",()),
            ("scan_sources",(self.sha,)),
            ("start_game",()),
        ):
            with self.subTest(method=method):
                for credential in ("",None,"incorrect"):
                    with self.assertRaises(PermissionError):
                        getattr(protected,method)(credential,*params)
        self.assertEqual(protected.get_state(secret)["activeSha"],self.sha)
        self.assertEqual(len(protected.get_hand(secret)["hand"]),5)

    def test_updates_bridge_is_explicit_and_does_not_download(self):
        from unittest.mock import patch
        with patch("dueltrace_web_bridge.check_for_updates",return_value={
            "status":"preview_ahead","currentVersion":"0.7.2","latestStable":"v0.6.6",
            "updateAvailable":False,"message":"Prévia mais nova",
            "channel":"preview","releasePage":"https://github.com/guibatoni/appassist/releases/latest"
        }) as check, patch(
            "dueltrace_web_bridge.fetch_latest_preview_package",return_value=None
        ) as preview:
            result=self.bridge.check_updates()
        self.assertEqual(result["status"],"preview_ahead")
        check.assert_called_once()
        preview.assert_called_once()
        self.assertTrue(callable(check.call_args.kwargs["preview_fetcher"]))
        with patch("dueltrace_web_bridge.open_official_releases",return_value=True) as opener:
            self.assertEqual(self.bridge.open_updates_page(),{"opened":True})
            opener.assert_called_once_with(None)
        with patch("dueltrace_web_bridge.open_official_releases",return_value=True) as opener:
            self.assertEqual(self.bridge.open_updates_page(41696820609),{"opened":True})
            opener.assert_called_once_with(41696820609)


    def test_capability_only_injected_into_exact_loopback_origin(self):
        origin="http://127.0.0.1:49321/"
        self.assertTrue(trusted_window_url(origin,origin))
        self.assertTrue(trusted_window_url(origin+"biblioteca/",origin))
        for candidate in (
            "https://127.0.0.1:49321/",
            "http://localhost:49321/",
            "http://127.0.0.1:49322/",
            "http://evil.example/",
            "http://evil.example@127.0.0.1:49321/",
            "http://127.0.0.1:49321/#evil",
            "not-a-url",None,
        ):
            with self.subTest(candidate=candidate):
                self.assertFalse(trusted_window_url(candidate,origin))

    def test_web_without_native_picker_does_not_open_arbitrary_path(self):
        with self.assertRaises(RuntimeError):
            self.bridge.import_iso()
        with self.assertRaises(RuntimeError):
            self.bridge.configure_epsxe()

    def test_static_server_rejects_cross_origin_and_dangerous_paths(self):
        static=self.home/"www"
        static.mkdir()
        (static/"index.html").write_text("DUELTRACE",encoding="utf-8")
        (static/"safe.js").write_text("console.log('safe')",encoding="utf-8")
        (static/".env").write_text("SECRET_CANARY",encoding="utf-8")
        (static/"empty").mkdir()
        outside=self.home/"not_static.txt"
        outside.write_text("PRIVATE_CANARY",encoding="utf-8")
        handler=local_handler(static,self.bridge)
        server=http.server.ThreadingHTTPServer(("127.0.0.1",0),handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        try:
            base="http://127.0.0.1:"+str(server.server_port)
            with urlopen(base+"/") as response:
                self.assertEqual(response.read(),b"DUELTRACE")
                self.assertEqual(response.headers["X-Frame-Options"],"DENY")
                self.assertIn("script-src 'self'",response.headers["Content-Security-Policy"])
                self.assertEqual(response.headers["Cross-Origin-Resource-Policy"],
                                 "same-origin")
            for url,headers,method,expected in (
                ("/",{"Host":"evil.example"}, "GET",403),
                ("/",{"Origin":"https://evil.example"}, "GET",403),
                ("/",{"Sec-Fetch-Site":"cross-site"},"GET",403),
                ("/%2e%2e/not_static.txt",{},"GET",403),
                ("/%252e%252e/not_static.txt",{},"GET",403),
                ("//evil.example/path",{},"GET",404),  # urllib normaliza a dupla barra
                ("/.env",{},"GET",403),
                ("/empty/",{},"GET",403),
                ("/",{},"POST",405),
                ("/__art__/"+"b"*64+"/1.png",{},"HEAD",405),
            ):
                with self.subTest(url=url,headers=headers,method=method):
                    req=Request(base+url,headers=headers,method=method)
                    with self.assertRaises(HTTPError) as denied:
                        urlopen(req)
                    self.assertEqual(denied.exception.code,expected)
            conn=http.client.HTTPConnection("127.0.0.1",server.server_port)
            try:
                conn.request("GET","//evil.example/path")
                response=conn.getresponse()
                # BaseHTTPRequestHandler pode normalizar // para / antes
                # de chamar nosso handler; a resposta NÃO deve apontar
                # para domínio externo.
                self.assertIn(response.status,(403,404,308))
                location=response.getheader("Location")
                if location:
                    self.assertTrue(location.startswith("/"))
                    self.assertFalse(location.startswith("//"))
                response.read()
            finally:
                conn.close()
            try:
                (static/"outbound.txt").symlink_to(outside)
            except (OSError,NotImplementedError):
                pass  # Windows CI pode negar symlinks não privilegiados.
            else:
                with self.assertRaises(HTTPError) as denied:
                    urlopen(base+"/outbound.txt")
                self.assertEqual(denied.exception.code,403)
        finally:
            server.shutdown()
            server.server_close()

    def test_scan_sources_rejects_unregistered_or_missing_source_file(self):
        with self.assertRaises(ValueError):
            self.bridge.scan_sources("not-a-sha")
        with self.assertRaises(ValueError):
            self.bridge.scan_sources("b"*64)
        with self.assertRaises(FileNotFoundError):
            self.bridge.scan_sources(self.sha)

    def test_rescan_does_not_overwrite_registry_for_modified_iso(self):
        source=self.home/"rom.iso"
        source.write_bytes(b"changed"*20000)
        with patch.object(self.catalog,"analyse",side_effect=AssertionError(
                "Não deve alterar registry após SHA divergente")):
            with self.assertRaises(RuntimeError):
                self.bridge.scan_sources(self.sha)
        self.assertEqual(self.catalog.list()[0]["sha256"],self.sha)

    def test_art_route_never_leaks_other_profile_and_denies_post(self):
        (self.analysis/"artes_722").mkdir()
        (self.analysis/"artes_722"/"001.png").write_bytes(b"\x89PNG\r\n\x1a\nSYNTHETIC")
        (self.analysis/"cartas_com_moldura").mkdir()
        (self.analysis/"cartas_com_moldura"/"001.png").write_bytes(b"\x89PNG\r\n\x1a\nFRAMED")
        (self.analysis/"artes_upscaled").mkdir()
        (self.analysis/"artes_upscaled"/"001.png").write_bytes(b"HD-ART-SYNTHETIC")
        (self.analysis/"cartas_classicas_hd").mkdir()
        (self.analysis/"cartas_classicas_hd"/"001.png").write_bytes(b"FULL-CLASSIC-SYNTHETIC")
        static=self.home/"static"
        static.mkdir()
        (static/"index.html").write_text("<html>DUELTRACE</html>",encoding="utf-8")
        handler=local_handler(static,self.bridge)
        server=http.server.ThreadingHTTPServer(("127.0.0.1",0),handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        try:
            base="http://127.0.0.1:"+str(server.server_port)
            with urlopen(base+"/__art__/"+self.sha+"/1.png") as response:
                self.assertTrue(response.read().startswith(b"\x89PNG"))
            with urlopen(base+"/__card__/"+self.sha+"/1.png") as response:
                self.assertIn(b"FRAMED",response.read())
            with urlopen(base+"/__art_hd__/"+self.sha+"/1.png") as response:
                self.assertEqual(response.read(),b"HD-ART-SYNTHETIC")
            with urlopen(base+"/__card_hd__/"+self.sha+"/1.png") as response:
                self.assertEqual(response.read(),b"FULL-CLASSIC-SYNTHETIC")
            with self.assertRaises(HTTPError) as foreign_classic:
                urlopen(base+"/__card_hd__/"+"b"*64+"/1.png")
            self.assertEqual(foreign_classic.exception.code,404)
            with self.assertRaises(HTTPError) as invalid_classic:
                urlopen(base+"/__card_hd__/"+self.sha+"/0.png")
            self.assertEqual(invalid_classic.exception.code,404)
                self.assertEqual(response.headers["Content-Type"],"image/png")
            with self.assertRaises(HTTPError) as foreign_hd:
                urlopen(base+"/__art_hd__/"+"b"*64+"/1.png")
            self.assertEqual(foreign_hd.exception.code,404)
            with self.assertRaises(HTTPError) as forbidden_hd_head:
                urlopen(Request(base+"/__art_hd__/"+self.sha+"/1.png",method="HEAD"))
            self.assertEqual(forbidden_hd_head.exception.code,405)
            with self.assertRaises(HTTPError) as foreign_card:
                urlopen(base+"/__card__/"+"b"*64+"/1.png")
            self.assertEqual(foreign_card.exception.code,404)
            with self.assertRaises(HTTPError) as bad_sha:
                urlopen(base+"/__art__/"+"b"*64+"/1.png")
            self.assertEqual(bad_sha.exception.code,404)
            with self.assertRaises(HTTPError) as wrong:
                urlopen(base+"/__art__/"+self.sha+"/0.png")
            self.assertEqual(wrong.exception.code,404)
        finally:
            server.shutdown()
            server.server_close()

if __name__=="__main__":
    unittest.main()
