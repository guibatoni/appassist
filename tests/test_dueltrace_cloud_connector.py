"""Local-only DUELTRACE Cloud connector security and data-isolation tests."""
from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_cloud_connector import (
    HOST, _local_state, _local_live, _is_allowed_origin,
    create_server, _local_art, make_handler,
)

ORIGIN="http://127.0.0.1:3000"
TOKEN="dueltrace-"+"r"*45
SHA="a"*64
OTHER="b"*64


class FakeBridge:
    def __init__(self):
        self.active=SHA
        self.imports=0
        self.memories=0
        self.activations=[]
        self.catalog=None

    def get_state(self):
        return {
            "activeSha":self.active,
            "activeName":"Rising of Wicked Gods",
            "source_path":"C:/private/game.iso",
            "mods":[
                {"sha256":SHA,"name":"Rising","cards":722,"fusions":100,
                 "opponents":39,"dropEntries":722,
                 "source_path":"C:/secret/file.bin","privateEvidenceSync":"secret"},
                {"sha256":"invalid","name":"Fake"},
            ],
            "cards":[
                {"id":1,"name":"Dragão", "type":"Dragon","atk":100,"def":50,
                 "effect":"Fogo", "description":"Carta local",
                 "source_path":"C:/secret/game.bin","ram_address":"0xdeadbeef"},
                {"id":999,"name":"Out of bounds"},
            ],
        }

    def get_fusions(self,**kwargs):
        return {"total":1,"offset":kwargs["offset"],
                "rows":[{"a":1,"b":2,"result":3,
                         "nameA":"Dragão","nameB":"Fada",
                         "nameResult":"Fusão",
                         "source":"ISO-local"}]}

    def get_card_fusion_paths(self,card_id):
        return {
            "available": True, "romSha": SHA, "cardId": card_id,
            "provisional": True, "materialTotal": 5, "resultTotal": 5,
            "materialRows": [
                {"partnerId": index, "partnerName": "Carta parceira",
                 "resultId": 3, "resultName": "Resultado <teste>",
                 "atk": 1000, "def": 800}
                for index in range(2, 7)
            ],
            "resultRows": [
                {"materialAId": 2, "materialAName": "Material A",
                 "materialBId": 3, "materialBName": "Material B"}
                for _ in range(5)
            ],
        }

    def get_opponent_deck(self,opponent_id=0):
        return {"available":True,"opponentId":opponent_id,
                "opponents":[{"id":1,"name":"Simon"}],
                "cards":[{"id":1,"name":"Dragão","weight":2048}],
                "status":"pool local","provisional":True}

    def get_drops(self,**kwargs):
        return {"available":True,"total":1,"rows":[
            {"cardId":1,"cardName":"Dragão","groupLabel":"S-POW",
             "chancePercent":10.1}],"status":"drop local"}

    def get_deck_library(self,deck_id=""):
        return {"linked":False,"cards":[],"status":"Selecione Memory Card",
                "saved":[],"fusions":{"total":0,"rows":[]},"selectedBlock":None}

    def get_hand(self):
        return {"ready":True,"hand":[
            {"id":1,"slot":1,"name":"Dragão","atk":100,"def":50,
             "address":"0xBFF484"}],
            "pairs":[{"slot_a":1,"slot_b":2,"result":3,
                      "result_name":"Fusion Test","atk":2200,
                      "validation":"ISO","pid":321}],
            "chains":[{"result":4,"result_name":"Chain Test","atk":2400,
                       "ram_address":"0xBFF484"}],
            "status":"mão validada","pid":321,"ram_address":"0xBFF484"}

    def get_rank_auto(self):
        return {"ready":True,"score":94,"category":"S-POW",
                "status":"rank local","pid":321,
                "secret_memory_dump":"A1B2C3"}

    def activate_mod(self,sha,acknowledge=False):
        self.activations.append((sha,acknowledge))
        self.active=sha

    def import_iso(self):
        self.imports+=1
        return {"cancelled":False,"mod":{"sha256":SHA,"name":"Novo",
                "source_path":"C:/secret/new.iso"}}

    def select_memory_card(self):
        self.memories+=1
        return {"selected":True,"cardName":"epsxe000.mcr",
                "detectedSaveCount":1,"status":"local",
                "path":"C:/secret/memcard.mcr"}


class CloudSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge=FakeBridge()
        cls.http=create_server(cls.bridge,allowed_origins=[ORIGIN],token=TOKEN,port=0)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()
        cls.base="http://"+HOST+":"+str(cls.http.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(timeout=3)

    def request(self,path,*,origin=ORIGIN,token=TOKEN,method="GET",body=None,headers=None):
        h={"Origin":origin}
        if token is not None:h["Authorization"]="Bearer "+token
        if body is not None:
            h["Content-Type"]="application/json"
            body=json.dumps(body).encode("utf-8")
        if headers:h.update(headers)
        req=urllib.request.Request(
            self.base+path,data=body,method=method,headers=h)
        try:
            with urllib.request.urlopen(req,timeout=5) as res:
                return res.status,res.headers,res.read()
        except urllib.error.HTTPError as e:
            return e.code,e.headers,e.read()

    def test_valid_token_exact_origin_and_no_filesystem_paths(self):
        status,headers,raw=self.request("/v1/state")
        self.assertEqual(status,200)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"),ORIGIN)
        self.assertEqual(headers.get("Cache-Control"),"no-store, max-age=0")
        data=json.loads(raw)
        self.assertEqual(data["storage"],"local-only")
        self.assertFalse(data["cloudUpload"])
        self.assertEqual(data["cards"][0]["description"],"Carta local")
        self.assertEqual(len(data["cards"]),1)
        self.assertEqual(len(data["mods"]),1)
        self.assertNotIn(b"C:/secret",raw)
        self.assertNotIn(b"source_path",raw)
        self.assertNotIn(b"ram_address",raw)
        self.assertNotIn(b"privateEvidenceSync",raw)

    def test_wrong_origin_is_denied_even_with_token(self):
        status,headers,raw=self.request("/v1/state",origin="https://malicious.example")
        self.assertEqual(status,403)
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))

    def test_wrong_token_missing_token_and_no_origin_are_denied(self):
        self.assertEqual(self.request("/v1/state",token="wrong")[0],401)
        self.assertEqual(self.request("/v1/state",token=None)[0],401)
        self.assertEqual(self.request("/v1/state",origin="")[0],403)

    def test_preflight_requires_exact_origin_and_allowlisted_headers(self):
        h={"Access-Control-Request-Method":"POST",
           "Access-Control-Request-Headers":"authorization, content-type"}
        status,headers,_=self.request("/v1/activate",method="OPTIONS",token=None,headers=h)
        self.assertEqual(status,204)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"),ORIGIN)
        self.assertEqual(self.request(
            "/v1/activate",method="OPTIONS",token=None,
            headers={"Access-Control-Request-Headers":"x-custom"})[0],403)

    def test_reads_reuse_existing_python_engine(self):
        for endpoint in (
            "/v1/fusions?query=Fusao&offset=0&limit=80",
            "/v1/opponents?opponent=1","/v1/drops?opponent=1",
            "/v1/decks","/v1/live",
        ):
            code,_,raw=self.request(endpoint)
            self.assertEqual(code,200,endpoint)
            self.assertIsInstance(json.loads(raw),dict)
        _,_,live_raw=self.request("/v1/live")
        self.assertNotIn(b"pid",live_raw)
        self.assertNotIn(b"ram_address",live_raw)
        self.assertNotIn(b"secret_memory_dump",live_raw)
        self.assertEqual(json.loads(live_raw)["hand"]["cards"][0]["id"],1)
        self.assertEqual(len(json.loads(live_raw)["hand"]["pairs"]),1)
        self.assertEqual(json.loads(live_raw)["hand"]["chains"][0]["result_name"],"Chain Test")

    def test_invalid_or_unregistered_sha_cannot_activate(self):
        self.assertEqual(self.request(
            "/v1/activate",method="POST",body={"sha":OTHER})[0],400)
        self.assertEqual(self.request(
            "/v1/activate",method="POST",body={"sha":"../../iso"})[0],400)
        self.assertFalse(self.bridge.activations)
        self.assertEqual(self.request(
            "/v1/activate",method="POST",body={"sha":SHA})[0],200)
        self.assertEqual(self.bridge.activations[-1],(SHA,True))

    def test_import_and_memory_selection_are_local_only(self):
        before=self.bridge.imports,self.bridge.memories
        self.assertEqual(self.request(
            "/v1/import",method="POST",body={"path":"C:/secret/iso.iso"})[0],400)
        self.assertEqual(self.request(
            "/v1/memory-card",method="POST",body={"path":"../foo.mcr"})[0],400)
        self.assertEqual((self.bridge.imports,self.bridge.memories),before)
        status,_,raw=self.request(
            "/v1/import",method="POST",body={"chooseLocalFile":True})
        self.assertEqual(status,200)
        self.assertNotIn(b"source_path",raw)
        self.assertEqual(self.bridge.imports,before[0]+1)
        status,_,raw=self.request(
            "/v1/memory-card",method="POST",body={"chooseLocalFile":True})
        self.assertEqual(status,200)
        self.assertNotIn(b"C:/secret",raw)
        self.assertEqual(self.bridge.memories,before[1]+1)

    def test_art_path_and_unknown_route_fail_closed(self):
        self.assertEqual(self.request("/v1/art?sha="+SHA+"&id=1")[0],503)
        self.assertEqual(self.request("/v1/art?sha=bad&id=1")[0],404)
        self.assertEqual(self.request("/etc/passwd")[0],404)

    def test_http_host_rebinding_is_rejected(self):
        status,_,_=self.request("/v1/state",headers={"Host":"evil.test"})
        self.assertEqual(status,403)

    def test_oversized_or_invalid_post_cannot_trigger_action(self):
        self.assertEqual(self.request(
            "/v1/import",method="POST",body={"chooseLocalFile":True,"padding":"a"*4000})[0],413)
        self.assertEqual(self.request(
            "/v1/import",method="POST",body={"chooseLocalFile":1})[0],400)


if __name__ == "__main__":
    unittest.main()
