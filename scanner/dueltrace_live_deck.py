"""Read-only active-deck sampling from the already-confirmed ePSXe hand RAM.

No guesswork from a static deck-sized buffer. Only the SAME process and a
PS1 RAM base with a hand anchor confirmed by actual changes are eligible.
The caller additionally must bind this PID to a ROM it launched itself.
"""
from __future__ import annotations

import ctypes
import struct
import sys
import time
from ctypes import wintypes

from dueltrace_epsxe_memory import HAND_OFFSET
from dueltrace_live_hand import (
    read_hand_from_epsxe, _PID_HAND_ADDRESS_CACHE,
    PROCESS_QUERY_INFORMATION, PROCESS_VM_READ,
)

DECK_OFFSET = 0x1D0200
DECK_BYTES = 80


def parse_live_deck(blob):
    if not isinstance(blob,bytes) or len(blob)!=DECK_BYTES:
        return None
    ids=list(struct.unpack("<40H",blob))
    if not all(1 <= x <= 722 for x in ids):
        return None
    return ids


def derive_host_deck_address(confirmed_hand_address):
    if (type(confirmed_hand_address) is not int or
            confirmed_hand_address <= HAND_OFFSET+0x10000):
        return None
    base=confirmed_hand_address-HAND_OFFSET
    if base < 0x10000:
        return None
    return base+DECK_OFFSET


def read_live_deck(preferred_pid=None):
    """Requires a hand anchor with a *real prior change* in the same PID."""
    empty={"ready":False,"deckIds":[],"pid":None,
           "status":"RAM do deck não confirmada."}
    if sys.platform!="win32" or type(preferred_pid) is not int or preferred_pid<=0:
        return empty
    try:
        hand=read_hand_from_epsxe(preferred_pid=preferred_pid)
        if hand.get("ready") is not True or hand.get("pid")!=preferred_pid:
            return {**empty,"status":"Aguardando confirmação da mão na RAM do ePSXe."}
        from dueltrace_live_hand import _PID_HAND_ADDRESS_CACHE
        address=derive_host_deck_address(
            _PID_HAND_ADDRESS_CACHE.get(preferred_pid))
        if address is None:
            return empty
        kernel=ctypes.windll.kernel32
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.ReadProcessMemory.argtypes=[
            wintypes.HANDLE,ctypes.c_void_p,ctypes.c_void_p,
            ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
        kernel.ReadProcessMemory.restype=wintypes.BOOL
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        kernel.CloseHandle.restype=wintypes.BOOL
        handle=kernel.OpenProcess(
            PROCESS_QUERY_INFORMATION|PROCESS_VM_READ,False,preferred_pid)
        if not handle:
            return empty
        try:
            def sample():
                buf=ctypes.create_string_buffer(DECK_BYTES)
                count=ctypes.c_size_t(0)
                ok=kernel.ReadProcessMemory(
                    handle,ctypes.c_void_p(address),buf,DECK_BYTES,ctypes.byref(count))
                return buf.raw if ok and count.value==DECK_BYTES else None
            first=sample()
            time.sleep(0.012)
            second=sample()
            ids=parse_live_deck(first)
            if ids is None or first!=second:
                return empty
            return {"ready":True,"deckIds":ids,"pid":preferred_pid,
                    "status":"Deck em RAM confirmado pela mão em movimento."}
        finally:
            kernel.CloseHandle(handle)
    except (AttributeError,OSError,TypeError,ValueError,OverflowError):
        return empty
