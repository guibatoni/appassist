"""Testes do encaixe do perfil ativo na mão do CompactPanel legado."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from overlay_profile_bridge import apply_overlay_profile


def snap(sha,name,cards,recipes=None,rank=False,allowed=True):
    return {
        "ready":True,
        "rom_sha256":sha,
        "profile_name":name,
        "features":{
            "nomes_cartas":allowed, "fusoes":bool(recipes),
            "rank":rank, "artes":False, "drops_brutos":True,
        },
        "cards":cards,
        "recipes":recipes or [],
    }


class ProfileBridgeTests(unittest.TestCase):
    def test_legacy_captured_references_see_new_card_names(self):
        original={123:{"name":"Carta #123","atk":0,"def":0}}
        recipe_list=[(1,2,3)]
        app=SimpleNamespace(cards=original,recipes=recipe_list,index={(1,2):3})
        compact=SimpleNamespace(cards=original,recipes=recipe_list,
                                strategy=SimpleNamespace(cards=original,recipes=recipe_list),
                                atlas={"rankLabels":["Z-POW"],"drops":[{"card":1}]})
        captured_card_dict=original
        captured_recipe_list=recipe_list
        new=snap("a"*64,"FM Original",
                 {123:{"name":"Blue-Eyes White Dragon","atk":3000,"def":2500,"type_id":1}})
        result=apply_overlay_profile(new,app=app,compact=compact)
        self.assertTrue(result["applied"])
        self.assertEqual(result["card_count"],1)
        self.assertIs(app.cards,original)
        self.assertIs(compact.cards,original)
        self.assertEqual(captured_card_dict[123]["name"],"Blue-Eyes White Dragon")
        self.assertEqual(captured_recipe_list,[])
        self.assertEqual(compact.atlas["rankLabels"],[])
        self.assertFalse(result["iso_active_in_emulator_verified"])

    def test_switching_mods_removes_stale_names(self):
        original={722:{"name":"Outra carta"}}
        compact=SimpleNamespace(cards=original,recipes=[],atlas={})
        first=snap("a"*64,"Original",{123:{"name":"Carta Um","atk":1230,"def":900}})
        second=snap("b"*64,"Novo Mod",{208:{"name":"Carta Dois","atk":1800,"def":1300}})
        apply_overlay_profile(first,compact=compact)
        apply_overlay_profile(second,compact=compact)
        self.assertEqual(sorted(original.keys()),[208])
        self.assertEqual(original[208]["name"],"Carta Dois")
        self.assertEqual(compact._active_profile["profile_name"],"Novo Mod")

    def test_no_profile_does_not_clear_live_overlay(self):
        old={123:{"name":"Original"}}
        panel=SimpleNamespace(cards=old,recipes=[])
        result=apply_overlay_profile({"ready":False,"reason":"Perfil ausente"},compact=panel)
        self.assertFalse(result["applied"])
        self.assertEqual(old[123]["name"],"Original")

    def test_unverified_cards_do_not_leak(self):
        fake=snap("c"*64,"Desconhecido",{123:{"name":"ERRADO","atk":100,"def":200}},allowed=False)
        panel=SimpleNamespace(cards={123:{"name":"Anterior"}},recipes=[])
        apply_overlay_profile(fake,compact=panel)
        self.assertEqual(panel.cards,{})
        self.assertNotIn(123,panel.cards)


if __name__ == "__main__":
    unittest.main()
