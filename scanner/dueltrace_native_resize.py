"""Restore native Win32 edge resize on pywebview 6.x frameless WinForms.

pywebview's WinForms backend uses FormBorderStyle.None for frameless windows,
which also strips the Win32 sizing frame even when resizable=True. Re-enable
*only* WS_THICKFRAME; do not add a caption or replace WndProc. Windows then
owns edge/corner hit testing, live resizing, and minimum-size enforcement.

This is UI-only, does not expose HWND or system calls to the web JS bridge.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

GWL_STYLE=-16
WS_THICKFRAME=0x00040000
WS_CAPTION=0x00C00000
SWP_NOSIZE=0x0001
SWP_NOMOVE=0x0002
SWP_NOZORDER=0x0004
SWP_NOACTIVATE=0x0010
SWP_FRAMECHANGED=0x0020
FRAME_FLAGS=(SWP_NOSIZE|SWP_NOMOVE|SWP_NOZORDER|
             SWP_NOACTIVATE|SWP_FRAMECHANGED)


def _native_handle(window) -> int | None:
    """Read the pywebview WinForms Handle, not a guessed process HWND."""
    native=getattr(window,"native",None)
    handle=getattr(native,"Handle",None)
    if handle is None:
        return None
    try:
        value=int(handle.ToInt64() if hasattr(handle,"ToInt64") else handle)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if 0<value<2**64 else None


def enable_native_edge_resize(window, *, user32=None) -> bool:
    """Opt in native edge/corner resizing for one trusted main window.

    Returns False if the form/native style was not available. Never changes
    the caption bit, the minimized/maximized state, or the page scale.
    """
    if sys.platform!="win32" and user32 is None:
        return False
    hwnd=_native_handle(window)
    if hwnd is None:
        return False

    dll=user32 if user32 is not None else ctypes.windll.user32
    getter=getattr(dll,"GetWindowLongPtrW",None)
    setter=getattr(dll,"SetWindowLongPtrW",None)
    # Win32 32-bit exports the macro aliases as Get/SetWindowLongW.
    if getter is None or setter is None:
        getter=getattr(dll,"GetWindowLongW",None)
        setter=getattr(dll,"SetWindowLongW",None)
    setpos=getattr(dll,"SetWindowPos",None)
    if getter is None or setter is None or setpos is None:
        return False
    getter.argtypes=[wintypes.HWND,ctypes.c_int]
    getter.restype=ctypes.c_ssize_t
    setter.argtypes=[wintypes.HWND,ctypes.c_int,ctypes.c_ssize_t]
    setter.restype=ctypes.c_ssize_t
    setpos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,
                     ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
    setpos.restype=wintypes.BOOL
    old_style=int(getter(hwnd,GWL_STYLE))
    if old_style==0:
        return False
    # Frameless must stay captionless; refuse to mutate an unexpected
    # decorated form or to remove any security-related window styles.
    if old_style & WS_CAPTION:
        return False
    if old_style & WS_THICKFRAME:
        return True

    new_style=old_style|WS_THICKFRAME
    setter(hwnd,GWL_STYLE,new_style)
    if not bool(setpos(hwnd,0,0,0,0,0,FRAME_FLAGS)):
        # Best effort revert to the original style on failure.
        setter(hwnd,GWL_STYLE,old_style)
        setpos(hwnd,0,0,0,0,0,FRAME_FLAGS)
        return False
    return bool(int(getter(hwnd,GWL_STYLE)) & WS_THICKFRAME)
