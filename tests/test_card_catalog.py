"""Cartas, categorias e efeitos: dados sintéticos; nenhum mod comercial necessário."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from card_catalog import (
    describe_type, enrich_cards, category_summary,
    effect_sidecar_path, attach_effect_manifest
)


class CardCatalogTests(unittest.TestCase):
    def test_five_categories_and_unknown(self):
        samples=[(0,"Monstros","Dragão"),(19,"Monstros","Planta"),
                 (20,"Mágicas","Magia"),(21,"Armadilhas","Armadilha"),
                 (22,"Rituais","Ritual"),(23,"Equipamentos","Equipamento")]
        for type_id,category,label in samples:
            self.assertEqual(describe_type(type_id)[:2],(category,label))
        for v in (-1,24,31,None,"20",True):
            self.assertEqual(describe_type(v)[0],"Não identificado")
        self.assertEqual(describe_type(20,known_fm_layout=False)[0],"Não identificado")

    def test_category_counts_no_effect_invention(self):
        cards=enrich_cards([
            {"id":i+1,"name":f"Card {i}","type_id":t,"atk":0,"def":0}
            for i,t in enumerate((0,20,21,22,23,31))
        ])
        counts=category_summary(cards)
        self.assertEqual(list(counts.values()),[1]*6)
        self.assertTrue(all(x["effect_text"] is None for x in cards))
        self.assertTrue(all(x["effect_status"]=="nao_identificado" for x in cards))

    def test_manifest_requires_exact_hash_and_known_ids(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"mod.iso.dueltrace-effects.json"
            sha=hashlib.sha256(b"image").hexdigest()
            cards=enrich_cards([{"id":1,"name":"Teste","type_id":20}])
            self.assertEqual(effect_sidecar_path(Path(d)/"mod.iso"),path)
            self.assertEqual(attach_effect_manifest(cards,path,rom_sha256=sha)[1]["count"],0)
            path.write_text(json.dumps({"schema":1,"rom_sha256":sha,"effects":[
                {"id":1,"text":"Este efeito foi fornecido pelo autor do mod."}
            ]}),encoding="utf-8")
            modified,status=attach_effect_manifest(cards,path,rom_sha256=sha)
            self.assertEqual(status["count"],1)
            self.assertTrue(status["sha256_matches"])
            self.assertEqual(modified[0]["category"],"Mágicas")
            self.assertEqual(modified[0]["effect_text"],"Este efeito foi fornecido pelo autor do mod.")
            self.assertEqual(modified[0]["effect_status"],"fornecido_externamente_nao_verificado_na_iso")
            self.assertIsNone(cards[0]["effect_text"])
            with self.assertRaisesRegex(ValueError,"SHA"):
                attach_effect_manifest(cards,path,rom_sha256="f"*64)
            path.write_text(json.dumps({"schema":1,"rom_sha256":sha,"effects":[
                {"id":1,"text":"X"},{"id":1,"text":"Y"}
            ]}),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"duplicado"):
                attach_effect_manifest(cards,path,rom_sha256=sha)

    def test_untrusted_manifest_rejects_invalid_entries(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"effects.json"
            sha="a"*64
            cards=enrich_cards([{"id":1,"name":"Teste","type_id":0}])
            for effects in (
                [{"id":True,"text":"Efeito"}],
                [{"id":99,"text":"Efeito"}],
                [{"id":1,"text":""}],
                [{"id":1,"text":"x"*2000}],
            ):
                path.write_text(json.dumps({"schema":1,"rom_sha256":sha,
                                            "effects":effects}),encoding="utf-8")
                with self.assertRaises(ValueError):
                    attach_effect_manifest(cards,path,rom_sha256=sha)


if __name__=="__main__":
    unittest.main()
