"""Persistent UI preferences and safe native Windows placement for DUELTRACE.

The app's own settings JSON stays in the existing ModCatalog home. Only
whitelisted values are stored; emulator paths and previously saved options
remain intact. Geometry writes are atomic and coalesced during drag/resize.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from uuid import uuid4

LANGUAGES=("pt-BR","en","es","ja","zh-CN","it")
DEFAULT_LANGUAGE="pt-BR"
MAX_SETTINGS_BYTES=1_000_000
_GLOBAL_SETTINGS_LOCK=threading.RLock()


def _read_json(path):
    path=Path(path)
    try:
        if not path.is_file() or path.stat().st_size>MAX_SETTINGS_BYTES:
            return {}
        data=json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError,TypeError):
        return {}


def _atomic_json(path,data):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+"."+uuid4().hex+".tmp")
    try:
        with tmp.open("x",encoding="utf-8") as fh:
            json.dump(data,fh,ensure_ascii=False,indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)


def public_settings(path):
    state=_read_json(path)
    lang=state.get("ui_language")
    return {"language":lang if lang in LANGUAGES else DEFAULT_LANGUAGE,
            "languages":list(LANGUAGES),
            "windowRemembered":isinstance(state.get("window_geometry"),dict)}


def save_language(path,language):
    if type(language) is not str or language not in LANGUAGES:
        raise ValueError("Idioma não suportado.")
    with _GLOBAL_SETTINGS_LOCK:
        values=_read_json(path)
        values["ui_language"]=language
        _atomic_json(path,values)
    return {"language":language}


def clamp_geometry(geometry,work_width,work_height,default):
    """Restore a safe visible normal window, never an offscreen/broken size."""
    if not isinstance(geometry,dict):
        return dict(default)
    if any(type(x) is not int or x<=0 for x in (work_width,work_height)):
        return dict(default)
    w=geometry.get("width")
    h=geometry.get("height")
    if type(w) is not int or type(h) is not int:
        return dict(default)
    width=min(max(w,default["min_width"]),work_width)
    height=min(max(h,default["min_height"]),work_height)
    out={**default,"width":width,"height":height}
    x=geometry.get("x")
    y=geometry.get("y")
    if type(x) is int and type(y) is int:
        # A monitor may have been removed between sessions. Keep the window
        # visible and recover the last size on the surviving main monitor.
        out["x"]=min(max(x,0),max(0,work_width-width))
        out["y"]=min(max(y,0),max(0,work_height-height))
    out["maximized"]=geometry.get("maximized") is True
    return out


class WindowPreferenceStore:
    def __init__(self,path,work_width,work_height,default):
        self.path=Path(path)
        self.work_width=work_width
        self.work_height=work_height
        self.default=dict(default)
        self.lock=threading.RLock()
        self.geometry=clamp_geometry(_read_json(path).get("window_geometry"),
                                     work_width,work_height,default)
        self.maximized=self.geometry.get("maximized") is True
        self._timer=None
        self._dirty=False
        self._closed=False

    def starting_geometry(self):
        with self.lock:
            return dict(self.geometry)

    def _queue(self):
        self._dirty=True
        if self._timer is None and not self._closed:
            self._timer=threading.Timer(.75,self.flush)
            self._timer.daemon=True
            self._timer.start()

    def normal_resize(self,width,height):
        with self.lock:
            if self._closed or self.maximized:
                return
            if (type(width) is not int or type(height) is not int
                    or not 1<=width<=self.work_width
                    or not 1<=height<=self.work_height):
                return
            self.geometry["width"]=max(self.default["min_width"],width)
            self.geometry["height"]=max(self.default["min_height"],height)
            self._queue()

    def normal_move(self,x,y):
        with self.lock:
            if self._closed or self.maximized:
                return
            if type(x) is not int or type(y) is not int:
                return
            w=self.geometry["width"]
            h=self.geometry["height"]
            self.geometry["x"]=min(max(0,x),max(0,self.work_width-w))
            self.geometry["y"]=min(max(0,y),max(0,self.work_height-h))
            self._queue()

    def set_maximized(self,state):
        if type(state) is not bool:
            return
        with self.lock:
            if self._closed:
                return
            self.maximized=state
            self.geometry["maximized"]=state
            self._queue()

    def flush(self):
        with self.lock:
            self._timer=None
            if not self._dirty:
                return
            with _GLOBAL_SETTINGS_LOCK:
                values=_read_json(self.path)
                values["window_geometry"]=dict(self.geometry)
                _atomic_json(self.path,values)
            self._dirty=False

    def close(self):
        with self.lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer=None
            self.flush()
            self._closed=True
