"""Native Window.move drag regression cases; no live HWND required.

Our previous pywebview-drag-region did not move the embedded WebView2
window. The v51 mouse drag is a token-bound begin/step/end protocol that
moves only the currently attached DUELTRACE main window.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))
from dueltrace_web_security import ProtectedDesktopApi


class NativePointerDragV51Tests(unittest.TestCase):
    def setUp(self):
        self.token="z"*64
        self.api=ProtectedDesktopApi(Mock(),self.token)
        self.window=Mock()
        self.window.x=200
        self.window.y=175
        self.window.native.WindowState="Normal"
        self.api._native_window=self.window

    def test_drag_moves_only_attached_window_relative_to_start(self):
        started=self.api.drag_window_begin(self.token,400,300)
        self.assertEqual(started,{"started":True,"dragId":1})
        self.assertEqual(self.api.drag_window_move(self.token,1,430,350),
                         {"moved":True})
        self.window.move.assert_called_once_with(230,225)
        self.assertEqual(self.api.drag_window_move(self.token,1,460,340),
                         {"moved":True})
        self.window.move.assert_called_with(260,215)
        # Coordinates are always derived from original drag point, avoiding
        # drift even when the WebView2 bridge retries/delays a request.
        self.assertEqual(self.window.move.call_count,2)
        self.assertEqual(self.api.drag_window_end(self.token,1),{"ended":True})
        self.assertEqual(self.api.drag_window_move(self.token,1,470,370),
                         {"moved":False})
        self.assertEqual(self.window.move.call_count,2)

    def test_move_start_end_all_require_correct_session_token(self):
        with self.assertRaises(PermissionError):
            self.api.drag_window_begin("wrong",10,10)
        started=self.api.drag_window_begin(self.token,100,100)
        with self.assertRaises(PermissionError):
            self.api.drag_window_move("wrong",started["dragId"],140,150)
        with self.assertRaises(PermissionError):
            self.api.drag_window_end("wrong",started["dragId"])
        self.window.move.assert_not_called()

    def test_invalid_and_remote_window_coordinates_are_rejected(self):
        for invalid in ("20",12.2,True,None,[],{},50001,-50001):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    self.api.drag_window_begin(self.token,invalid,0)
        self.api.drag_window_begin(self.token,200,250)
        for invalid in ("20",1.5,False,None,[],{},50100):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    self.api.drag_window_move(self.token,1,invalid,0)
        self.assertEqual(self.api.drag_window_move(self.token,1,12000,250),
                         {"moved":False})
        self.window.move.assert_not_called()

    def test_stale_drag_id_never_moves_the_window(self):
        first=self.api.drag_window_begin(self.token,100,100)
        second=self.api.drag_window_begin(self.token,400,400)
        self.assertEqual(second,{"started":True,"dragId":2})
        self.assertEqual(self.api.drag_window_move(self.token,first["dragId"],401,401),
                         {"moved":False})
        self.window.move.assert_not_called()
        # Stale callbacks cannot cancel the second, newer drag.
        self.assertEqual(
            self.api.drag_window_move(self.token,second["dragId"],430,435),
            {"moved":True})
        self.window.move.assert_called_once_with(230,210)
        self.window.move.reset_mock()
        # User can then immediately restart a valid drag.
        started=self.api.drag_window_begin(self.token,200,200)
        self.assertEqual(started["dragId"],3)
        self.assertEqual(self.api.drag_window_move(self.token,3,210,210),
                         {"moved":True})
        self.window.move.assert_called_once_with(210,185)

    def test_expired_drag_session_is_rejected(self):
        with patch("dueltrace_web_security.time.monotonic",side_effect=[100.0,111.0]):
            self.api.drag_window_begin(self.token,100,100)
            self.assertEqual(self.api.drag_window_move(self.token,1,120,130),
                             {"moved":False})
        self.window.move.assert_not_called()

    def test_maximized_window_or_missing_window_is_not_dragged(self):
        self.api._native_maximized=True
        self.assertFalse(self.api.drag_window_begin(self.token,100,100)["started"])
        self.api._native_maximized=False
        self.window.native.WindowState="Maximized"
        self.assertFalse(self.api.drag_window_begin(self.token,100,100)["started"])
        self.window.native.WindowState="Normal"
        self.api._native_window=None
        with self.assertRaises(RuntimeError):
            self.api.drag_window_begin(self.token,100,100)

    def test_negative_multimonitor_positions_supported(self):
        self.window.x=-1280
        self.window.y=100
        start=self.api.drag_window_begin(self.token,-1000,150)
        self.assertTrue(start["started"])
        self.api.drag_window_move(self.token,start["dragId"],-1180,200)
        self.window.move.assert_called_once_with(-1460,150)

    def test_frontend_moves_only_when_mouse_held_and_excludes_buttons(self):
        ui=(ROOT/"web/components/shell/top-bar.tsx").read_text(encoding="utf-8")
        types=(ROOT/"web/lib/desktop.ts").read_text(encoding="utf-8")
        self.assertIn("event.button !== 0",ui)
        self.assertIn("event.isPrimary",ui)
        self.assertIn("api.drag_window_native()",ui)
        self.assertNotIn("setPointerCapture(event.pointerId)",ui)
        self.assertNotIn("onLostPointerCapture={onHeaderPointerEnd}",ui)
        self.assertIn('target.closest(\'button,a,input,textarea,select',ui)
        self.assertNotIn("state.api.drag_window_move(state.dragId, x, y)",ui)
        self.assertNotIn("state.api.drag_window_end(state.dragId)",ui)
        self.assertNotIn("state.sending = true",ui)
        self.assertIn("drag_window_native: () => native.drag_window_native(token)",types)


if __name__=="__main__":
    unittest.main()
