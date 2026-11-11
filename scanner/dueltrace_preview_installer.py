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
import urllib.error
import zipfile
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit

from dueltrace_update_checker import CURRENT_VERSION, parse_version
from dueltrace_patch_notes import summarize_patch_notes
from dueltrace_preview_updates import (
    BUILD_INFO_FILE, _get_json, installed_preview_build_id,
)
from dueltrace_public_distribution import (
    PUBLIC_UPDATES_API as REPO_API, PUBLIC_UPDATES_WEB as REPO_WEB,
    verified_source_identity,
)
from dueltrace_signed_install import TrustedRedirect, TRUSTED_HOSTS, UnsafeUpdate

PREVIEW_LIST = REPO_API + "/releases?per_page=30"
ASSET_NAME = "DUELTRACE-WebUI-Windows-Preview.zip"
STABLE_ASSET_NAME = "DUELTRACE-WebUI-Windows.zip"
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
    try:
        audited_run,sha=verified_source_identity(release.get("body"),parsed.group(1),run_id)
    except ValueError as exc:
        raise UnsafeUpdate(str(exc)) from exc
    return {"tag":tag,"version":version,"run_id":audited_run,"sha":sha,
            "url":url,"sha256":parsed.group(1),"size":a["size"],
            "page":release["html_url"],
            "patchNotes":summarize_patch_notes(release.get("body"))}


def fetch_latest_preview_package(*, current_version: str = CURRENT_VERSION,
                                 installed_run_id: int | None = None,
                                 fetcher=None) -> dict | None:
    # Public binary distribution, always anonymous. Never prompt customers to
    # authenticate to the private source repository or embed a GitHub token.
    data=fetcher() if fetcher is not None else _get_json(PREVIEW_LIST,list)
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


def select_portable_stable_release(release: dict, current_version: str,
                                   installed_channel: str = "preview") -> dict | None:
    """ZIP estável com SHA-256 oficial: assinatura digital não é exigida."""
    if (not isinstance(release,dict) or release.get("draft") is not False
            or release.get("prerelease") is not False):
        raise UnsafeUpdate("Release estável pública obrigatória.")
    tag=release.get("tag_name")
    installed=parse_version(current_version)
    newer=parse_version(tag)
    if installed is None or newer is None or installed_channel not in ("preview","stable"):
        raise UnsafeUpdate("Versão estável inválida.")
    if newer<installed or (newer==installed and installed_channel=="stable"):
        return None
    if release.get("html_url")!=f"{REPO_WEB}/releases/tag/{tag}":
        raise UnsafeUpdate("Origem estável não autorizada.")
    assets=release.get("assets")
    matches=([a for a in assets if isinstance(a,dict)
              and a.get("name")==STABLE_ASSET_NAME]
             if isinstance(assets,list) else [])
    if len(matches)!=1:
        return None
    item=matches[0]
    digest=item.get("digest")
    digest_match=DIGEST.fullmatch(digest) if isinstance(digest,str) else None
    url=f"{REPO_WEB}/releases/download/{tag}/{STABLE_ASSET_NAME}"
    if (not digest_match or type(item.get("size")) is not int
            or not 0<item["size"]<=MAX_ARCHIVE
            or item.get("browser_download_url")!=url):
        raise UnsafeUpdate("ZIP estável sem SHA-256 ou endereço oficial.")
    try:
        _source_run,sha=verified_source_identity(release.get("body"),digest_match.group(1))
    except ValueError as exc:
        raise UnsafeUpdate(str(exc)) from exc
    return {"tag":tag,"version":".".join(map(str,newer)),
            "run_id":None,"sha":sha,"url":url,
            "sha256":digest_match.group(1),"size":item["size"],
            "page":release["html_url"],"channel":"stable",
            "patchNotes":summarize_patch_notes(release.get("body"))}


def fetch_portable_stable_package(*, current_version: str = CURRENT_VERSION,
                                 installed_channel: str = "preview",
                                 fetcher=None) -> dict | None:
    from dueltrace_update_checker import fetch_stable_release
    release=(fetcher or fetch_stable_release)()
    return select_portable_stable_release(release,current_version,installed_channel)


def install_portable_stable_release(*, data_home: Path,
                                    current_version: str = CURRENT_VERSION,
                                    installed_channel: str = "preview",
                                    fetcher=None, **kwargs) -> dict:
    info=fetch_portable_stable_package(
        current_version=current_version,installed_channel=installed_channel,
        fetcher=fetcher)
    if info is None:
        return {"started":False,
                "status":"Nenhuma versão estável portátil nova com SHA-256 disponível."}
    return stage_preview_update(info=info,data_home=data_home,**kwargs)


def download_preview_zip(info: dict, destination: Path, *, opener=None) -> Path:
    if destination.exists() or destination.is_symlink():
        raise UnsafeUpdate("Destino de download já existe.")
    if info.get("transport") is not None:
        raise UnsafeUpdate("Atualizações para clientes usam apenas download HTTPS público.")
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
        allowed={"DUELTRACE-WebUI.exe","_internal","LEIA-ME-SEGURANCA.txt"}
        if any(child.name not in allowed for child in directory.iterdir()):
            raise UnsafeUpdate("Pacote contém arquivos inesperados fora de _internal.")
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
                or (data.get("run_id")!=info["run_id"] if info["run_id"] is not None
                    else type(data.get("run_id")) is not int or not 0<data["run_id"]<10**15)
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
                               old_pid: int, legacy_backup: Path | None = None) -> str:
    """Substitui componentes dentro da pasta atual e relança o mesmo EXE.

    Usa a pasta de dados local para staging, log e rollback, nunca uma segunda
    pasta de instalação. O processo anterior precisa terminar antes da troca.
    """
    paths = {
        "@@OLD@@": _ps_quote(original),
        "@@STAGE@@": _ps_quote(staged),
        "@@BACKUP@@": _ps_quote(backup),
        "@@LEGACY@@": _ps_quote(legacy_backup) if legacy_backup else "",
        "@@LOG@@": _ps_quote(backup.parent / "ultima-atualizacao.log"),
        "@@PID@@": str(old_pid),
    }
    script = r"""$ErrorActionPreference='Stop'
$old='@@OLD@@'
$stage='@@STAGE@@'
$backup='@@BACKUP@@'
$legacy='@@LEGACY@@'
$log='@@LOG@@'
$pidOld=@@PID@@
$managed=@('DUELTRACE-WebUI.exe','_internal','LEIA-ME-SEGURANCA.txt')
$exe=Join-Path $old 'DUELTRACE-WebUI.exe'
$installed=@()
$moved=@()
$newProcess=$null
$restarted=$false

function Write-UpdateLog([string]$message) {
  try {
    Add-Content -LiteralPath $log -Value ("{0:u} {1}" -f (Get-Date),$message) -Encoding UTF8
  } catch {}
}

function Confirm-ManagedBackup([string]$folder) {
  if (!(Test-Path -LiteralPath $folder -PathType Container)) { return $false }
  if (!(Test-Path -LiteralPath (Join-Path $folder 'DUELTRACE-WebUI.exe') -PathType Leaf)) { return $false }
  if (!(Test-Path -LiteralPath (Join-Path $folder '_internal') -PathType Container)) { return $false }
  foreach ($item in (Get-ChildItem -LiteralPath $folder -Force)) {
    if ($managed -notcontains $item.Name -or
        ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { return $false }
  }
  return $true
}

try {
  Write-UpdateLog "Preparando a atualização na pasta original."
  if (!(Test-Path -LiteralPath $old -PathType Container)) { throw 'Pasta original ausente.' }
  if (!(Test-Path -LiteralPath (Join-Path $stage 'DUELTRACE-WebUI.exe') -PathType Leaf) -or
      !(Test-Path -LiteralPath (Join-Path $stage '_internal') -PathType Container)) {
    throw 'Pacote de atualização incompleto.'
  }
  if (Test-Path -LiteralPath $backup) { throw 'Backup temporário já existe.' }

  # Esperar o encerramento normal da janela e do processo antigo.
  Wait-Process -Id $pidOld -Timeout 30 -ErrorAction SilentlyContinue
  $still=Get-Process -Id $pidOld -ErrorAction SilentlyContinue
  if ($null -ne $still) {
    # Só força o encerramento se o PID ainda pertence a este EXE exato.
    $runningPath=$null
    try { $runningPath=$still.Path } catch {}
    if ([string]::IsNullOrWhiteSpace($runningPath) -or
        !([string]::Equals([IO.Path]::GetFullPath($runningPath),
                          [IO.Path]::GetFullPath($exe),
                          [StringComparison]::OrdinalIgnoreCase))) {
      throw 'Processo antigo ainda aberto e identidade não confirmada.'
    }
    Write-UpdateLog "Janela encerrada mas processo persistiu; finalizando somente o DUELTRACE."
    Stop-Process -Id $pidOld -Force -ErrorAction Stop
    Wait-Process -Id $pidOld -Timeout 10 -ErrorAction SilentlyContinue
    if (Get-Process -Id $pidOld -ErrorAction SilentlyContinue) {
      throw 'Processo antigo continua bloqueando os arquivos.'
    }
  }
  New-Item -ItemType Directory -Path $backup -ErrorAction Stop | Out-Null
  try {
    # Backup e substituição de itens gerenciados; arquivos pessoais não são tocados.
    foreach ($name in $managed) {
      $target=Join-Path $old $name
      if (Test-Path -LiteralPath $target) {
        Move-Item -LiteralPath $target -Destination (Join-Path $backup $name) -ErrorAction Stop
        $moved+= $name
      }
    }
    foreach ($name in $managed) {
      $source=Join-Path $stage $name
      if (Test-Path -LiteralPath $source) {
        Move-Item -LiteralPath $source -Destination (Join-Path $old $name) -ErrorAction Stop
        $installed+= $name
      }
    }
    if (!(Test-Path -LiteralPath $exe -PathType Leaf) -or
        !(Test-Path -LiteralPath (Join-Path $old '_internal') -PathType Container)) {
      throw 'O patch não instalou os componentes necessários.'
    }
    # -PassThru permite verificar que o aplicativo novo realmente abriu.
    $newProcess=Start-Process -FilePath $exe -WorkingDirectory $old -PassThru -ErrorAction Stop
    Start-Sleep -Seconds 3
    $newProcess.Refresh()
    if ($newProcess.HasExited) { throw 'O executável atualizado fechou durante a inicialização.' }
    $restarted=$true
    Write-UpdateLog "Atualização aplicada e aplicativo reiniciado no mesmo caminho."
  } catch {
    Write-UpdateLog ("Falha na substituição/reinício: " + $_.Exception.Message)
    if ($null -ne $newProcess) {
      try {
        $newProcess.Refresh()
        if (!$newProcess.HasExited) { Stop-Process -Id $newProcess.Id -Force -ErrorAction Stop }
      } catch {}
    }
    foreach ($name in $installed) {
      $newFile=Join-Path $old $name
      if (Test-Path -LiteralPath $newFile) {
        Remove-Item -LiteralPath $newFile -Recurse -Force -ErrorAction Stop
      }
    }
    foreach ($name in $moved) {
      $previous=Join-Path $backup $name
      if (Test-Path -LiteralPath $previous) {
        Move-Item -LiteralPath $previous -Destination (Join-Path $old $name) -ErrorAction Stop
      }
    }
    if (Test-Path -LiteralPath $exe -PathType Leaf) {
      try {
        Start-Process -FilePath $exe -WorkingDirectory $old -ErrorAction Stop | Out-Null
        Write-UpdateLog "Rollback concluído; versão anterior reiniciada."
      } catch {
        Write-UpdateLog ("Rollback efetuado; reinício antigo falhou: "+$_.Exception.Message)
      }
    }
  }
} catch {
  Write-UpdateLog ("Falha antes da substituição: "+$_.Exception.Message)
} finally {
  # Staging contém apenas arquivos do pacote verificado e não é usado após a troca.
  if (Test-Path -LiteralPath $stage) {
    try { Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction Stop }
    catch { Write-UpdateLog "Pasta temporária não pôde ser limpa." }
  }
  if ($restarted) {
    # Temporários antigos criados pelo instalador anterior são realocados
    # para os dados locais, sem apagar qualquer arquivo.
    $parent=Split-Path $old -Parent
    $legacyPrefix='.' + (Split-Path $old -Leaf) + '-staged-'
    $possible=@(Get-ChildItem -LiteralPath $parent -Directory -Force -ErrorAction SilentlyContinue)
    foreach ($candidate in $possible) {
      if (!$candidate.Name.StartsWith($legacyPrefix,[StringComparison]::OrdinalIgnoreCase)) { continue }
      $suffix=$candidate.Name.Substring($legacyPrefix.Length)
      if ($suffix -cnotmatch '^[0-9a-f]{12}$') { continue }
      if ($candidate.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
      $items=@(Get-ChildItem -LiteralPath $candidate.FullName -Force -ErrorAction SilentlyContinue)
      $unknown=@($items | Where-Object { ($managed -notcontains $_.Name) -or
        ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) })
      if ($unknown.Count -gt 0) {
        Write-UpdateLog "Pasta temporária antiga contém dados desconhecidos: preservada."
        continue
      }
      try {
        $destination=Join-Path (Split-Path $backup -Parent) ('stage-legado-'+[guid]::NewGuid().ToString('N'))
        Move-Item -LiteralPath $candidate.FullName -Destination $destination -ErrorAction Stop
        Write-UpdateLog "Pasta temporária de versão antiga realocada para os dados locais."
      } catch { Write-UpdateLog "Pasta temporária anterior preservada por falha na migração." }
    }
    # Pastas de backups locais ficam nos dados do aplicativo, não junto ao EXE.
    # Mover SOMENTE pastas legadas conhecidas da versão anterior.
    if ($legacy -and (Test-Path -LiteralPath $legacy)) {
      if (Confirm-ManagedBackup $legacy) {
        try {
          $destination=Join-Path (Split-Path $backup -Parent) ('backup-legado-'+[guid]::NewGuid().ToString('N'))
          Move-Item -LiteralPath $legacy -Destination $destination -ErrorAction Stop
          Write-UpdateLog "Backup legado removido da pasta de instalação."
        } catch { Write-UpdateLog "Backup legado preservado no local antigo por falha na migração." }
      } else { Write-UpdateLog "Backup legado não movido: conteúdo não reconhecido." }
    }
  } elseif (Test-Path -LiteralPath $backup) {
    # Em erro, manter o backup caso algum componente não tenha sido restaurado.
    $remaining=@(Get-ChildItem -LiteralPath $backup -Force -ErrorAction SilentlyContinue)
    if ($remaining.Count -eq 0) {
      try { Remove-Item -LiteralPath $backup -Force -ErrorAction Stop } catch {}
    }
  }
}
"""
    for old, new in paths.items():
        script = script.replace(old, new)
    return script


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
    if home==original/"_internal" or home.is_relative_to(original/"_internal"):
        raise UnsafeUpdate("Os dados pessoais estão dentro de _internal; mova-os para fora antes de atualizar.")
    if (not original.is_dir() or original.is_symlink() or
            any((original / name).is_symlink() for name in
                ("DUELTRACE-WebUI.exe","_internal","LEIA-ME-SEGURANCA.txt"))):
        raise UnsafeUpdate("Pasta de instalação inválida ou contém links simbólicos.")
    # Os temporários e backups ficam no diretório de dados, não em uma nova pasta
    # vizinha ao executável. Nunca sobrescrever o usuário por padrão.
    work=home/"preview_updates"
    work.mkdir(parents=True,exist_ok=True)
    if work.is_symlink():
        raise UnsafeUpdate("Diretório temporário de atualizações inválido.")
    legacy_backup=original.parent/("."+original.name+"-backup")
    if legacy_backup.is_symlink():
        raise UnsafeUpdate("Backup legado contém link simbólico; revise-o antes.")
    token=uuid4().hex[:12]
    stage=work/("stage-"+token)
    backup=work/("rollback-"+token)
    archive=work/("download-"+uuid4().hex+".zip")
    if any(p.exists() or p.is_symlink() for p in (stage,backup,archive)):
        raise UnsafeUpdate("Preparação de atualização já existe.")
    try:
        (downloader or download_preview_zip)(info,archive)
        (unpacker or unpack_preview_zip)(archive,stage,info)
        script=_powershell_replace_script(original,stage,backup,
                                          __import__("os").getpid(),legacy_backup)
        if launcher is None:
            encoded=base64.b64encode(script.encode("utf-16le")).decode("ascii")
            subprocess.Popen(
                ["powershell.exe","-NoProfile","-NonInteractive",
                 "-WindowStyle","Hidden","-EncodedCommand",encoded],
                creationflags=(getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)
                               | getattr(subprocess,"CREATE_NO_WINDOW",0)),
                close_fds=True)
        else:
            launcher(script)
        return {"started":True,"status":(
            f"DUELTRACE v{info['version']} verificado. O aplicativo fecha e "
            "reabre automaticamente na mesma pasta. Os arquivos pessoais são preservados."),
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
