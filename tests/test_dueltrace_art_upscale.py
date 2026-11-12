"""Automatic conservative PS1 art upscaling, no generative models or ROMs."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner"))

from PIL import Image
from dueltrace_art_upscale import (
    UPSCALE_FACTOR, MANIFEST_FILE, upscale_extracted_arts,
)


def make_original(folder: Path, cid: int, *, tint: int = 80) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (102, 96), (tint, 60, 120))
    for x in range(102):
        im.putpixel((x, 45), (x * 2 % 256, 128, 100))
    path = folder / f"{cid:03d}.png"
    im.save(path)
    return path


class ArtUpscaleTests(unittest.TestCase):
    def test_originals_are_unchanged_and_hd_matches_expected_dimensions(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "artes_722"
            output = Path(td) / "artes_upscaled"
            one = make_original(source, 1)
            two = make_original(source, 2)
            before = {x.name: hashlib.sha256(x.read_bytes()).hexdigest()
                      for x in (one, two)}
            first = upscale_extracted_arts(source, output)
            self.assertEqual(UPSCALE_FACTOR, 3)
            self.assertEqual(first["generated"], 2)
            self.assertEqual(first["cached"], 0)
            self.assertEqual(first["available"], 2)
            self.assertEqual(first["failed"], 0)
            self.assertTrue(first["originalsPreserved"])
            with Image.open(output / "001.png") as im:
                self.assertEqual(im.size, (306, 288))
                self.assertEqual(im.getpixel((20, 20)), (80, 60, 120))
            for item in (one, two):
                self.assertEqual(hashlib.sha256(item.read_bytes()).hexdigest(),
                                 before[item.name])
                with Image.open(item) as original:
                    self.assertEqual(original.size, (102, 96))
            info = json.loads((output / MANIFEST_FILE).read_text("utf-8"))
            self.assertEqual(info["algorithm"], "Pillow Lanczos 3x + UnsharpMask leve")
            self.assertEqual(info["schema"], 1)

    def test_repeated_extraction_reuses_cache_and_rebuilds_only_changed_art(self):
        with tempfile.TemporaryDirectory() as td:
            source, output = Path(td) / "artes_722", Path(td) / "artes_upscaled"
            make_original(source, 1)
            make_original(source, 2)
            upscale_extracted_arts(source, output)
            repeat = upscale_extracted_arts(source, output)
            self.assertEqual((repeat["generated"], repeat["cached"]), (0, 2))
            make_original(source, 2, tint=130)
            updated = upscale_extracted_arts(source, output)
            self.assertEqual((updated["generated"], updated["cached"]), (1, 1))
            with Image.open(output / "002.png") as img:
                self.assertEqual(img.getpixel((20,20)), (130, 60, 120))

    def test_invalid_image_is_ignored_without_erasing_original(self):
        with tempfile.TemporaryDirectory() as td:
            source,output=Path(td)/"artes_722",Path(td)/"artes_upscaled"
            original=make_original(source,1)
            invalid=source/"002.png"
            invalid.write_bytes(b"not-a-PS1-art")
            result=upscale_extracted_arts(source,output)
            self.assertEqual(result["generated"],1)
            self.assertEqual(result["failed"],1)
            self.assertEqual(invalid.read_bytes(),b"not-a-PS1-art")
            self.assertEqual(original.is_file(),True)
            self.assertFalse((output/"002.png").exists())

    def test_does_not_overwrite_source_directory(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"artes_722"
            make_original(source,1)
            with self.assertRaises(ValueError):
                upscale_extracted_arts(source,source)
            with self.assertRaises(ValueError):
                upscale_extracted_arts(source,source/"nested")

    def test_extraction_invokes_upscaler_and_hd_endpoint_is_source_bound(self):
        root=Path(__file__).resolve().parents[1]
        extractor=(root/"scanner/fm_deep_assets.py").read_text("utf-8")
        web=(root/"scanner/dueltrace_web_desktop.py").read_text("utf-8")
        ui=(root/"web/components/desktop/card-hover-preview.tsx").read_text("utf-8")
        self.assertIn("upscale_extracted_arts(",extractor)
        self.assertIn('out / "artes_upscaled"',extractor)
        self.assertIn("ART_HD_PATTERN",web)
        self.assertIn('"artes_upscaled" if hd_match',web)
        self.assertIn('active.get("sha256")!=sha',web)
        self.assertIn("image.is_relative_to(root)",web)
        self.assertIn("cardArtHd(sha,card.id)",ui)
        self.assertIn('source==="original"?cardArt(sha,card.id)',ui)


if __name__ == "__main__":
    unittest.main()
