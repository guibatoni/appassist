"""Native Windows caption dragging for the DUELTRACE frameless main window.

The WebView2 pointer-move bridge in v51 loses the mouse stream when the OS
window is repositioned. Start the Windows caption move loop instead:
ReleaseCapture() + SendMessageW(WM_NCLBUTTONDOWN, HTCAPTION). This gives the
whole operation to the Windows window manager until the mouse is released.

Only the application's already-attached WinForms Form is eligible. Never
accept an HWND, coordinates or an arbitrary window from browser JavaScript.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from dueltrace_native_resize import _native_handle

WM_NCLBUTTONDOWN = 0x00A1
HTCAPTION = 2
VK_LBUTTON = 0x01


def request_native_caption_drag(window, *, user32=None, action_factory=None) -> bool:
    """Queue a native title-bar drag on the Form's owning GUI thread.

    BeginInvoke is necessary: the pywebview JS bridge runs asynchronously and
    WinForms controls must be accessed on their original STA thread. Scheduling
    returns immediately while the Windows modal move loop handles the gesture.
    Once queued, the callback checks that the left button is STILL pressed.
    """
    if sys.platform != "win32" and user32 is None:
        return False
    form = getattr(window, "native", None)
    if form is None or not callable(getattr(form, "BeginInvoke", None)):
        return False
    dll = user32 if user32 is not None else ctypes.windll.user32
    key_state = getattr(dll, "GetAsyncKeyState", None)
    release_capture = getattr(dll, "ReleaseCapture", None)
    send_message = getattr(dll, "SendMessageW", None)
    if not all(callable(fn) for fn in (key_state, release_capture, send_message)):
        return False

    # Set the real Win32 prototypes. Mocks injected by tests have no effect on
    # the actual process; only the trusted desktop entry point calls this.
    key_state.argtypes = [ctypes.c_int]
    key_state.restype = ctypes.c_short
    release_capture.argtypes = []
    release_capture.restype = wintypes.BOOL
    send_message.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    ]
    send_message.restype = wintypes.LPARAM

    if action_factory is None:
        from System import Action  # pythonnet, imported only in Windows GUI
        action_factory = Action

    def on_winforms_thread():
        # An exception must not escape an asynchronous .NET GUI delegate and
        # crash the host; a failed gesture simply leaves the window in place.
        try:
            if bool(form.IsDisposed) or not bool(form.IsHandleCreated):
                return
            if str(form.WindowState).casefold().endswith("maximized"):
                return
            hwnd = _native_handle(window)
            if hwnd is None or not (int(key_state(VK_LBUTTON)) & 0x8000):
                return
            release_capture()
            send_message(hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0)
        except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
            return

    try:
        form.BeginInvoke(action_factory(on_winforms_thread))
    except (OSError, RuntimeError, TypeError, ValueError, AttributeError):
        return False
    return True
