"""Conservative PS1 save labels, bound to the ISO selected in DUELTRACE.

The PS1 card directory identifies a game/save, not necessarily the FM mod.
Labels distinguish user-confirmed per-ISO links from unrelated game slots.
No content from another mod is ever claimed to be verified by a ROM hash.
"""
from __future__ import annotations

import re
import unicodedata

_ROM_RE = re.compile(r"[0-9a-f]{64}\Z")
_SAVE_TITLE_RE = re.compile(
    r"(?i)yu[ -]?gi[ -]?oh|forbidden|memories|duel|遊戯王"
)
_ALLOWED_MOD_LEN = 84


def safe_mod_name(value):
    if not isinstance(value, str):
        return ""
    value = "".join(" " if unicodedata.category(ch)[0] == "C" else ch
                    for ch in value).strip()
    if value.lower().startswith("mod local — "):
        value = value[12:].strip()
    return " ".join(value.split())[:_ALLOWED_MOD_LEN]


def title_from_ps1_header(block):
    """The SC block title occupies 64 bytes at offsets 0x04..0x43."""
    if not isinstance(block,bytes) or len(block)<68 or block[:2]!=b"SC":
        return None
    raw=block[4:68].split(b"\x00\x00",1)[0].strip(b"\x00\xff ")
    for codec in ("shift_jis","ascii"):
        try:
            text=raw.decode(codec).replace("\x00","").strip()
        except (UnicodeError,ValueError):
            continue
        text=" ".join(text.split())
        if (4 <= len(text) <= 64
                and _SAVE_TITLE_RE.search(text)
                and all(unicodedata.category(ch)[0]!="C" for ch in text)):
            return text[:64]
    return None


def label_saves(saves, links, *, current_sha, memory_path, mod_name):
    """Create per-save descriptions; no inferred mod identity from FM serial.

    A mod is named only after the user has selected/pinned that save for
    that same ROM SHA. Cross-mod links are displayed as ambiguity, not proof.
    """
    if not isinstance(saves,list):
        return []
    if not isinstance(links,dict):
        links={}
    current=links.get(current_sha)
    if not isinstance(current,dict):
        current={}
    current_mod=safe_mod_name(mod_name) or safe_mod_name(current.get("modName"))
    available=[]
    for row in saves:
        if not isinstance(row,dict) or type(row.get("block")) is not int:
            continue
        block=row["block"]
        if not 1<=block<=15:
            continue
        seq=row.get("saveSequence")
        seq_str=str(seq) if type(seq) is int and 0<=seq<=0xFFFFFFFF else "?"
        title=row.get("saveTitle")
        if type(title) is not str or len(title)>64:
            title=None
        title=title or "Save Yu-Gi-Oh! FM"
        matched=[]
        for sha,link in links.items():
            if (not isinstance(sha,str) or not _ROM_RE.fullmatch(sha)
                    or not isinstance(link,dict)
                    or link.get("path") != memory_path
                    or type(link.get("selectedBlock")) is not int
                    or link["selectedBlock"]!=block):
                continue
            if (link.get("selectedSaveName") is not None
                    and link["selectedSaveName"]!=row.get("saveName")):
                continue
            if (type(link.get("selectedDuelistCode")) is int
                    and link["selectedDuelistCode"]!=row.get("duelistCode")):
                continue
            matched.append((sha,safe_mod_name(link.get("modName"))))
        active=any(sha==current_sha for sha,_ in matched)
        other=[name or "outro mod" for sha,name in matched if sha!=current_sha]
        if active:
            # User-selected link; not an assertion that the ISO owns the save.
            mod=current_mod or "mod atual"
            suffix=" · também associado a outro mod" if other else ""
            desc=f"Bloco {block} · {mod} (vinculado){suffix} · seq. {seq_str}"
            association="linked_current_mod" if not other else "shared_between_mods"
            assoc_mod=mod
        elif other:
            mod=other[0]
            suffix=" · vínculos múltiplos" if len(other)>1 else ""
            desc=f"Bloco {block} · {mod} (outro mod){suffix} · seq. {seq_str}"
            association="linked_other_mod"
            assoc_mod=mod
        else:
            desc=f"Bloco {block} · {title} (mod não associado) · seq. {seq_str}"
            association="unassigned"
            assoc_mod=None
        available.append({**row,
                          "displayName":desc[:225],
                          "association":association,
                          "linkedModName":assoc_mod,
                          "saveTitle":title})
    return available
