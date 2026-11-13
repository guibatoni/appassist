"""Launch a user-installed PCSX-Redux with the active DUELTRACE ISO only.

The launcher deliberately DOES NOT start its web server automatically. Redux's
HTTP server may bind all network interfaces and exposes write/mutation APIs.
The user must enable the web server explicitly, after securing the firewall.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from dueltrace_pcsx_redux import is_redux_process_name


def command_for_redux(executable: str | Path, image: str | Path) -> tuple[list[str],Path]:
    exe=Path(executable).expanduser().resolve(strict=True)
    rom=Path(image).expanduser().resolve(strict=True)
    if not exe.is_file() or exe.suffix.lower()!=".exe" or not is_redux_process_name(exe.name):
        raise ValueError("Selecione pcsx-redux.exe instalado no Windows.")
    if not rom.is_file() or rom.suffix.lower() not in (".iso",".bin"):
        raise ValueError("Selecione imagem ISO/BIN validada pelo DUELTRACE.")
    if rom.stat().st_size<100_000:
        raise ValueError("Imagem PS1 muito pequena.")
    # -iso and -run are documented cross-build flags; no custom commands.
    return [str(exe),"-iso",str(rom),"-run"],exe.parent


def launch_redux(catalog, executable: str | Path, sha256: str, *,
                 popen=subprocess.Popen, platform: str | None=None):
    if platform is None:
        platform=sys.platform
    if platform!="win32":
        raise OSError("PCSX-Redux externo só pode ser iniciado no DUELTRACE Windows.")
    active=catalog.current() or {}
    if active.get("sha256")!=sha256:
        raise PermissionError("Ative o mod antes de iniciar o PCSX-Redux.")
    entry=next((item for item in catalog.list() if item.get("sha256")==sha256),None)
    if not entry or catalog.profile_for(entry) is None:
        raise ValueError("Perfil do mod não está disponível.")
    source=Path(entry.get("source_path",""))
    if not source.is_file():
        raise FileNotFoundError("ISO/BIN não encontrado.")
    stat=source.stat()
    if stat.st_size!=entry.get("size") or stat.st_mtime_ns!=entry.get("mtime_ns"):
        raise ValueError("ISO/BIN modificado desde a análise; reimporte o arquivo.")
    argv,cwd=command_for_redux(executable,source)
    return popen(argv,cwd=str(cwd),shell=False)
