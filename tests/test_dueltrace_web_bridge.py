"""Regressões para integrar a interface v0 ao motor real sem dados fictícios."""
from __future__ import annotations

import functools
import http.server
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
from dueltrace_web_desktop import local_handler


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
            "supported_features":{"cards":True,"art":True,"fusions":True},
            "verified":{"cartas":"verificado"},
            "cards":[
                {"id":1,"name":"Carta comprovada","atk":1250,"def":1000,
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
        self.assertEqual(snapshot["cards"][1]["effect"],"Efeito com fonte")
        self.assertEqual(snapshot["cards"][1]["effectSource"],"ROM-offset-auditado")
        self.assertNotIn("source_path",str(snapshot))

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

    def test_partial_profile_needs_manual_acknowledgement(self):
        self.entry["level"]="parcial_revisar"
        atomic_json(self.catalog.registry_file,{"schema":1,"entries":[self.entry]})
        with self.assertRaises(PermissionError):
            self.bridge.activate_mod(self.sha,False)
        self.assertEqual(self.bridge.activate_mod(self.sha,True)["activeSha"],self.sha)

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
                ("//evil.example/path",{},"GET",403),
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

    def test_art_route_never_leaks_other_profile_and_denies_post(self):
        (self.analysis/"artes_722").mkdir()
        (self.analysis/"artes_722"/"001.png").write_bytes(b"\x89PNG\r\n\x1a\nSYNTHETIC")
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
