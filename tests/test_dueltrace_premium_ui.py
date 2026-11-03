"""Testes de regressão da identidade visual premium e leitura do scanner.

Usa componentes Tk reais apenas quando Windows disponibiliza sessão gráfica.
Nenhuma ISO comercial ou personagem é empacotado.
"""
from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))

from dueltrace_brand import ico_icon, png_icon
from dueltrace_theme import Panel, NeonButton, blend
from dueltrace_visuals import HeroArt, QuickTile, CardArt
from scanner_multiiso import art_extract
from dueltrace_desktop import DueltraceDesktop, USER_PAGES


class BrandAndExtractionTests(unittest.TestCase):
    def test_all_icon_sizes_are_valid_and_large_icon_is_not_empty(self):
        for size in (16,32,48,64,256):
            blob=png_icon(size)
            self.assertTrue(blob.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertGreater(len(blob),50)
            self.assertNotEqual(blob[45:80],b"\x00"*35)
        self.assertEqual(ico_icon()[:4],b"\x00\x00\x01\x00")

    def test_palette_fixture_outputs_local_art_if_pillow_installed(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow é dependência do pacote final; não está no runner de testes")
        import tempfile
        import struct
        from scanner_multiiso import WA_CARD_SECTOR_START
        offset=WA_CARD_SECTOR_START*2048
        # 1 imagem sintética de 102x96, sem arte comercial.
        wa=bytearray(offset+0x2840)
        wa[offset:offset+0x2640]=bytes([1]*(102*96))
        struct.pack_into("<256H",wa,offset+0x2640,*([0x03FF]*256))
        with tempfile.TemporaryDirectory() as temp:
            count,message=art_extract(bytes(wa),[{"id":1}],Path(temp))
            self.assertEqual(count,1,message)
            img=Image.open(Path(temp)/"001.png")
            self.assertEqual(img.size,(102,96))
        # Um binário insuficiente fornece diagnóstico, não afirma sucesso.
        with tempfile.TemporaryDirectory() as temp2:
            count,message=art_extract(b"tiny",[{"id":1}],Path(temp2))
        self.assertEqual(count,0)
        self.assertIn("insuficiente",message)

    def test_visual_component_contract(self):
        self.assertTrue(callable(Panel))
        self.assertTrue(callable(NeonButton))
        self.assertTrue(callable(HeroArt))
        self.assertTrue(callable(QuickTile))
        self.assertTrue(callable(CardArt))
        self.assertEqual([key for _,key in USER_PAGES],
                         ["inicio","mods","cartas","fusoes"])
        self.assertEqual(blend("#000000","#FFFFFF",0.5),"#808080")


@unittest.skipUnless(sys.platform=="win32","Captura Tk no runner Windows")
class WindowTests(unittest.TestCase):
    def test_navigation_and_card_panels_draw_without_exception(self):
        import tempfile
        import tkinter as tk
        from auto_mods import ModCatalog
        with tempfile.TemporaryDirectory() as temp:
            try:
                app=DueltraceDesktop(catalog=ModCatalog(Path(temp)))
            except tk.TclError as exc:
                if "display" in str(exc).lower() or "screen" in str(exc).lower():
                    self.skipTest(f"Runner sem display: {exc}")
                raise
            try:
                app.withdraw()
                app.update_idletasks()
                for _,key in USER_PAGES:
                    app.go(key)
                    app.update()
                self.assertTrue(hasattr(app,"mod_details_ai") or app.active_page=="fusoes")
                icon=png_icon(64)
                self.assertGreater(len(icon),200)
            finally:
                app.destroy()


if __name__=="__main__":
    unittest.main()
