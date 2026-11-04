"""Atualização opcional da Preview Windows via GitHub Releases (SEM assinatura).

Somente pré-releases oficiais com SHA-256 publicado, versão monotônica e
build-id/commit internos iguais aos metadados da release. Não executa
arquivos do GitHub Actions diretamente nem desativa proteção do Windows.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import stat
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit

from dueltrace_update_checker import CURRENT_VERSION, parse_version
from dueltrace_preview_updates import (
    REPO_API, REPO_WEB, BUILD_INFO_FILE, _get_json, installed_preview_build_id,
)
from dueltrace_signed_install import TrustedRedirect, TRUSTED_HOSTS, UnsafeUpdate

PREVIEW_LIST = REPO_API + "/releases?per_page=30"
ASSET_NAME = "DUELTRACE-WebUI-Windows-Preview.zip"
TAG_PATTERN = re.compile(r"preview-v(\d{1,4}\.\d{1,4}\.\d{1,4})-r(\d{1,15})\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"sha256:([a-f0-9]{64})\Z")
MAX_ARCHIVE = 230 * 1024 * 1024
MAX_EXTRACTED = 1050 * 1024 * 1024
MAX_FILES = 12000


def select_preview_release(release: dict, current_version: str,
                           installed_run_id: int | None = None) -> dict | None:
    if not isinstance(release,dict) or release.get("draft") is not False or release.get("prerelease") is not True:
        raise UnsafeUpdate("A atualização Preview exige pré-release pública oficial.")
    tag=release.get("tag_name")
    match=TAG_PATTERN.fullmatch(tag) if isinstance(tag,str) else None
    if not match:
        raise UnsafeUpdate("Tag Preview inválida.")
    version,run_str=match.groups()
    run_id=int(run_str)
    current=parse_version(current_version)
    new=parse_version(version)
    if current is None or new is None or not 0<run_id<10**15:
        raise UnsafeUpdate("Versão ou build inválidos.")
    if new<current or (new==current and
                       (type(installed_run_id) is not int or run_id<=installed_run_id)):
        return None
    if release.get("html_url") != f"{REPO_WEB}/releases/tag/{tag}":
        raise UnsafeUpdate("Origem da pré-release não é a oficial.")
    sha=release.get("target_commitish")
    if not isinstance(sha,str) or not SHA.fullmatch(sha):
        raise UnsafeUpdate("Commit de origem da release não identificado.")
    assets=release.get("assets")
    if not isinstance(assets,list):
        raise UnsafeUpdate("Release sem arquivos.")
    matches=[a for a in assets if isinstance(a,dict) and a.get("name")==ASSET_NAME]
    if len(matches)!=1:
        raise UnsafeUpdate("Pacote Preview único não encontrado.")
    a=matches[0]
    url=f"{REPO_WEB}/releases/download/{tag}/{ASSET_NAME}"
    digest=a.get("digest")
    parsed=DIGEST.fullmatch(digest) if isinstance(digest,str) else None
    if (a.get("browser_download_url")!=url or not parsed or
            type(a.get("size")) is not int or
            not 0<a["size"]<=MAX_ARCHIVE):
        raise UnsafeUpdate("URL, tamanho ou SHA-256 da Preview inválidos.")
    return {"tag":tag,"version":version,"run_id":run_id,"sha":sha,
            "url":url,"sha256":parsed.group(1),"size":a["size"],
            "page":release["html_url"]}


def fetch_latest_preview_package(*, current_version: str = CURRENT_VERSION,
                                 installed_run_id: int | None = None,
                                 fetcher=None) -> dict | None:
    data=(fetcher or (lambda:_get_json(PREVIEW_LIST,list)))()
    if not isinstance(data,list):
        raise UnsafeUpdate("Lista de pré-releases do GitHub inválida.")
    eligible=[]
    for r in data[:30]:
        if not isinstance(r,dict):
            continue
        tag=r.get("tag_name")
        if not isinstance(tag,str) or not tag.startswith("preview-v"):
            continue
        try:
            candidate=select_preview_release(r,current_version,installed_run_id)
            if candidate:
                eligible.append(candidate)
        except UnsafeUpdate:
            continue
    if not eligible:
        return None
    return max(eligible,key=lambda x:(parse_version(x["version"]),x["run_id"]))


def download_preview_zip(info: dict, destination: Path, *, opener=None) -> Path:
    if destination.exists() or destination.is_symlink():
        raise UnsafeUpdate("Destino de download já existe.")
    req=urllib.request.Request(info["url"],headers={
        "User-Agent":"DUELTRACE-Preview-Update/0.8.5",
        "Accept":"application/octet-stream"})
    transport=opener or urllib.request.build_opener(TrustedRedirect())
    size=0
    digest=hashlib.sha256()
    try:
        with transport.open(req,timeout=25) as response:
            url=urlsplit(response.geturl())
            if url.scheme!="https" or url.hostname not in TRUSTED_HOSTS:
                raise UnsafeUpdate("Redirecionamento para domínio não autorizado.")
            with destination.open("xb") as file:
                while chunk:=response.read(1024*1024):
                    size+=len(chunk)
                    if size>MAX_ARCHIVE or size>info["size"]:
                        raise UnsafeUpdate("Pacote excedeu o tamanho publicado.")
                    digest.update(chunk)
                    file.write(chunk)
        if size!=info["size"] or digest.hexdigest()!=info["sha256"]:
            raise UnsafeUpdate("SHA-256 do download divergente da release.")
        return destination
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def _validate_filename(name: str) -> None:
    if (not name or name.startswith("/") or "\\" in name or ":" in name
            or any(part in ("",".","..") for part in name.rstrip("/").split("/"))):
        raise UnsafeUpdate("Arquivo ZIP contém caminho perigoso.")


def unpack_preview_zip(archive: Path, directory: Path, info: dict) -> Path:
    """Extrai ZIP de forma limitada, sem links, traversal ou nomes duplicados."""
    if directory.exists() or directory.is_symlink():
        raise UnsafeUpdate("Diretório de preparação já existe.")
    directory.mkdir(parents=False)
    try:
        with zipfile.ZipFile(archive) as z:
            members=z.infolist()
            if len(members)>MAX_FILES:
                raise UnsafeUpdate("Pacote contém arquivos demais.")
            seen=set()
            total=0
            for entry in members:
                _validate_filename(entry.filename)
                name=entry.filename.rstrip("/")
                normalized=name.casefold()
                if normalized in seen:
                    raise UnsafeUpdate("Pacote contém arquivos com nomes duplicados.")
                seen.add(normalized)
                mode=(entry.external_attr>>16)&0o170000
                if mode==stat.S_IFLNK:
                    raise UnsafeUpdate("Links simbólicos não são permitidos.")
                if entry.is_dir():
                    continue
                total+=entry.file_size
                if total>MAX_EXTRACTED:
                    raise UnsafeUpdate("Tamanho extraído excede limite.")
                target=directory.joinpath(*name.split("/"))
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(entry) as src, target.open("xb") as dest:
                    while chunk:=src.read(1024*1024):
                        dest.write(chunk)
        exe=directory/"DUELTRACE-WebUI.exe"
        manifest_candidates=[directory/"_internal"/BUILD_INFO_FILE,
                             directory/BUILD_INFO_FILE]
        manifest=next((p for p in manifest_candidates if p.is_file()),None)
        if not exe.is_file() or exe.stat().st_size<1024 or manifest is None:
            raise UnsafeUpdate("Executável ou identidade do build ausente.")
        if manifest.stat().st_size>2048:
            raise UnsafeUpdate("Identidade de build muito grande.")
        data=json.loads(manifest.read_text(encoding="utf-8-sig"))
        if (not isinstance(data,dict) or data.get("schema")!=1
                or data.get("version")!=info["version"]
                or data.get("run_id")!=info["run_id"]
                or data.get("head_sha")!=info["sha"]):
            raise UnsafeUpdate("Conteúdo do pacote não corresponde ao build publicado.")
        return exe
    except BaseException:
        import shutil
        shutil.rmtree(directory,ignore_errors=True)
        raise


def _ps_quote(value: Path) -> str:
    return str(value).replace("'","''")


def _powershell_replace_script(original: Path, staged: Path, backup: Path,
                               old_pid: int) -> str:
    """Troca atômica de pastas depois da saída do processo atual, com rollback."""
    old=_ps_quote(original)
    stage=_ps_quote(staged)
    prev=_ps_quote(backup)
    original_name=original.name.replace("'","''")
    return f"""$ErrorActionPreference='Stop'
$pidOld={old_pid}
$old='{old}'
$stage='{stage}'
$backup='{prev}'
try {{
  Wait-Process -Id $pidOld -Timeout 90 -ErrorAction SilentlyContinue
  if (Get-Process -Id $pidOld -ErrorAction SilentlyContinue) {{ exit 20 }}
  if (!(Test-Path -LiteralPath (Join-Path $stage 'DUELTRACE-WebUI.exe'))) {{ exit 21 }}
  if (Test-Path -LiteralPath $backup) {{
    if (!(Test-Path -LiteralPath (Join-Path $backup 'DUELTRACE-WebUI.exe')) -or
        !(Test-Path -LiteralPath (Join-Path $backup '_internal'))) {{ exit 22 }}
    $allowed=@('DUELTRACE-WebUI.exe','_internal','LEIA-ME-SEGURANCA.txt')
    $unknown=@(Get-ChildItem -LiteralPath $backup -Force | Where-Object {{ $allowed -notcontains $_.Name }})
    if ($unknown.Count -gt 0) {{ exit 26 }}
    Remove-Item -LiteralPath $backup -Recurse -Force
  }}
  Rename-Item -LiteralPath $old -NewName '{backup.name.replace("'","''")}'
  try {{
    Rename-Item -LiteralPath $stage -NewName '{original_name}'
    Start-Process -FilePath (Join-Path $old 'DUELTRACE-WebUI.exe') -WorkingDirectory $old
  }} catch {{
    if ((Test-Path -LiteralPath $old) -and !(Test-Path -LiteralPath $backup)) {{ exit 23 }}
    if (Test-Path -LiteralPath $old) {{ Rename-Item -LiteralPath $old -NewName '{staged.name.replace("'","''")}' }}
    Rename-Item -LiteralPath $backup -NewName '{original_name}'
    exit 24
  }}
}} catch {{ exit 25 }}
"""


def stage_preview_update(*, info: dict, data_home: Path,
                         current_executable: Path | None = None,
                         downloader=None, unpacker=None, launcher=None) -> dict:
    if sys.platform!="win32" and current_executable is None:
        raise UnsafeUpdate("Atualização disponível apenas no Windows.")
    if current_executable is None and not getattr(sys,"frozen",False):
        raise UnsafeUpdate("Atualização automática exige aplicativo Windows empacotado.")
    executable=Path(current_executable or sys.executable).resolve(strict=True)
    if executable.name!="DUELTRACE-WebUI.exe":
        raise UnsafeUpdate("Instalação Windows não reconhecida.")
    home=Path(data_home).resolve()
    original=executable.parent
    if home==original or home.is_relative_to(original):
        raise UnsafeUpdate("A pasta do programa contém dados pessoais. Atualização bloqueada.")
    if not original.is_dir() or original.is_symlink():
        raise UnsafeUpdate("Pasta de instalação inválida.")
    backup=original.parent/("."+original.name+"-backup")
    if backup.is_symlink() or (backup.exists() and (
            not backup.is_dir() or
            not (backup/"DUELTRACE-WebUI.exe").is_file() or
            not (backup/"_internal").is_dir() or
            any(p.name not in ("DUELTRACE-WebUI.exe","_internal",
                               "LEIA-ME-SEGURANCA.txt")
                for p in backup.iterdir()))):
        raise UnsafeUpdate("Backup anterior contém dados inesperados. "
                           "Revise manualmente antes de atualizar.")
    stage=original.parent/("."+original.name+"-staged-"+uuid4().hex[:12])
    archive=home/"preview_updates"/("preview-"+uuid4().hex+".zip")
    archive.parent.mkdir(parents=True,exist_ok=True)
    try:
        (downloader or download_preview_zip)(info,archive)
        (unpacker or unpack_preview_zip)(archive,stage,info)
        script=_powershell_replace_script(original,stage,backup,
                                          __import__("os").getpid())
        if launcher is None:
            encoded=base64.b64encode(script.encode("utf-16le")).decode("ascii")
            subprocess.Popen(
                ["powershell.exe","-NoProfile","-NonInteractive",
                 "-WindowStyle","Hidden","-EncodedCommand",encoded],
                creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0),
                close_fds=True)
        else:
            launcher(script)
        return {"started":True,"status":(
            f"Preview v{info['version']} verificada. O aplicativo será fechado, "
            "substituído e reaberto. Uma cópia anterior será preservada."),
            "version":info["version"]}
    except BaseException:
        import shutil
        if stage.exists():
            shutil.rmtree(stage,ignore_errors=True)
        raise
    finally:
        archive.unlink(missing_ok=True)


def install_preview_release(*, data_home: Path,
                            current_version: str = CURRENT_VERSION,
                            installed_run_id: int | None = None,
                            fetcher=None, **kwargs) -> dict:
    info=fetch_latest_preview_package(
        current_version=current_version,
        installed_run_id=(installed_run_id if installed_run_id is not None
                          else installed_preview_build_id()),fetcher=fetcher)
    if not info:
        return {"started":False,
                "status":"Não há nova Preview pública verificada no GitHub Releases."}
    return stage_preview_update(info=info,data_home=data_home,**kwargs)
