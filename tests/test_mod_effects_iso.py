"""Metadados embutidos: fonte explícita na ISO, sem inventar efeito."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from card_catalog import enrich_cards
from mod_effects_iso import extract_embedded_effects


class FakeDisc:
    def __init__(self,_path):
        self.files={"DTEFFECT.JSON":(10,120)}
        self.closed=False
    def get(self,name,limit_bytes=None):
        return json.dumps({"schema":1,"effects":[
            {"id":2,"text":"Efeito fornecido no contêiner da ISO."}
        ]}).encode()
    def close(self):self.closed=True


class EmbeddedEffectsTests(unittest.TestCase):
    def test_embedded_effect_text_is_not_mechanic_verification(self):
        cards=enrich_cards([{"id":1,"type_id":0,"name":"A"},
                            {"id":2,"type_id":20,"name":"Magia"}])
        disc=FakeDisc("synthetic")
        with patch("mod_effects_iso.Disc",return_value=disc):
            changed,meta=extract_embedded_effects(Path("fake.iso"),cards,
                                                   rom_sha256="d"*64)
        self.assertTrue(disc.closed)
        self.assertEqual(changed[0]["effect_text"],None)
        self.assertEqual(changed[1]["effect_text"],"Efeito fornecido no contêiner da ISO.")
        self.assertTrue(meta["embedded_in_iso"])
        self.assertFalse(meta["effects_executed_in_game_verified"])
        self.assertTrue(changed[1]["effect_source"].startswith("declarado_no_iso:"))
        self.assertEqual(changed[1]["effect_status"],
                         "texto_embutido_na_iso_nao_validado_no_jogo")

    def test_missing_and_large_metadata_stay_unavailable(self):
        cards=enrich_cards([{"id":1,"type_id":23}])
        fake=FakeDisc("x");fake.files={}
        with patch("mod_effects_iso.Disc",return_value=fake):
            changed,meta=extract_embedded_effects(Path("foo.iso"),cards,
                                                   rom_sha256="d"*64)
        self.assertEqual(meta["count"],0)
        self.assertIsNone(changed[0]["effect_text"])
        self.assertTrue(fake.closed)
        too_big=FakeDisc("x")
        too_big.files={"DTEFFECT.JSON":(10,2_000_000)}
        with patch("mod_effects_iso.Disc",return_value=too_big):
            with self.assertRaisesRegex(ValueError,"tamanho"):
                extract_embedded_effects(Path("foo.iso"),cards,
                                         rom_sha256="d"*64)
        self.assertTrue(too_big.closed)


if __name__=="__main__":
    unittest.main()
