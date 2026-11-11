"""Safe, resolution-aware Windows sizing for DUELTRACE pywebview windows.

The Next.js UI rearranges contents using CSS. These helpers make sure Windows
can actually create/resize the native window on portrait, 4:3, 16:10, 16:9,
21:9, and other monitors without the old 1100x700 hard minimum.

No persistence, network requests, DPI manipulation or display-mode changes.
"""
from __future__ import annotations

import ctypes
import sys


def window_geometry(work_width: int, work_height: int) -> dict:
    """Choose the initial size from the available desktop work area.

    Returns logical dimensions measured in the same units as GetSystemMetrics.
    High DPI remains managed by Windows/pywebview; this never applies zoom.
    """
    if (type(work_width) is not int or type(work_height) is not int
            or work_width <= 0 or work_height <= 0):
        raise ValueError("Dimensões de tela inválidas.")
    ratio=work_width/work_height
    portrait=ratio<0.86
    ultrawide=ratio>=2.0

    # Small-screen proportions preserve orientation instead of imposing the
    # 1450x870 desktop window onto a narrow portrait display.
    width_cap=820 if portrait else (2000 if ultrawide else 1500)
    height_cap=1450 if portrait else 900
    width=max(1,min(int(work_width*0.95),width_cap))
    height=max(1,min(int(work_height*0.92),height_cap))

    return {
        "width":width,
        "height":height,
        "min_width":min(340,width),
        "min_height":min(460,height),
    }


def tool_geometry(work_width: int, work_height: int,
                  desired_width: int, desired_height: int,
                  *, min_width: int, min_height: int) -> dict:
    """Clamp small independent RANK/Fusions windows to the active screen."""
    for value in (work_width,work_height,desired_width,desired_height,
                  min_width,min_height):
        if type(value) is not int or value<=0:
            raise ValueError("Dimensões de pop-up inválidas.")
    width=min(desired_width,max(1,int(work_width*0.95)))
    height=min(desired_height,max(1,int(work_height*0.92)))
    return {
        "width":width,"height":height,
        "min_size":(min(min_width,width),min(min_height,height)),
    }


def windows_work_area() -> tuple[int,int]:
    """Use the work area excluding the taskbar, not a hard-coded resolution."""
    if sys.platform!="win32":
        raise OSError("Área de trabalho disponível apenas no Windows.")
    from ctypes import wintypes

    class RECT(ctypes.Structure):
        _fields_=[
            ("left",wintypes.LONG),("top",wintypes.LONG),
            ("right",wintypes.LONG),("bottom",wintypes.LONG),
        ]

    user32=ctypes.windll.user32
    user32.GetSystemMetrics.argtypes=[ctypes.c_int]
    user32.GetSystemMetrics.restype=ctypes.c_int
    width=max(1,int(user32.GetSystemMetrics(0)))
    height=max(1,int(user32.GetSystemMetrics(1)))
    user32.SystemParametersInfoW.argtypes=[
        wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT,
    ]
    user32.SystemParametersInfoW.restype=wintypes.BOOL
    rect=RECT()
    if user32.SystemParametersInfoW(0x30,0,ctypes.byref(rect),0):
        work_width=int(rect.right-rect.left)
        work_height=int(rect.bottom-rect.top)
        if work_width>0 and work_height>0:
            return work_width,work_height
    return width,height
