"""Regression tests for frameless Windows edge resizing (no GUI needed).

The actual Win32 resize cursors must still be inspected on Windows; tests
ensure we're only enabling native WS_THICKFRAME, keeping the caption hidden,
and never exposing HWND or OS memory access to JS.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))
from dueltrace_native_resize import (
    enable_native_edge_resize,_native_handle,
    GWL_STYLE,WS_CAPTION,WS_THICKFRAME,FRAME_FLAGS,
)


class ApiFunction:
    def __init__(self,callback):
        self.callback=callback
        self.argtypes=None
        self.restype=None
        self.calls=[]
    def __call__(self,*args):
        self.calls.append(args)
        return self.callback(*args)


class WindowsApi:
    def __init__(self,style=0x80000000,allow_pos=True):
        self.style=style
        self.allow_pos=allow_pos
        self.GetWindowLongPtrW=ApiFunction(self._get)
        self.SetWindowLongPtrW=ApiFunction(self._set)
        self.SetWindowPos=ApiFunction(lambda *_:1 if self.allow_pos else 0)

    def _get(self,hwnd,index):
        if index!=GWL_STYLE:raise AssertionError("not the window style")
        return self.style

    def _set(self,hwnd,index,style):
        old=self.style
        self.style=style
        return old


class NativeResizeTests(unittest.TestCase):
    def win(self,handle=12345):
        return SimpleNamespace(native=SimpleNamespace(Handle=handle))

    def test_frameless_restores_edge_and_corner_resize(self):
        api=WindowsApi()
        self.assertTrue(enable_native_edge_resize(self.win(),user32=api))
        self.assertTrue(api.style & WS_THICKFRAME)
        self.assertFalse(api.style & WS_CAPTION)
        self.assertEqual(api.GetWindowLongPtrW.calls[0],(12345,GWL_STYLE))
        self.assertEqual(api.SetWindowPos.calls[0][-1],FRAME_FLAGS)

    def test_already_sizable_is_idempotent(self):
        api=WindowsApi(style=0x80000000|WS_THICKFRAME)
        self.assertTrue(enable_native_edge_resize(self.win(),user32=api))
        self.assertEqual(api.SetWindowLongPtrW.calls,[])
        self.assertEqual(api.SetWindowPos.calls,[])

    def test_rejects_wrong_decorated_window_or_missing_handle(self):
        api=WindowsApi(style=0x80000000|WS_CAPTION)
        self.assertFalse(enable_native_edge_resize(self.win(),user32=api))
        self.assertEqual(api.SetWindowLongPtrW.calls,[])
        self.assertFalse(enable_native_edge_resize(
            SimpleNamespace(native=None),user32=api))
        self.assertFalse(enable_native_edge_resize(self.win(0),user32=api))

    def test_failed_frame_refresh_reverts_style(self):
        api=WindowsApi(allow_pos=False)
        self.assertFalse(enable_native_edge_resize(self.win(),user32=api))
        self.assertEqual(api.style,0x80000000)
        self.assertEqual(len(api.SetWindowLongPtrW.calls),2)

    def test_pywebview_form_handle_can_be_dotnet_intptr(self):
        handle=SimpleNamespace(ToInt64=lambda:6543)
        self.assertEqual(_native_handle(self.win(handle)),6543)

    def test_no_custom_window_proc_or_privileged_js_resizing(self):
        native=(ROOT/"scanner/dueltrace_native_resize.py").read_text(encoding="utf-8")
        desktop=(ROOT/"scanner/dueltrace_web_desktop.py").read_text(encoding="utf-8")
        shell=(ROOT/"web/components/shell/app-shell.tsx").read_text(encoding="utf-8")
        api=(ROOT/"scanner/dueltrace_web_security.py").read_text(encoding="utf-8")
        self.assertIn("window.events.shown+=restore_resize_border",desktop)
        self.assertIn("enable_native_edge_resize(window)",desktop)
        self.assertIn("frameless=True,easy_drag=False,resizable=True",desktop)
        self.assertIn("dueltrace-main",shell)
        self.assertNotIn("SetWindowLongPtrW",api)
        self.assertNotIn("window_begin_resize",api)
        for unsafe in ("WriteProcessMemory","SetWindowsHookEx","SetWindowLongPtrW(hwnd,GWL_WNDPROC"):
            self.assertNotIn(unsafe,native)


if __name__=="__main__":
    unittest.main()
