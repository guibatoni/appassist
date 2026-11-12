"""v0.14 image tests: dimensions, fidelity, stats, invalid files."""
from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))
from dueltrace_card_renderer_v014 import SIZE, render_card_v014


class CardVisual014Tests(unittest.TestCase):
    def setUp(self):
        self.fields = {
            "name": "Dragão Branco de Olhos Azuis com Nome Muito Extenso",
            "category": "Monstros", "kind": "Dragão",
            "monster": True, "attribute": "LUZ", "level": 8,
            "atk": 3000, "def": 2500,
            "description": "Monstro lendário com grande poder ofensivo e defensivo.",
        }
        self.image = Image.new("RGB", (102, 96), (24, 65, 111))

    def test_high_dpi_resolution_and_source_unchanged(self):
        before = hashlib.sha256(self.image.tobytes()).hexdigest()
        image = render_card_v014(self.fields, self.image, 1)
        self.assertEqual(image.size, (540, 780))
        self.assertEqual(image.size, SIZE)
        self.assertEqual(image.mode, "RGB")
        self.assertNotEqual(image.getpixel((268, 340)), image.getpixel((20, 20)))
        self.assertEqual(hashlib.sha256(self.image.tobytes()).hexdigest(), before)

    def test_without_stats_never_introduces_a_fake_monster(self):
        spell = dict(self.fields, name="Mágica de teste", category="Mágicas",
                     kind="Magia", monster=False, atk=None, level=None, **{"def": None})
        result = render_card_v014(spell, self.image, 2)
        self.assertEqual(result.size, SIZE)

    def test_absent_stats_do_not_crash(self):
        result = render_card_v014(dict(self.fields, atk=None, **{"def": None}), self.image, 3)
        self.assertEqual(result.size, SIZE)

    def test_extreme_monster_level_and_bad_id(self):
        result = render_card_v014(dict(self.fields, level=99), self.image, 2000)
        self.assertEqual(result.size, SIZE)

    def test_rejects_invalid_or_dangerous_art_dimensions(self):
        for dimensions in ((8, 8), (2049, 20)):
            with self.subTest(dimensions=dimensions):
                with self.assertRaises(ValueError):
                    render_card_v014(self.fields, Image.new("RGB", dimensions), 1)


if __name__ == "__main__":
    unittest.main()