"""Responsive Windows sizing and layout contracts for DUELTRACE.

Covers screen ratios without changing OS monitor resolution, game RAM,
license state or ISO data. CSS/React still need real on-screen QA.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_display_layout import window_geometry,tool_geometry,windows_work_area

CSS=(ROOT/"web/app/globals.css").read_text(encoding="utf-8")
SHELL=(ROOT/"web/components/shell/app-shell.tsx").read_text(encoding="utf-8")
TOP=(ROOT/"web/components/shell/top-bar.tsx").read_text(encoding="utf-8")
SIDE=(ROOT/"web/components/shell/sidebar.tsx").read_text(encoding="utf-8")
WINDOW=(ROOT/"web/components/shell/window-controls.tsx").read_text(encoding="utf-8")
MAIN=(ROOT/"web/components/desktop/desktop-page.tsx").read_text(encoding="utf-8")
DROPS=(ROOT/"web/components/desktop/drops-page.tsx").read_text(encoding="utf-8")
PREVIEW=(ROOT/"web/components/desktop/card-hover-preview.tsx").read_text(encoding="utf-8")
UPDATES=(ROOT/"web/components/shell/update-checker.tsx").read_text(encoding="utf-8")
NATIVE=(ROOT/"scanner/dueltrace_web_desktop.py").read_text(encoding="utf-8")
FLOATING=(ROOT/"web/components/desktop/floating-tools.tsx").read_text(encoding="utf-8")


class DisplayGeometryTests(unittest.TestCase):
    def test_standard_portrait_and_ultrawide_displays(self):
        # Width x height in Windows logical pixels; includes all requested
        # proportions and very small portrait Windows installations.
        cases=[
            ("16:9 Full HD",1920,1080),
            ("16:9 HD",1366,768),
            ("16:10",1280,800),
            ("4:3",1024,768),
            ("5:4",1280,1024),
            ("21:9",2560,1080),
            ("32:9",3840,1080),
            ("9:16 portrait",720,1280),
            ("9:16 small",360,640),
            ("narrow Windows",320,568),
        ]
        for name,width,height in cases:
            with self.subTest(display=name):
                shape=window_geometry(width,height)
                self.assertGreater(shape["width"],0)
                self.assertGreater(shape["height"],0)
                self.assertLessEqual(shape["width"],width)
                self.assertLessEqual(shape["height"],height)
                self.assertLessEqual(shape["min_width"],shape["width"])
                self.assertLessEqual(shape["min_height"],shape["height"])
                self.assertLessEqual(shape["min_width"],340)
                self.assertLessEqual(shape["min_height"],460)

    def test_portrait_remains_tall_and_ultrawide_can_use_width(self):
        portrait=window_geometry(720,1280)
        self.assertLess(portrait["width"]/portrait["height"],0.7)
        self.assertGreater(portrait["height"],portrait["width"])
        ultrawide=window_geometry(2560,1080)
        self.assertGreaterEqual(ultrawide["width"],1750)
        self.assertLessEqual(ultrawide["height"],900)

    def test_popup_uses_own_dimensions_but_cannot_exceed_screen(self):
        for width,height in ((360,640),(720,1280),(1024,768),(2560,1080)):
            for desired,minimum in (((390,280),(330,230)),
                                    ((440,600),(380,380))):
                with self.subTest(size=(width,height),kind=desired):
                    shape=tool_geometry(
                        width,height,*desired,
                        min_width=minimum[0],min_height=minimum[1])
                    self.assertLessEqual(shape["width"],width)
                    self.assertLessEqual(shape["height"],height)
                    self.assertLessEqual(shape["min_size"][0],shape["width"])
                    self.assertLessEqual(shape["min_size"][1],shape["height"])

    def test_invalid_work_area_or_popup_is_rejected(self):
        for width,height in ((0,100),(300,0),(-1,800),(500,-2),
                             (500.0,500),(True,800)):
            with self.subTest(size=(width,height)),self.assertRaises(ValueError):
                window_geometry(width,height)
        with self.assertRaises(ValueError):
            tool_geometry(720,1280,440,0,min_width=380,min_height=380)
        if sys.platform!="win32":
            with self.assertRaises(OSError):
                windows_work_area()

    def test_native_window_uses_work_area_not_fixed_1100x700(self):
        self.assertIn("work_width,work_height=windows_work_area()",NATIVE)
        self.assertIn("main_size=window_geometry(work_width,work_height)",NATIVE)
        self.assertIn('width=main_size["width"],height=main_size["height"]',NATIVE)
        self.assertIn('min_size=(main_size["min_width"],main_size["min_height"])',NATIVE)
        self.assertIn("tool_size=tool_geometry(",NATIVE)
        self.assertIn('min_size=tool_size["min_size"]',NATIVE)
        self.assertNotIn("min_size=(1100,700)",NATIVE)
        self.assertIn("frameless=True,easy_drag=False,resizable=True",NATIVE)


class ResponsiveUiContracts(unittest.TestCase):
    def test_small_screen_has_no_clipped_toolbar_controls(self):
        self.assertIn("flex-wrap",TOP)
        self.assertIn("sm:order-2 sm:w-auto",TOP)
        self.assertIn('order-2 shrink-0 sm:order-3',TOP)
        self.assertIn("<WindowControls />",TOP)
        self.assertIn("h-8 w-8",WINDOW)
        self.assertIn("sm:h-9 sm:w-10",WINDOW)
        self.assertIn("aria-label=\"Fechar DUELTRACE\"",WINDOW)
        self.assertIn("onPointerDown={onHeaderPointerDown}",TOP)
        self.assertIn("api.drag_window_native()",TOP)
        self.assertNotIn("setPointerCapture(event.pointerId)",TOP)

    def test_navigation_all_tabs_visible_even_in_portrait(self):
        self.assertIn("grid-cols-3",SIDE)
        self.assertIn("min-[600px]:grid-cols-5",SIDE)
        self.assertIn("lg:flex lg:flex-col",SIDE)
        self.assertIn('dt-nav-sidebar',SIDE)
        self.assertIn('dt-nav-list',SIDE)
        self.assertIn('dt-nav-link',SIDE)
        self.assertIn("@media (orientation: portrait) and (min-width: 1024px)",CSS)
        self.assertIn(".dt-shell-body { flex-direction: column; }",CSS)
        for menu in ("Início","Biblioteca de Mods","Biblioteca de Cartas",
                     "Fusões","Drops"):
            self.assertIn(menu,SIDE)
        self.assertIn('aria-label="Navegação principal"',SIDE)

    def test_adaptive_layouts_are_based_on_actual_panel_width(self):
        self.assertIn("dueltrace-main",SHELL)
        self.assertIn("container-type: inline-size",CSS)
        for selector in (".dt-hand-grid", ".dt-adaptive-cards",
                         ".dt-adaptive-drops"):
            self.assertIn(selector,CSS)
        self.assertIn('className="dt-hand-grid"',MAIN)
        self.assertIn('className="dt-adaptive-cards"',MAIN)
        self.assertIn('className="dt-adaptive-drops"',DROPS)
        self.assertIn('className="mt-4 grid grid-cols-2',MAIN)
        self.assertNotIn("function CardDropSourcesPanel(",MAIN)
        self.assertIn('max-w-[2100px]',SHELL)

    def test_popups_and_updater_remain_fully_visible(self):
        self.assertIn('max-h-[calc(100dvh-16px)]',PREVIEW)
        self.assertIn('grid gap-4 sm:grid-cols-[240px_minmax(0,1fr)]',PREVIEW)
        self.assertNotIn("CARD_PREVIEW_DELAY_MS=1000",PREVIEW)
        self.assertIn("max-h-[calc(100dvh-2rem)]",UPDATES)
        self.assertIn("createPortal(",UPDATES)
        self.assertIn("overflow-y-auto",UPDATES)
        self.assertIn("Atualizar agora",UPDATES)
        self.assertIn("flex flex-wrap items-start justify-center gap-1",FLOATING)
        self.assertIn("min-[390px]:w-[78px]",FLOATING)
        self.assertIn("aria-label=\"Fechar visor\"",FLOATING)

    def test_ratio_support_does_not_use_zoom_or_change_game_data(self):
        for source in (SHELL,TOP,SIDE,MAIN,DROPS):
            self.assertNotIn("zoom:",source)
        display=(ROOT/"scanner/dueltrace_display_layout.py").read_text(encoding="utf-8")
        self.assertNotIn("ChangeDisplaySettings",display)
        self.assertNotIn("WriteProcessMemory",display)
        self.assertNotIn("desktopApi()",display)


if __name__=="__main__":
    unittest.main()
