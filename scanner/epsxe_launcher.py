"""Inicialização opcional do ePSXe para a ISO do perfil ativo.

Nunca baixa emulador, BIOS ou ROM; nunca usa shell=True. O usuário informa o
executável instalado e seleciona o perfil antes de jogar. Não identifica
telemetria de RAM ou prova que o jogo inicializou sem erro.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def command_for_epsxe(executable: str | Path, image: str | Path) -> tuple[list[str], Path]:
    """ePSXe moderno aceita -nogui -loadiso, com o caminho como 1 argumento."""
    exe = Path(executable).expanduser().resolve(strict=True)
    rom = Path(image).expanduser().resolve(strict=True)
    if not exe.is_file() or exe.suffix.lower() != ".exe" or "epsxe" not in exe.stem.lower():
        raise ValueError("Selecione o arquivo ePSXe.exe instalado no Windows.")
    if not rom.is_file() or rom.suffix.lower() not in {".iso",".bin"}:
        raise ValueError("Selecione uma imagem ISO/BIN já analisada.")
    if rom.stat().st_size < 100_000:
        raise ValueError("Imagem muito pequena para iniciar como jogo PS1.")
    return [str(exe), "-nogui", "-loadiso", str(rom)], exe.parent


def launch_epsxe(catalog, executable: str | Path, sha256: str, *,
                 popen=subprocess.Popen, platform: str | None = None):
    """Somente a imagem do perfil ativo pode ser executada."""
    if platform is None:
        platform=sys.platform
    if platform != "win32":
        raise OSError("A integração automática com ePSXe é exclusiva do Windows.")
    active=catalog.current() or {}
    if active.get("sha256") != sha256:
        raise PermissionError("Ative o mod selecionado antes de iniciar o ePSXe.")
    entry=next((x for x in catalog.list() if x.get("sha256")==sha256),None)
    if not entry or catalog.profile_for(entry) is None:
        raise ValueError("Perfil de mod inválido.")
    source=Path(entry.get("source_path",""))
    if not source.is_file():
        raise FileNotFoundError("Arquivo ISO/BIN não encontrado no caminho original.")
    stat=source.stat()
    if stat.st_size != entry.get("size") or stat.st_mtime_ns != entry.get("mtime_ns"):
        raise ValueError("A imagem foi modificada depois da análise; reanalise antes de jogar.")
    argv, cwd=command_for_epsxe(executable, source)
    process=popen(argv,cwd=str(cwd),shell=False)
    return process
