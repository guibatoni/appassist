"""Aviso local e confiável da versão Preview recém-instalada.

As notas pertencem ao próprio build Windows, não ao feed remoto: mesmo
offline, a primeira abertura após uma atualização mostra as novidades.
Somente o usuário pode marcar a versão atual como lida.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from auto_mods import load_json, atomic_json
from dueltrace_patch_notes import summarize_patch_notes
from dueltrace_preview_updates import BUILD_INFO_FILE
from dueltrace_update_checker import CURRENT_VERSION

NOTES_FILE = "DUELTRACE_UPDATE_NOTES.md"
ACK_FILE = "dueltrace_update_notice.json"
MAX_NOTES_BYTES = 24_000
RUN_LIMIT = 10**15


def _installed_identity(bundle: Path) -> tuple[int, str] | None:
    manifest = bundle / BUILD_INFO_FILE
    try:
        if not manifest.is_file() or not 0 < manifest.stat().st_size <= 2048:
            return None
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
        run_id = data.get("run_id")
        version = data.get("version")
        if (data.get("schema") != 1 or type(run_id) is not int
                or not 0 < run_id < RUN_LIMIT
                or version != CURRENT_VERSION
                or not re.fullmatch(r"[0-9a-f]{40}", data.get("head_sha", ""))):
            return None
        return run_id, version
    except (OSError, ValueError, TypeError, UnicodeError):
        return None


def read_installed_update_notice(data_home: Path, *, bundle: Path | None = None) -> dict:
    """Returns on-device release notes and an unread flag for this exact build."""
    directory = Path(bundle or getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    identity = _installed_identity(directory)
    result = {"available": False, "unread": False,
              "version": CURRENT_VERSION, "runId": None, "notes": []}
    if identity is None:
        return result
    run_id, version = identity
    path = directory / NOTES_FILE
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_NOTES_BYTES:
            return result
        body = path.read_text(encoding="utf-8-sig")
        if not body.startswith(f"# DUELTRACE v{version}"):
            return result
        notes = summarize_patch_notes(body)
    except (OSError, UnicodeError, ValueError):
        return result
    if not notes:
        return result
    saved = load_json(Path(data_home) / ACK_FILE, {})
    seen = saved.get("run_id") if isinstance(saved, dict) else None
    unread = not (type(seen) is int and seen == run_id)
    return {"available": True, "unread": unread, "version": version,
            "runId": run_id, "notes": notes}


def acknowledge_installed_update_notice(data_home: Path, run_id: int, *,
                                         bundle: Path | None = None) -> dict:
    """Only acknowledge the currently installed build; never an arbitrary ID."""
    current = read_installed_update_notice(data_home, bundle=bundle)
    if (not current["available"] or type(run_id) is not int
            or run_id != current["runId"]):
        raise ValueError("Identidade da atualização instalada inválida.")
    atomic_json(Path(data_home) / ACK_FILE,
                {"schema": 1, "run_id": run_id, "version": current["version"]})
    return {"acknowledged": True, "runId": run_id}
