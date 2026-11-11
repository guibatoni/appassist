"""Regression tests for v52 native Win32 caption drag (no live Windows needed)."""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_native_drag import (
    request_native_caption_drag, WM_NCLBUTTONDOWN, HTCAPTION, VK_LBUTTON,
)
from dueltrace_web_security import ProtectedDesktopApi


class NativeCaptionDragTests(unittest.TestCase):
    def setUp(self):
        self.window=Mock()
        self.form=self.window.native
        self.form.Handle=1234
        self.form.IsDisposed=False
        self.form.IsHandleCreated=True
        self.form.WindowState="Normal"
        self.user32=Mock()
        self.user32.GetAsyncKeyState.return_value=-32768
        # Tests run callback on demand so WinForms STA scheduling is verified.
        self.actions=[]
        self.form.BeginInvoke.side_effect=lambda action: self.actions.append(action)

    def request(self):
        return request_native_caption_drag(
            self.window,user32=self.user32,action_factory=lambda cb: cb)

    def test_native_os_owns_drag_and_begininvoke_schedules_gui_thread(self):
        self.assertTrue(self.request())
        self.form.BeginInvoke.assert_called_once()
        self.user32.SendMessageW.assert_not_called()
        self.actions[0]()
        self.user32.GetAsyncKeyState.assert_called_once_with(VK_LBUTTON)
        self.user32.ReleaseCapture.assert_called_once_with()
        self.user32.SendMessageW.assert_called_once_with(
            1234,WM_NCLBUTTONDOWN,HTCAPTION,0)

    def test_release_before_callback_aborts_stale_gesture(self):
        self.assertTrue(self.request())
        self.user32.GetAsyncKeyState.return_value=0
        self.actions[0]()
        self.user32.SendMessageW.assert_not_called()

    def test_invalid_form_or_maximized_aborts(self):
        self.form.WindowState="Maximized"
        self.assertTrue(self.request())
        self.actions[0]()
        self.user32.SendMessageW.assert_not_called()
        self.actions.clear()
        self.form.WindowState="Normal"
        self.form.IsDisposed=True
        self.assertTrue(self.request())
        self.actions[0]()
        self.user32.SendMessageW.assert_not_called()

    def test_unavailable_native_handle_cannot_start(self):
        self.form.Handle=None
        self.assertTrue(self.request())
        self.actions[0]()
        self.user32.SendMessageW.assert_not_called()

    def test_failure_to_schedule_returns_false(self):
        self.form.BeginInvoke.side_effect=RuntimeError("form closing")
        self.assertFalse(self.request())
        self.user32.SendMessageW.assert_not_called()

    def test_private_bridge_requires_token_and_known_attached_window(self):
        token="a"*64
        api=ProtectedDesktopApi(Mock(),token)
        with self.assertRaises(PermissionError):
            api.drag_window_native("invalid")
        with self.assertRaises(RuntimeError):
            api.drag_window_native(token)
        api._native_window=self.window
        with patch("dueltrace_native_drag.request_native_caption_drag",return_value=True) as drag:
            self.assertEqual(api.drag_window_native(token),{"started":True})
            drag.assert_called_once_with(self.window)
            api._native_maximized=True
            self.assertEqual(api.drag_window_native(token),{"started":False})
            drag.assert_called_once()
            api._native_maximized=False
            api._native_close_requested=True
            self.assertEqual(api.drag_window_native(token),{"started":False})
            drag.assert_called_once()


if __name__=="__main__":
    unittest.main()
