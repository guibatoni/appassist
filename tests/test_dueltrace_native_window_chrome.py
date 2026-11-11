"""Regressões da janela Windows frameless e dos controles autenticados.

Nenhuma janela real, navegador, ROM ou ePSXe é necessária para estes testes.
O GitHub Actions Windows ainda compila o executável com pywebview 6.2.1.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_web_security import ProtectedDesktopApi


class NativeWindowControlsTests(unittest.TestCase):
    def setUp(self):
        self.token="s"*64
        self.api=ProtectedDesktopApi(Mock(),self.token)
        self.window=Mock()
        self.api._native_window=self.window

    def test_only_local_capability_may_control_the_window(self):
        for command in ("state","minimize","toggle_maximize","close"):
            with self.subTest(command=command):
                with self.assertRaises(PermissionError):
                    self.api.window_control("wrong token",command)
        self.window.minimize.assert_not_called()
        self.window.maximize.assert_not_called()
        self.window.destroy.assert_not_called()

    def test_action_allowlist_is_strict(self):
        for command in ("move","resize","eval","open_url","reload","quit","",None,1,{}):
            with self.subTest(command=command):
                with self.assertRaises(ValueError):
                    self.api.window_control(self.token,command)
        self.window.minimize.assert_not_called()
        self.window.destroy.assert_not_called()

    def test_state_minimize_maximize_and_restore(self):
        self.assertEqual(self.api.window_control(self.token,"state"),{"maximized":False})
        self.assertEqual(self.api.window_control(self.token,"minimize"),{"maximized":False})
        self.window.minimize.assert_called_once_with()
        self.assertEqual(self.api.window_control(self.token,"toggle_maximize"),{"maximized":True})
        self.window.maximize.assert_called_once_with()
        self.assertEqual(self.api.window_control(self.token,"toggle_maximize"),{"maximized":False})
        self.window.restore.assert_called_once_with()
        self.window.destroy.assert_not_called()

    def test_close_is_delayed_and_scheduled_once(self):
        with patch("dueltrace_web_security.threading.Thread") as thread:
            self.api.window_control(self.token,"close")
            self.api.window_control(self.token,"close")
        thread.assert_called_once()
        self.assertTrue(self.api._native_close_requested)
        self.window.destroy.assert_not_called()

    def test_popouts_are_token_bound_and_kind_allowlisted(self):
        self.api._tool_window_open=Mock(return_value={
            "opened":True,"kind":"calculadora"})
        self.api._tool_window_close=Mock(return_value={
            "closed":True,"kind":"calculadora"})
        for kind in ("calculadora","fusoes"):
            with self.subTest(kind=kind):
                with self.assertRaises(PermissionError):
                    self.api.open_tool_window("invalid",kind)
                with self.assertRaises(PermissionError):
                    self.api.close_tool_window("invalid",kind)
        for invalid in (None,1,{},"config","http://evil.local",""):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    self.api.open_tool_window(self.token,invalid)
                with self.assertRaises(ValueError):
                    self.api.close_tool_window(self.token,invalid)
        self.api._tool_window_open.assert_not_called()
        self.api._tool_window_close.assert_not_called()
        self.api.open_tool_window(self.token,"calculadora")
        self.api.close_tool_window(self.token,"calculadora")
        self.api._tool_window_open.assert_called_once_with("calculadora")
        self.api._tool_window_close.assert_called_once_with("calculadora")

    def test_no_native_window_does_not_perform_any_action(self):
        self.api._native_window=None
        with self.assertRaises(RuntimeError):
            self.api.window_control(self.token,"minimize")

    def test_python_desktop_uses_frameless_and_real_drag_region(self):
        desktop=(ROOT/"scanner/dueltrace_web_desktop.py").read_text(encoding="utf-8")
        self.assertIn("frameless=True,easy_drag=False,resizable=True",desktop)
        self.assertIn("api._native_window=window",desktop)
        self.assertIn("window.events.maximized+=mark_maximized",desktop)
        self.assertIn("window.events.restored+=mark_restored",desktop)
        self.assertIn("window.events.loaded+=secure_loaded",desktop)
        self.assertIn("trusted_window_url(current,url)",desktop)
        self.assertIn("bridge._request_shutdown=close_for_update",desktop)

    def test_topbar_buttons_are_inside_app_but_excluded_from_pointer_drag(self):
        topbar=(ROOT/"web/components/shell/top-bar.tsx").read_text(encoding="utf-8")
        controls=(ROOT/"web/components/shell/window-controls.tsx").read_text(encoding="utf-8")
        self.assertIn("<WindowControls />",topbar)
        self.assertIn("sticky top-0",topbar)
        self.assertIn("onPointerDown={onHeaderPointerDown}",topbar)
        self.assertIn('target.closest(\'button,a,input,textarea,select,[role="button"],[data-no-window-drag]\')',topbar)
        for label in ("Minimizar janela","Maximizar janela","Restaurar janela","Fechar DUELTRACE"):
            with self.subTest(label=label):
                self.assertIn(label,controls)
        self.assertIn('act("minimize")',controls)
        self.assertIn('act("toggle_maximize")',controls)
        self.assertIn('act("close")',controls)
        self.assertIn('window.addEventListener("pywebviewready",sync)',controls)
        self.assertIn("disabled={disabled}",controls)

    def test_entire_titlebar_uses_webview2_mouse_capture_and_native_move(self):
        topbar=(ROOT/"web/components/shell/top-bar.tsx").read_text(encoding="utf-8")
        native=(ROOT/"scanner/dueltrace_web_desktop.py").read_text(encoding="utf-8")
        self.assertIn("onPointerDown={onHeaderPointerDown}",topbar)
        self.assertIn("onPointerMove={onHeaderPointerMove}",topbar)
        self.assertIn("onPointerUp={onHeaderPointerEnd}",topbar)
        self.assertIn("onPointerCancel={onHeaderPointerEnd}",topbar)
        self.assertIn("onLostPointerCapture={onHeaderPointerEnd}",topbar)
        self.assertIn("setPointerCapture(event.pointerId)",topbar)
        self.assertIn("releasePointerCapture(event.pointerId)",topbar)
        self.assertIn("state.api.drag_window_move(state.dragId, x, y)",topbar)
        self.assertIn("state.api.drag_window_end(state.dragId)",topbar)
        self.assertIn("api.drag_window_begin(x, y)",topbar)
        self.assertIn("pointer-events-none relative z-10",topbar)
        self.assertIn('<UpdateChecker />',topbar)
        self.assertIn('<WindowControls />',topbar)
        self.assertIn('frameless=True,easy_drag=False,resizable=True',native)
        self.assertIn('window.events.shown+=restore_resize_border',native)
        self.assertNotIn('webview.settings["DRAG_REGION_DIRECT_TARGET_ONLY"]=True',native)

    def test_native_api_remains_token_bound_no_open_http_endpoint(self):
        types=(ROOT/"web/lib/desktop.ts").read_text(encoding="utf-8")
        secured=(ROOT/"scanner/dueltrace_web_security.py").read_text(encoding="utf-8")
        self.assertIn("window_control: (action) => native.window_control(token,action)",types)
        self.assertIn("drag_window_begin: (x,y) => native.drag_window_begin(token,x,y)",types)
        self.assertIn("drag_window_move: (dragId,x,y) => native.drag_window_move(token,dragId,x,y)",types)
        self.assertIn("drag_window_end: (dragId) => native.drag_window_end(token,dragId)",types)
        self.assertIn("def drag_window_begin(self, credential, screen_x, screen_y):",secured)
        self.assertIn("def drag_window_move(self, credential, drag_id, screen_x, screen_y):",secured)
        self.assertIn("window_control(token:string,action:WindowControlAction)",types)
        self.assertIn("self._authorize(credential)",secured)
        self.assertIn('"toggle_maximize","close"',secured)
        server=(ROOT/"scanner/dueltrace_web_desktop.py").read_text(encoding="utf-8")
        self.assertIn('self.send_error(405,"Apenas conteúdo estático")',server)

    def test_scrollbar_is_inside_app_and_matches_theme(self):
        css=(ROOT/"web/app/globals.css").read_text(encoding="utf-8")
        shell=(ROOT/"web/components/shell/app-shell.tsx").read_text(encoding="utf-8")
        self.assertIn("dueltrace-scroll",shell)
        self.assertIn("min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain",shell)
        self.assertIn("h-dvh min-h-0 flex-col overflow-hidden",shell)
        for selector in (".dueltrace-scroll","*::-webkit-scrollbar","*::-webkit-scrollbar-thumb:hover"):
            self.assertIn(selector,css)
        self.assertIn("scrollbar-width: thin",css)
        self.assertIn("scrollbar-gutter: stable",css)
        self.assertIn("background: transparent",css)
        self.assertIn("background: #38c8ff",css)


if __name__=="__main__":
    unittest.main()
