"""Contract and synthetic PS1-executable tests for automatic type names & HD."""
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))
from dueltrace_type_names import RETAIL_EN, extract_type_names, apply_type_names
from dueltrace_card_on_demand import ensure_card_hd
from dueltrace_classic_cards import SIZE

SHA_A = "a" * 64
SHA_B = "b" * 64


def make_exe(*, replacements=None, offset=1024, stride=24):
    names = list(RETAIL_EN)
    for code, value in (replacements or {}).items():
        names[code] = value
    bank = b"".join(name.encode("ascii").ljust(stride,b"\x00")
                    for name in names)
    return b"RANDOM_DIALOGUE_GOD_IS_NOT_A_TYPE_MAP\x00" + b"\xff" * offset + bank + b"END"


class IsoTypeNamesTests(unittest.TestCase):
    def test_name_god_replaces_reptile_at_original_code(self):
        result = extract_type_names(make_exe(replacements={11: "GOD"}),
                                    rom_sha256=SHA_A)
        self.assertEqual(result["status"], "tabela_textual_coerente")
        self.assertGreaterEqual(result["matchedRetailEntries"], 19)
        self.assertEqual(result["typeNameMap"], {"11": "GOD"})
        self.assertEqual(result["tableStride"], 24)
        cards=[{"id":1,"type_id":11,"category":"Monstros",
                "type_label":"Réptil","atk":5110,"def":5110}]
        renamed=apply_type_names(cards,result,rom_sha256=SHA_A)
        self.assertEqual(renamed[0]["type_label"], "GOD")
        self.assertEqual(renamed[0]["category"], "Monstros")
        self.assertEqual(renamed[0]["atk"],5110)
        self.assertEqual(cards[0]["type_label"], "Réptil")

    def test_never_leak_between_isos(self):
        result=extract_type_names(make_exe(replacements={11:"DEUS"}),
                                  rom_sha256=SHA_A)
        card=[{"id":1,"type_id":11,"type_label":"Réptil"}]
        self.assertEqual(apply_type_names(card,result,rom_sha256=SHA_B),card)

    def test_unrelated_god_word_is_not_a_type_table(self):
        result=extract_type_names(b"This card is a GOD\x00"+b"\x00"*100,
                                  rom_sha256=SHA_A)
        self.assertEqual(result["status"],"tabela_nao_localizada")
        self.assertFalse(result["typeNameMap"])

    def test_conflicting_type_banks_are_not_accepted(self):
        data=make_exe(replacements={11:"GOD"})+b"\xff"*100+make_exe(
            replacements={11:"DEUS"})
        result=extract_type_names(data,rom_sha256=SHA_A)
        self.assertEqual(result["status"],"tabelas_ambiguas")
        self.assertFalse(result["typeNameMap"])

    def test_truncated_and_malformed_iso_are_safe(self):
        for bad in (None,b"",b"DRAGON",{"id":4}):
            result=extract_type_names(bad,rom_sha256=SHA_A)
            self.assertEqual(result["status"],"tabela_nao_localizada")
        with self.assertRaises(ValueError):
            extract_type_names(b"binary",rom_sha256="../../outside")


class LazyCardGenerationTests(unittest.TestCase):
    def test_old_image_is_replaced_by_hd_and_original_stays_intact(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            raw=root/"artes_722"
            raw.mkdir()
            original=raw/"001.png"
            Image.new("RGB",(102,96),(204,140,25)).save(original)
            original_hash=hashlib.sha256(original.read_bytes()).hexdigest()
            old=root/"cartas_classicas_hd"
            old.mkdir()
            Image.new("RGB",(52,60)).save(old/"001.png")
            card={"id":1,"name":"Horakhty","category":"Monstros",
                  "type_label":"GOD","category_source":"tabela_textual_posicional_iso",
                  "level":12,"atk":5110,"def":5110}
            out=ensure_card_hd(root,card,rom_sha256=SHA_A)
            with Image.open(out) as im:
                self.assertEqual(im.size,SIZE)
            self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),
                             original_hash)
            marker=(old/"001.png.source-sha256").read_text("ascii")
            self.assertEqual(ensure_card_hd(root,card,rom_sha256=SHA_A),out)
            self.assertEqual((old/"001.png.source-sha256").read_text("ascii"), marker)
            another=dict(card,type_label="DRAGON")
            ensure_card_hd(root,another,rom_sha256=SHA_A)
            self.assertNotEqual((old/"001.png.source-sha256").read_text("ascii"),marker)

    def test_bad_id_or_iso_sha_cannot_write(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for card,sha in (({"id":0},SHA_A),({"id":723},SHA_A),
                             ({"id":1},"invalid")):
                with self.assertRaises(ValueError):
                    ensure_card_hd(root,card,rom_sha256=sha)
            self.assertFalse((root/"cartas_classicas_hd").exists())

    def test_shared_card_endpoint_does_not_require_manual_refresh(self):
        source=(ROOT/"scanner/dueltrace_web_desktop.py").read_text("utf8")
        self.assertIn("ensure_card_hd(root,card,rom_sha256=sha)",source)
        self.assertIn('if classic_match:',source)
        scanner=(ROOT/"scanner/scanner_multiiso.py").read_text("utf8")
        self.assertIn("extract_type_names(",scanner)
        self.assertIn('"nomes_tipos_iso.json"',scanner)
        importer=(ROOT/"scanner/importador_perfis.py").read_text("utf8")
        self.assertIn("apply_type_names(",importer)
        graphics=(ROOT/"scanner/fm_deep_assets.py").read_text("utf8")
        self.assertIn("type_name_analysis=type_name_analysis",graphics)


if __name__ == "__main__":
    unittest.main()
