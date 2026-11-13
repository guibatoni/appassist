"""The ePSXe overlay must never fabricate RANK or intercept/modify the game."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scanner"))

from dueltrace_epsxe_rank_overlay import (
    DEFAULT, EpsxeRankOverlay, normalized_settings,
    overlay_geometry, rank_overlay_text,
    read_overlay_settings, save_overlay_settings,
)
from dueltrace_web_security import ProtectedDesktopApi
from dueltrace_web_bridge import DueltraceWebBridge


class RankOverlayTests(unittest.TestCase):
    def test_only_provisional_valid_rank_is_rendered(self):
        rank = {"ready": True, "state": "provisional", "score": 60,
                "category": "S-POW", "status": "Projeção"}
        self.assertEqual(rank_overlay_text(rank),
                         ("RANK: 60", "S-POW", "PREVISÃO"))
        rank["category"] = "Z-POW"
        self.assertEqual(rank_overlay_text(rank)[1], "Z-POW")
        for wrong in (-1001, 1001, 60.0, None, True):
            with self.subTest(score=wrong):
                self.assertIsNone(rank_overlay_text({**rank, "score": wrong}))
        for category in ("NONE", "SPOW", "S-POW malicious", "", "S-P0W"):
            with self.subTest(category=category):
                self.assertIsNone(rank_overlay_text({**rank, "category": category}))
        self.assertIsNone(rank_overlay_text({**rank, "ready": False}))
        self.assertIsNone(rank_overlay_text({**rank, "state": "unavailable"}))

    def test_candidate_lp_shows_reading_not_a_fictitious_rank(self):
        for state in ("auto_calibrating", "needs_lp_confirmation",
                      "needs_ram_validation"):
            result = rank_overlay_text({"ready": False, "state": state,
                                        "candidateLp": 8000,
                                        "score": 95, "category": "S-POW"})
            self.assertIsNotNone(result)
            self.assertEqual(result[0], "RANK: —")
            self.assertEqual(result[1], "ANALISANDO")
        for lp in (-1, 0, 32767, None, True):
            self.assertIsNone(rank_overlay_text({
                "ready": False, "state": "auto_calibrating",
                "candidateLp": lp}))
        self.assertIsNone(rank_overlay_text({"ready":False,
                       "state":"unavailable","candidateLp":8000}))

    def test_overlay_within_epsxe_client_not_titlebar_for_all_positions(self):
        game=(140,88,1280,720)
        for position in ("top-center-right","top-left","top-center","top-right"):
            for scale in (70,100,160):
                with self.subTest(position=position,scale=scale):
                    x,y,w,h=overlay_geometry(game,position,scale)
                    self.assertGreaterEqual(x,140)
                    self.assertGreaterEqual(y,88)
                    self.assertLessEqual(x+w,1420)
                    self.assertLessEqual(y+h,808)
        self.assertIsNone(overlay_geometry((0,0,180,130),"top-left",100))
        self.assertIsNone(overlay_geometry((1,2,3),"top-left",100))
        x,y,w,h=overlay_geometry((-1500,-800,1024,700),"top-center-right",120)
        self.assertLess(x,0)
        self.assertLess(y,0)

    def test_settings_are_opt_in_strict_atomic_and_preserve_prior_config(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"settings.json"
            path.write_text(json.dumps({
                "epsxe_executable":"D:/ePSXe/ePSXe.exe",
                "window_geometry":{"width":1000,"height":700},
                "ui_language":"pt-BR",
                "fusion_tips_visible":True,
            }),encoding="utf8")
            self.assertEqual(read_overlay_settings(path),DEFAULT)
            config=save_overlay_settings(path,True,"top-center-right",120,85)
            self.assertEqual(config["scale"],120)
            self.assertEqual(read_overlay_settings(path),config)
            persisted=json.loads(path.read_text("utf8"))
            self.assertEqual(persisted["ui_language"],"pt-BR")
            self.assertEqual(persisted["epsxe_executable"],"D:/ePSXe/ePSXe.exe")
            self.assertEqual(persisted["window_geometry"]["width"],1000)
            self.assertTrue(persisted["fusion_tips_visible"])
            self.assertEqual(
                sorted(x.name for x in Path(temp).iterdir()), ["settings.json"])
            for args in ((1,"top-center",100,95), (True,"bottom",100,95),
                         (True,"top-left",True,95),
                         (True,"top-right",100,101),
                         (True,"top-right",100,0)):
                with self.subTest(args=args):
                    with self.assertRaises(ValueError):
                        save_overlay_settings(path,*args)
            self.assertEqual(read_overlay_settings(path),config)

    def test_untrusted_json_is_clamped_and_boolean_not_truthy(self):
        settings=normalized_settings({
            "enabled":1,"position":"unknown",
            "scale":999,"opacity":"100"})
        self.assertEqual(settings,DEFAULT)

    def test_overlay_is_inert_by_default_and_on_unsupported_platforms(self):
        with tempfile.TemporaryDirectory() as temp:
            bridge=Mock()
            engine=EpsxeRankOverlay(bridge,Path(temp)/"settings.json",
                                    locator=lambda:None)
            self.assertFalse(engine.status()["enabled"])
            self.assertFalse(engine.status()["visible"])
            if sys.platform!="win32":
                self.assertFalse(engine.start())
            changed=engine.configure({
                "enabled":True,"position":"top-center","scale":80,"opacity":95})
            self.assertTrue(changed["enabled"])
            engine.stop()

    def test_bridge_and_security_share_one_authenticated_settings_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            bridge=object.__new__(DueltraceWebBridge)
            bridge._lock=threading.RLock()
            bridge.settings_path=Path(tmp)/"settings.json"
            bridge._rank_overlay=None
            token="r"*48
            api=ProtectedDesktopApi(bridge,token)
            with self.assertRaises(PermissionError):
                api.set_rank_overlay_settings("invalid",True,"top-center",100,95)
            saved=api.set_rank_overlay_settings(token,True,"top-center",100,95)
            self.assertTrue(saved["enabled"])
            self.assertEqual(saved["scale"],100)
            self.assertTrue(api.get_rank_overlay_settings(token)["enabled"])

    def test_windows_entrypoint_lifetime_and_no_network_or_ram_writes(self):
        entry=(ROOT/"scanner/dueltrace_web_desktop.py").read_text("utf8")
        self.assertIn("rank_overlay.start()",entry)
        self.assertIn("rank_overlay.stop()",entry)
        self.assertIn("bridge._rank_overlay=rank_overlay",entry)
        source=(ROOT/"scanner/dueltrace_epsxe_rank_overlay.py").read_text("utf8")
        self.assertIn("WS_EX_LAYERED | TRANSPARENT | TOOLWINDOW | NOACTIVATE",source)
        self.assertIn('get_rank_auto()  # cache ONLY',source)
        for forbidden in ("WriteProcessMemory","requests.post(", "websocket",
                          "GetAsyncKeyState","SendInput("):
            self.assertNotIn(forbidden,source)

    def test_settings_ui_exposes_toggle_position_size_opacity(self):
        ui=(ROOT/"web/components/desktop/settings-page.tsx").read_text("utf8")
        self.assertIn("Overlay de RANK no ePSXe",ui)
        self.assertIn("Ativar sobreposição automática",ui)
        self.assertIn("get_rank_overlay_settings()",ui)
        self.assertIn("set_rank_overlay_settings(",ui)
        self.assertIn("Tamanho",ui)
        self.assertIn("Opacidade",ui)
        self.assertIn("fullscreen",ui.lower())


if __name__ == "__main__":
    unittest.main()
