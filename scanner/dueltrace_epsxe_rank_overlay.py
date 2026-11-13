"""Local Windows ePSXe RANK overlay: passive, click-through, no game injection.

This is not an ePSXe plugin. Tk only draws a transparent native window.
Every score comes from DUELTRACE's already-running validated RANK cache.
Nothing is captured or sent to a network. All Tk calls stay on one thread.
"""
from __future__ import annotations

import ctypes
import re
import sys
import threading
from pathlib import Path

from dueltrace_preferences import _GLOBAL_SETTINGS_LOCK, _atomic_json, _read_json

SETTINGS_KEY = "epsxe_rank_overlay"
TRANSPARENT = "#ff00fe"
POSITIONS = ("top-center-right", "top-left", "top-center", "top-right")
DEFAULT = {"enabled": False, "position": "top-center-right", "scale": 100, "opacity": 95}
RANK_LABEL = re.compile(r"^(?:[SABCD]-(?:POW|TEC)|Z-POW)$")


def normalized_settings(payload):
    payload = payload if isinstance(payload, dict) else {}
    return {
        "enabled": payload.get("enabled") is True,
        "position": (payload["position"] if payload.get("position") in POSITIONS
                     else DEFAULT["position"]),
        "scale": (payload["scale"] if type(payload.get("scale")) is int
                  and 70 <= payload["scale"] <= 160 else DEFAULT["scale"]),
        "opacity": (payload["opacity"] if type(payload.get("opacity")) is int
                    and 55 <= payload["opacity"] <= 100 else DEFAULT["opacity"]),
    }


def read_overlay_settings(path):
    return normalized_settings(_read_json(Path(path)).get(SETTINGS_KEY))


def save_overlay_settings(path, enabled, position, scale, opacity):
    """Atomically update only this option; keep ROM paths and window geometry."""
    if type(enabled) is not bool:
        raise ValueError("Ativação do overlay inválida.")
    if type(position) is not str or position not in POSITIONS:
        raise ValueError("Posição do overlay inválida.")
    if type(scale) is not int or not 70 <= scale <= 160:
        raise ValueError("Escala do overlay inválida.")
    if type(opacity) is not int or not 55 <= opacity <= 100:
        raise ValueError("Opacidade do overlay inválida.")
    config = {"enabled": enabled, "position": position,
              "scale": scale, "opacity": opacity}
    with _GLOBAL_SETTINGS_LOCK:
        existing = _read_json(Path(path))
        existing[SETTINGS_KEY] = config
        _atomic_json(Path(path), existing)
    return dict(config)


def rank_overlay_text(rank):
    """Return only truthful duel states. Never turn unvalidated RAM into a rank."""
    if not isinstance(rank, dict):
        return None
    if (rank.get("ready") is True and rank.get("state") == "provisional"
            and type(rank.get("score")) is int
            and -1000 <= rank["score"] <= 1000
            and type(rank.get("category")) is str
            and RANK_LABEL.fullmatch(rank["category"])):
        return "RANK: " + str(rank["score"]), rank["category"], "PREVISÃO"
    # An actual candidate LP is required before stating a duel is detected.
    if (rank.get("ready") is False
            and rank.get("state") in ("auto_calibrating", "needs_lp_confirmation",
                                      "needs_ram_validation")
            and type(rank.get("candidateLp")) is int
            and 0 < rank["candidateLp"] <= 32766):
        return "RANK: —", "ANALISANDO", "DUelo detectado".upper()
    return None


def overlay_geometry(game, position, scale):
    """Place a compact label inside the ePSXe CLIENT area (not title bar).

    game: (left, top, width, height) in Windows screen pixels.
    """
    if (not isinstance(game, (tuple, list)) or len(game) != 4
            or any(type(v) is not int for v in game)):
        return None
    left, top, client_w, client_h = game
    if client_w < 320 or client_h < 180:
        return None
    width = max(110, round(215 * scale / 100))
    height = max(50, round(92 * scale / 100))
    width = min(client_w - 12, width)
    height = min(client_h - 10, height)
    if position == "top-left":
        x = left + 15
    elif position == "top-center":
        x = left + (client_w - width) // 2
    elif position == "top-right":
        x = left + client_w - width - 15
    else:
        # Reference: to the right of the centre, before the game's LP HUD.
        x = left + round(client_w * 0.68) - width // 2
    x = min(max(x, left + 5), left + client_w - width - 5)
    y = top + max(5, round(client_h * 0.01))
    return x, y, width, height


def foreground_epsxe_client():
    """Only one active, real ePSXe process window is eligible.

    When the emulator is minimized, another app has focus, or multiple ePSXe
    windows compete, the overlay hides instead of covering unrelated apps.
    """
    if sys.platform != "win32":
        return None
    from ctypes import wintypes
    from dueltrace_live_hand import discover_epsxe_pids

    try:
        pids = set(discover_epsxe_pids())
    except (OSError, RuntimeError, ValueError):
        return None
    if not pids:
        return None

    user32 = ctypes.windll.user32
    # ctypes defaults to 32-bit int returns, which can truncate HWND on x64.
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [
        wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
    foreground = user32.GetForegroundWindow()
    if not foreground:
        return None
    foreground_pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(foreground, ctypes.byref(foreground_pid))
    if foreground_pid.value not in pids:
        return None

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
    found = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)

    @callback_type
    def visitor(hwnd, _context):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return 1
        if user32.GetWindow(hwnd, 4):  # GW_OWNER: no dialogs/plugin windows
            return 1
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in pids or pid.value != foreground_pid.value:
            return 1
        length = user32.GetWindowTextLengthW(hwnd)
        if not 4 <= length <= 255:
            return 1
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        if "epsxe" not in title.value.casefold():
            return 1
        rect = RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return 1
        w, h = rect.right - rect.left, rect.bottom - rect.top
        if w < 320 or h < 180:
            return 1
        origin = POINT(0, 0)
        if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
            return 1
        found.append((int(origin.x), int(origin.y), int(w), int(h)))
        return 1

    try:
        user32.EnumWindows(visitor, 0)
    except (OSError, RuntimeError, ValueError):
        return None
    return found[0] if len(found) == 1 else None


class EpsxeRankOverlay:
    """Owns a single Tk window on a dedicated thread; never mutates ePSXe."""
    def __init__(self, bridge, settings_path, *, locator=foreground_epsxe_client):
        self.bridge = bridge
        self.settings_path = Path(settings_path)
        self.locator = locator
        self._lock = threading.RLock()
        self._settings = read_overlay_settings(settings_path)
        self._stop = threading.Event()
        self._thread = None
        self._visible = False
        self._error = None

    def configure(self, settings):
        with self._lock:
            self._settings = normalized_settings(settings)
        return self.status()

    def status(self):
        with self._lock:
            return {**self._settings,
                    "supported": sys.platform == "win32",
                    "running": bool(self._thread and self._thread.is_alive()),
                    "visible": self._visible,
                    "error": self._error}

    def start(self):
        if sys.platform != "win32":
            return False
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True,
                                            name="dueltrace-epsxe-rank-overlay")
            self._thread.start()
        return True

    def stop(self):
        self._stop.set()
        worker = self._thread
        if worker and worker.is_alive() and threading.current_thread() is not worker:
            worker.join(timeout=3)
        with self._lock:
            self._visible = False

    def _run(self):
        try:
            import tkinter as tk
            root = tk.Tk(className="DUELTRACE_Rank_Overlay")
            root.withdraw()
            root.overrideredirect(True)
            root.configure(bg=TRANSPARENT)
            root.wm_attributes("-transparentcolor", TRANSPARENT)
            root.wm_attributes("-topmost", True)
            canvas = tk.Canvas(root, bg=TRANSPARENT, highlightthickness=0,
                               bd=0, relief="flat")
            canvas.pack(fill="both", expand=True)
            root.update_idletasks()

            # Tk transparency makes background pixels invisible; these Win32
            # flags also pass all mouse clicks straight through to the game.
            from ctypes import wintypes
            win32 = ctypes.windll.user32
            win32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
            win32.GetAncestor.restype = wintypes.HWND
            win32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
            win32.SetWindowLongW.argtypes = [
                wintypes.HWND, ctypes.c_int, ctypes.c_long]
            win32.SetWindowPos.argtypes = [
                wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            win32.SetWindowPos.restype = wintypes.BOOL
            hwnd = win32.GetAncestor(root.winfo_id(), 2) or int(root.winfo_id())
            def clickthrough():
                exstyle = win32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
                win32.SetWindowLongW(
                    hwnd, -20,
                    exstyle | 0x80000 | 0x20 | 0x80 | 0x08000000)
                # WS_EX_LAYERED | TRANSPARENT | TOOLWINDOW | NOACTIVATE
            clickthrough()
            root.update_idletasks()
            shown = [False]
            last_draw = [None]

            def tick():
                if self._stop.is_set():
                    root.destroy()
                    return
                with self._lock:
                    config = dict(self._settings)
                target = None
                if config["enabled"]:
                    monitor = getattr(self.bridge, "_background_live", None)
                    if monitor is not None and monitor.running:
                        try:
                            rank = self.bridge.get_rank_auto()  # cache ONLY
                            text = rank_overlay_text(rank)
                            if text is not None:
                                game = self.locator()
                                if game:
                                    region = overlay_geometry(game, config["position"],
                                                               config["scale"])
                                    if region is not None:
                                        target = (region, text)
                        except (OSError, ValueError, RuntimeError, AttributeError):
                            target = None
                if target is None:
                    if shown[0]:
                        root.withdraw()
                        shown[0] = False
                    last_draw[0] = None
                    with self._lock:
                        self._visible = False
                else:
                    (x, y, w, h), lines = target
                    key = (w, h, lines, config["opacity"], config["scale"])
                    if key != last_draw[0]:
                        canvas.config(width=w, height=h)
                        canvas.delete("all")
                        scale = config["scale"] / 100
                        main_font = ("Segoe UI", max(12, round(22 * scale)), "bold")
                        sub_font = ("Segoe UI", max(12, round(19 * scale)), "bold")
                        note_font = ("Segoe UI", max(8, round(9 * scale)), "bold")
                        for label, yy, font, color in (
                            (lines[0], round(h*.30), main_font, "#ffffff"),
                            (lines[1], round(h*.65), sub_font, "#ffffff"),
                            (lines[2], round(h*.92), note_font, "#dbeafe"),
                        ):
                            canvas.create_text(w//2+1, yy+2, text=label,
                                               font=font, fill="#000000")
                            canvas.create_text(w//2, yy, text=label,
                                               font=font, fill=color)
                        root.wm_attributes("-alpha", config["opacity"]/100)
                        last_draw[0] = key
                    # Reposition if the user moves/resizes the emulator.
                    root.geometry(f"{w}x{h}+{x}+{y}" if x>=0 and y>=0 else
                                  f"{w}x{h}{x:+d}{y:+d}")
                    if not shown[0]:
                        root.deiconify()
                        # Tk may reapply native extended styles when a
                        # withdrawn window is shown; enforce pass-through.
                        clickthrough()
                        shown[0] = True
                    # Never activate/focus the overlay or intercept input.
                    win32.SetWindowPos(hwnd, -1, x, y, w, h,
                                       0x0010 | 0x0040)  # NOACTIVATE | SHOWWINDOW
                    with self._lock:
                        self._visible = True
                root.after(300, tick)

            root.after(100, tick)
            root.mainloop()
        except Exception as exc:
            with self._lock:
                self._error = f"Overlay nativo indisponível: {type(exc).__name__}"
                self._visible = False
        finally:
            with self._lock:
                self._visible = False
