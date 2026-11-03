"""Pipeline automático e ícone: testes sem ISO nem interface gráfica."""
from __future__ import annotations

import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from card_catalog import enrich_cards
from mod_autopilot import ModAutopilot, discover_images, profile_summary
from dueltrace_brand import ico_icon, png_icon
from dueltrace_theme import blend
from dueltrace_visuals import category_color, CATEGORY_SYMBOLS, NAV_SYMBOLS, QuickTile, HeroArt, CardArt, CategoryMeters
from dueltrace_desktop import DueltraceDesktop


class AutopilotTests(unittest.TestCase):
    def test_folder_scans_only_images_in_stable_order(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            for name in ("Z.bin","a.ISO","readme.txt","image.cue","a.iso.dueltrace-effects.json"):
                (path/name).write_bytes(b"x")
            self.assertEqual([x.name for x in discover_images(path)],["a.ISO","Z.bin"])
            with self.assertRaises(NotADirectoryError):
                discover_images(path/"no")

    def test_profile_has_true_counters_no_invented_effects(self):
        profile={
            "name":"Teste",
            "supported_features":{"cards":True,"effects":False,"fusions":False},
            "cards":enrich_cards([
                {"id":1,"name":"M","type_id":20},{"id":2,"name":"E","type_id":23},
                {"id":3,"name":"T","type_id":21}
            ]),
            "effects_provenance":{"status":"nao_fornecido","count":0},
            "fusion_recipes":[{"a":1,"b":2,"result":3}],
        }
        result=profile_summary({"sha256":"f"*64,"file_name":"x.iso",
                                "level":"parcial_revisar"},profile)
        self.assertEqual(result["categories"]["Mágicas"],1)
        self.assertEqual(result["categories"]["Equipamentos"],1)
        self.assertEqual(result["categories"]["Armadilhas"],1)
        self.assertEqual(result["effect_count"],0)
        self.assertEqual(result["fusion_count"],0)
        self.assertTrue(result["requires_review"])
        self.assertFalse(result["iso_verified_in_emulator"])

    def test_worker_scans_all_files_without_fabrication(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in ("one.iso","two.bin"):
                (root/name).write_bytes(b"x"*1024)
            fake=Mock()
            fake.analyse.side_effect=lambda p,progress=None:{
                "file_name":p.name,"sha256":hashlib.sha256(p.name.encode()).hexdigest(),
                "level":"desconhecido"}
            fake.profile_for.return_value=None
            found=[]
            result=ModAutopilot(fake).analyze_folder(root,callback=found.append)
            self.assertEqual(len(result),2)
            self.assertTrue(all(item["requires_review"] for item in result))
            self.assertEqual(len([e for e in found if e["event"]=="done"]),2)
            self.assertEqual(found[-1]["event"],"finished")


class BrandAndUITests(unittest.TestCase):
    def test_png_and_multi_size_ico_are_structurally_valid(self):
        blob=png_icon(64)
        self.assertTrue(blob.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(struct.unpack(">II",blob[16:24]),(64,64))
        icon=ico_icon()
        self.assertEqual(struct.unpack("<HHH",icon[:6]),(0,1,5))
        self.assertGreater(len(icon),1500)

    def test_redesign_components_are_integrated(self):
        self.assertIn("inicio", NAV_SYMBOLS)
        self.assertIn("Monstros", CATEGORY_SYMBOLS)
        self.assertEqual(category_color("Mágicas"), "#38D8AE")
        self.assertEqual(category_color("inexistente"), "#93B5CC")
        for component in (QuickTile, HeroArt, CardArt, CategoryMeters):
            self.assertTrue(callable(component))
        self.assertIn("CardArt", DueltraceDesktop._page_cartas.__code__.co_names)
        self.assertIn("HeroArt", DueltraceDesktop._page_inicio.__code__.co_names)

    def test_palette_and_ui_methods(self):
        self.assertEqual(blend("#000000","#FFFFFF",0),"#000000")
        self.assertEqual(blend("#000000","#FFFFFF",1),"#ffffff")
        for name in ("_page_inicio","_page_mods","_page_cartas","_page_fusoes",
                     "_page_overlay","_page_diagnostico","_page_configuracoes",
                     "activate_selected","_poll_events","choose_folder"):
            self.assertTrue(callable(getattr(DueltraceDesktop,name)))


if __name__=="__main__":
    unittest.main()
