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

    def test_drops_from_active_iso_are_paged_and_authenticated(self):
        groups=["TABELA_1_RANK_DESCONHECIDO","TABELA_2_RANK_DESCONHECIDO",
                "TABELA_3_RANK_DESCONHECIDO"]
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
        with self.assertRaises(PermissionError):
            protected.record_duel_result("invalid",2,"Z-POW",2,95)
        evidence=protected.record_duel_result("x"*64,2,"Z-POW",2,95)
        self.assertEqual(evidence["observations"],1)
        evidence=protected.record_duel_result("x"*64,3,"Z-POW",2,94)
        self.assertEqual(evidence["observations"],2)
        self.assertEqual(evidence["suspectedMappings"]["Z-POW"]["group"],groups[1])
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
            [f"PC=0x{0x80012000+(i%17)*4:08X}" for i in range(120)]))
        self.bridge._file_picker=lambda kind: [str(trace)] if kind=="trace" else []
        response=self.bridge.import_rank_trace()
        self.assertFalse(response["cancelled"])
        self.assertTrue(response["executionEvidence"])
        self.assertFalse(response["rankRoutineConfirmed"])
        self.assertEqual(self.bridge.get_rank_trace_status()["records"],1)
        self.assertNotIn(str(trace),str(self.bridge.get_rank_trace_status()))
        trace.unlink()

    def test_partial_profile_needs_manual_acknowledgement(self):
        self.entry["level"]="parcial_revisar"
        atomic_json(self.catalog.registry_file,{"schema":1,"entries":[self.entry]})
        with self.assertRaises(PermissionError):
            self.bridge.activate_mod(self.sha,False)
        self.assertEqual(self.bridge.activate_mod(self.sha,True)["activeSha"],self.sha)

    def test_rank_is_disabled_for_unrecognized_sha_without_ram_access(self):
        probe=Mock()
        self.bridge._rank_reader=probe
        result=self.bridge.get_rank()
        self.assertFalse(result["ready"])
        self.assertEqual(result["state"],"unsupported")
        self.assertIsNone(result["score"])
        probe.assert_not_called()

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
        self.assertEqual(result["category"],"Z-POW")
        self.bridge._rank_reader.assert_not_called()
        reader.assert_called()
        counters["criterion_01"]=0
        self.assertEqual(self.bridge.get_rank()["state"],"needs_lp_confirmation")

    def test_identical_executable_and_rank_table_enable_other_mod_after_lp_check(self):
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
        counters={"turns":1,"effective_attacks":0,"defense_wins":0,
                  "face_down":0,"spells":0,"traps":0,
                  "fusions":0,"equips":0,"remaining_lp":8000,"cards_used":0}
        self.bridge._rank_reader=Mock(return_value={
            "ready":True,"status":"Amostras estáveis","pid":1234,"counters":counters})
        start=self.bridge.get_rank()
        self.assertEqual(start["state"],"needs_lp_confirmation")
        result=self.bridge.confirm_rank_lp(8000)
        self.assertTrue(result["ready"])
        self.assertEqual(result["category"],"Z-POW")
        self.assertIn("idênticos ao X15",result["status"])

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
        }) as check:
            result=self.bridge.check_updates()
        self.assertEqual(result["status"],"preview_ahead")
        check.assert_called_once_with()
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
