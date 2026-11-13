"""Overlay calculator parity: actual Exo 2 glyphs and POW/TEC color chips."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_epsxe_rank_overlay import (
    BAND_COLORS, MODE_COLORS, MUTED_COLOR, WHITE_COLOR,
    overlay_font_path, overlay_geometry, render_rank_overlay_bitmap,
)


class RankOverlayCalculatorParityTests(unittest.TestCase):
    def test_same_exo2_font_as_calculator_is_available_and_bundled(self):
        self.assertTrue((ROOT/"web/app/fonts/Exo2-Variable.ttf").is_file())
        self.assertEqual(overlay_font_path().name,"Exo2-Variable.ttf")
        frontend=(ROOT/"web/app/layout.tsx").read_text(encoding="utf8")
        self.assertIn('Exo2-Variable.ttf',frontend)
        self.assertIn('variable: "--font-exo"',frontend)
        css=(ROOT/"web/app/globals.css").read_text(encoding="utf8")
        self.assertIn("--font-display: var(--font-exo)",css)
        pipeline=(ROOT/".github/workflows/validar-webui-desktop.yml").read_text("utf8")
        self.assertIn('--add-data "web/app/fonts/Exo2-Variable.ttf;fonts"',pipeline)
        self.assertIn("--hidden-import PIL.ImageTk",pipeline)
        self.assertIn('_internal/fonts/Exo2-Variable.ttf',pipeline)

    def test_python_rank_palette_is_pixel_identical_to_react_components(self):
        react=(ROOT/"web/components/desktop/rank-score-display.tsx").read_text("utf8")
        css=(ROOT/"web/app/globals.css").read_text("utf8")
        for grade,color in BAND_COLORS.items():
            with self.subTest(grade=grade):
                if grade == "Z":
                    self.assertIn('Z:"text-gold"',react)
                    self.assertIn(f"--gold: {color}",css)
                else:
                    self.assertIn(f'{grade}:"text-[{color}]"',react)
        for mode,(bg,border) in MODE_COLORS.items():
            with self.subTest(mode=mode):
                self.assertIn(f'bg-[{bg}]',react)
                self.assertIn(f'border-[{border}]/75',react)
        self.assertIn(f"--muted: {MUTED_COLOR}",css)
        self.assertEqual(WHITE_COLOR,"#ffffff")

    def test_render_paint_is_transparent_except_text_and_rounded_chip(self):
        for rank,bg in (("S-POW","#b42332"),("A-TEC","#1554ab"),
                        ("Z-POW","#b42332")):
            with self.subTest(rank=rank):
                img=render_rank_overlay_bitmap(
                    ("RANK: 60",rank,"PREVISÃO"),250,116)
                self.assertEqual(img.size,(250,116))
                self.assertEqual(img.mode,"RGBA")
                self.assertEqual(img.getpixel((0,0))[3],0)
                self.assertEqual(img.getpixel((249,115))[3],0)
                self.assertGreater(img.getbbox()[2],100)
                rgb=tuple(bytes.fromhex(bg[1:]))
                # With 3x antialiasing, interior chip pixels keep exact fill.
                painted=sum(1 for p in img.getdata()
                            if p[:3]==rgb and p[3]==255)
                self.assertGreater(painted,25)

    def test_rank_grade_uses_colored_glyph_and_score_remains_white(self):
        img=render_rank_overlay_bitmap(
            ("RANK: 60","S-POW","PREVISÃO"),250,116)
        magenta=tuple(bytes.fromhex(BAND_COLORS["S"][1:]))
        colors={pixel[:3] for pixel in img.getdata() if pixel[3]==255}
        self.assertIn(magenta,colors)
        self.assertIn((255,255,255),colors)

    def test_calibrating_label_has_no_misleading_grade_or_colored_chip(self):
        img=render_rank_overlay_bitmap(
            ("RANK: —","ANALISANDO","DUELO DETECTADO"),250,116)
        pixels={p[:3] for p in img.getdata() if p[3]==255}
        for color in BAND_COLORS.values():
            self.assertNotIn(tuple(bytes.fromhex(color[1:])),pixels)
        for bg,_ in MODE_COLORS.values():
            self.assertNotIn(tuple(bytes.fromhex(bg[1:])),pixels)
        self.assertNotEqual(img.getbbox(),None)

    def test_dimensions_remain_inside_epsxe_client_after_font_upgrade(self):
        for pos in ("top-center-right","top-left","top-center","top-right"):
            for scale in (70,100,160):
                x,y,w,h=overlay_geometry((120,50,800,600),pos,scale)
                self.assertGreaterEqual(x,120)
                self.assertGreaterEqual(y,50)
                self.assertLessEqual(x+w,920)
                self.assertLessEqual(y+h,650)

    def test_incorrect_payloads_fail_closed(self):
        for lines,w,h in ((("RANK: 60","S-POW"),250,116),
                          (("RANK: 60","S-POW","PREVISÃO"),0,116),
                          (("RANK: 60","S-POW","PREVISÃO"),900,116),
                          (("RANK: 60","S-POW","x"*50),250,116)):
            with self.subTest(value=(lines,w,h)):
                with self.assertRaises(ValueError):
                    render_rank_overlay_bitmap(lines,w,h)


if __name__=="__main__":
    unittest.main()
