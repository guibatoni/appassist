"""Cartas clássicas HD: dados reais, fundo preservado, cache e rotas locais."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))

from dueltrace_classic_cards import (
    SIZE, card_fields, render_card, render_card_pack,
)


class ClassicCardsTest(unittest.TestCase):
    def setUp(self):
        self.card = {
            "id": 1, "nome": "Dragão de olhos azuis do mod",
            "tipo": 0, "nivel": 8, "atributo": 3,
            "atk": 3000, "def": 2500,
            "descricao": "Dragão lendário extraído do próprio jogo.",
        }

    def test_render_classic_reference_size_and_non_destructive_art(self):
        original = Image.new("RGB", (102, 96), (15, 70, 190))
        before = original.tobytes()
        image = render_card(self.card, original)
        self.assertEqual(image.size, (360, 520))
        self.assertEqual(image.mode, "RGB")
        self.assertNotEqual(image.getpixel((6, 6)), image.getpixel((180, 250)))
        self.assertEqual(original.tobytes(), before)
        self.assertEqual(card_fields(self.card)["level"], 8)
        self.assertEqual(card_fields(self.card)["atk"], 3000)
        self.assertEqual(card_fields(self.card)["def"], 2500)
        self.assertEqual(card_fields(self.card)["category"], "Monstros")

    def test_non_monster_never_invents_atk_level_or_element(self):
        spell = {"id": 4, "name": "Carta de magia", "tipo": 20,
                 "atk": 9000, "def": 9000, "nivel": 9}
        parsed = card_fields(spell)
        self.assertEqual(parsed["category"], "Mágicas")
        self.assertIsNone(parsed["level"])
        self.assertIsNone(parsed["atk"])
        self.assertIsNone(parsed["def"])
        image = render_card(spell, Image.new("RGB", (102, 96)))
        self.assertEqual(image.size, SIZE)

    def test_cache_generated_once_and_metadata_changes_invalidate(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            original = home / "artes_722"
            enhanced = home / "artes_upscaled"
            cache = home / "cartas_classicas_hd"
            original.mkdir()
            enhanced.mkdir()
            source = original / "001.png"
            Image.new("RGB", (102, 96), (90, 20, 20)).save(source)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            first = render_card_pack([self.card], original, enhanced, cache)
            self.assertEqual(first["rendered"], 1)
            self.assertEqual(first["available"], 1)
            self.assertEqual(first["dimensions"], [360, 520])
            self.assertTrue(first["originalsPreserved"])
            second = render_card_pack([self.card], original, enhanced, cache)
            self.assertEqual(second["cached"], 1)
            self.assertEqual(second["rendered"], 0)
            changed = dict(self.card, atk=3200)
            third = render_card_pack([changed], original, enhanced, cache)
            self.assertEqual(third["rendered"], 1)
            self.assertEqual(third["cached"], 0)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)
            manifest = json.loads((cache / "cartas-hd-cache.json").read_text("utf-8"))
            self.assertEqual(manifest["revision"], 1)
            with Image.open(cache / "001.png") as generated:
                self.assertEqual(generated.size, SIZE)

    def test_high_resolution_source_is_preferred_over_original_art(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            raw = home / "artes_722"
            hd = home / "artes_upscaled"
            out = home / "cartas_classicas_hd"
            raw.mkdir()
            hd.mkdir()
            Image.new("RGB", (102, 96), (220, 20, 20)).save(raw / "001.png")
            Image.new("RGB", (306, 288), (20, 220, 20)).save(hd / "001.png")
            render_card_pack([self.card], raw, hd, out)
            with Image.open(out / "001.png") as card:
                pixel = card.getpixel((180, 245))
                self.assertGreater(pixel[1], pixel[0])

    def test_render_rejects_oversize_image_without_touching_input(self):
        with self.assertRaises(ValueError):
            render_card(self.card, Image.new("RGB", (4096, 4096)))
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            raw = home / "artes_722"
            raw.mkdir()
            with self.assertRaises(ValueError):
                render_card_pack([self.card], raw, raw, raw)

    def test_pipeline_and_view_share_same_iso_bound_full_card(self):
        scanner=(ROOT/"scanner/fm_deep_assets.py").read_text("utf-8")
        web=(ROOT/"scanner/dueltrace_web_desktop.py").read_text("utf-8")
        client=(ROOT/"web/lib/desktop.ts").read_text("utf-8")
        library=(ROOT/"web/components/desktop/desktop-page.tsx").read_text("utf-8")
        drops=(ROOT/"web/components/desktop/drops-page.tsx").read_text("utf-8")
        detail=(ROOT/"web/components/desktop/card-hover-preview.tsx").read_text("utf-8")
        self.assertIn('out / "cartas_classicas_hd"',scanner)
        self.assertIn('CLASSIC_CARD_PATTERN',web)
        self.assertIn('"cartas_classicas_hd" if classic_match',web)
        self.assertIn('active.get("sha256")!=sha',web)
        self.assertIn('/__card_hd__/',client)
        self.assertIn('cardClassicHd(sha,card.id)',library)
        self.assertIn('cardClassicHd(sha,id)',drops)
        self.assertIn('cardClassicHd(sha,card.id)',detail)
        self.assertNotIn('<MonsterStats card={card} className="mt-1 text-center"/>',library)


if __name__ == "__main__":
    unittest.main()
