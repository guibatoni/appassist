"""Contract for compact passive rank and fusion popouts in DUELTRACE Alpha.

UI checks are intentionally static; Windows WebView2 needs separate real-world
smoke validation. These rules prevent regressions to the 10-field form.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/"web/components/desktop/floating-tools.tsx"
RANK=ROOT/"web/components/desktop/rank-score-display.tsx"
HOME=ROOT/"web/components/desktop/desktop-page.tsx"
WINDOW=ROOT/"scanner/dueltrace_web_desktop.py"

class FloatingVisorUiTests(unittest.TestCase):
    def test_calculator_popup_only_reads_rank_and_has_no_manual_form(self):
        source=TOOL.read_text(encoding="utf-8")
        calculator=source.split("export function FloatingCalculator()",1)[1]
        calculator=calculator.split("export function FloatingFusionTips()",1)[0]
        self.assertIn("api.get_rank_auto()",calculator)
        self.assertIn("<RankScoreDisplay",calculator)
        for forbidden in ("calculate_spoils(","type=\"number\"",
                          "<input","<select","CRITERIA","Calculadora manual",
                          "setVictory","setFields"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,calculator)

    def test_fusion_popup_is_passive_and_auto_updates_both_kinds(self):
        source=TOOL.read_text(encoding="utf-8")
        fusion=source.split("export function FloatingFusionTips()",1)[1]
        self.assertIn("api.get_hand()",fusion)
        self.assertIn("pairs.slice(0,6)",fusion)
        self.assertIn("chains.slice(0,4)",fusion)
        self.assertIn("Mão",fusion)
        for forbidden in ("onChange","setMode","setExpanded",
                          "Calcular SPOILS","calculate_spoils("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,fusion)

    def test_rank_grade_palette_and_mode_backgrounds(self):
        source=RANK.read_text(encoding="utf-8")
        colors={"S":"#ff4dd7","A":"#ff5353","B":"#facc15",
                "C":"#4ade80","D":"#9ca3af"}
        for band,color in colors.items():
            with self.subTest(band=band):
                self.assertIn(f'{band}:"text-[{color}]"',source)
        self.assertIn('POW:"border border-[#ef555d]/75 bg-[#b42332] text-white"',source)
        self.assertIn('TEC:"border border-[#579bf8]/75 bg-[#1554ab] text-white"',source)
        self.assertIn("rounded-md",source)
        self.assertIn("splitRankCategory(category)",source)
        home=HOME.read_text(encoding="utf-8")
        self.assertIn("import {RankScoreDisplay}",home)
        self.assertIn("<RankScoreDisplay score={ready?rank.score:null}",home)

    def test_windows_keep_native_independence_with_compact_sizes(self):
        source=WINDOW.read_text(encoding="utf-8")
        self.assertIn('("RANK ao vivo — DUELTRACE",390,280)',source)
        self.assertIn('("Dicas de fusões — DUELTRACE",440,600)',source)
        self.assertIn('on_top=True',source)
        self.assertIn('tool_size=tool_geometry(',source)
        self.assertIn('min_width=330 if kind=="calculadora" else 380',source)
        self.assertIn('min_height=230 if kind=="calculadora" else 380',source)
        self.assertIn('min_size=tool_size["min_size"]',source)


if __name__=="__main__":
    unittest.main()
