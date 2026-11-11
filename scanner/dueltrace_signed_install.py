"""Atualização assistida de releases oficiais assinadas do DUELTRACE.

Regras: não instalar artefatos de Actions, ZIP não assinado ou versão antiga;
só baixar instalador de release estável com hash publicado pela API GitHub,
assinatura Authenticode válida e MESMO editor verificado do app instalado.
Credenciais nunca são armazenadas aqui. O instalador assinado executa a
substituição do programa; este módulo não modifica o exe em execução.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from dueltrace_update_checker import CURRENT_VERSION, fetch_stable_release, parse_version
from dueltrace_public_distribution import PUBLIC_UPDATES_WEB
from dueltrace_preview_updates import NoRedirect

# Só configurar após validação jurídica do certificado REAL da Batoni Dev.
# O valor vazio desliga TODA instalação automática.
# A primeira versão assinada é a âncora de confiança para futuras atualizações.
MAX_INSTALLER_BYTES = 220 * 1024 * 1024
TRUSTED_HOSTS = {"github.com", "release-assets.githubusercontent.com",
                 "objects.githubusercontent.com"}
DIGEST = re.compile(r"sha256:([a-fA-F0-9]{64})\Z")


class UnsafeUpdate(ValueError):
    pass


class TrustedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname not in TRUSTED_HOSTS:
            raise UnsafeUpdate("Redirecionamento para domínio não autorizado.")
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def select_signed_installer(release: dict, installed_version: str) -> dict | None:
    """Metadados somente, sem baixar o binário; None se não houver release nova."""
    if not isinstance(release,dict) or release.get("draft") or release.get("prerelease"):
        raise UnsafeUpdate("A instalação automática exige release estável.")
    tag = release.get("tag_name")
    current = parse_version(installed_version)
    version = parse_version(tag)
    if not version or not current:
        raise UnsafeUpdate("Tag inválida.")
    if version <= current:
        return None
    if release.get("html_url") != f"{PUBLIC_UPDATES_WEB}/releases/tag/{tag}":
        raise UnsafeUpdate("Release de origem não autorizada.")
    name = f"DUELTRACE-Setup-{tag}.exe"
    url = f"{PUBLIC_UPDATES_WEB}/releases/download/{tag}/{name}"
    assets = release.get("assets")
    if not isinstance(assets,list):
        raise UnsafeUpdate("Release ainda não contém instalador.")
    matches=[a for a in assets if isinstance(a,dict) and a.get("name")==name]
    if len(matches)!=1:
        raise UnsafeUpdate("Release sem instalador assinado único.")
    item=matches[0]
    m=DIGEST.fullmatch(str(item.get("digest") or ""))
    size=item.get("size")
    if (not m or type(size) is not int or not 0 < size <= MAX_INSTALLER_BYTES
            or item.get("browser_download_url")!=url):
        raise UnsafeUpdate("Instalador sem hash SHA-256 verificável ou origem válida.")
    return {"version":tag,"filename":name,"url":url,"sha256":m.group(1).lower(),"size":size}


def _signed_identity(path: Path) -> dict | None:
    """Identidade do certificado Authenticode com cadeia validada no Windows.

    A assinatura da própria instalação vira a âncora de confiança. Exigir
    exatamente o mesmo certificado (thumbprint) na atualização previne
    downloads de executáveis assinados por outra editora.
    """
    if sys.platform != "win32":
        return None
    quoted=str(path.resolve()).replace("'","''")
    script=(
        f"$s=Get-AuthenticodeSignature -LiteralPath '{quoted}';"
        "if($s.Status -ne 'Valid' -or !$s.SignerCertificate){exit 7};"
        "$c=$s.SignerCertificate;"
        "$o=@{subject=$c.Subject;issuer=$c.Issuer;thumbprint=$c.Thumbprint};"
        "[Console]::Out.Write(($o | ConvertTo-Json -Compress))"
    )
    encoded=base64.b64encode(script.encode("utf-16le")).decode("ascii")
    try:
        output=subprocess.run(
            ["powershell.exe","-NoProfile","-NonInteractive","-EncodedCommand",encoded],
            capture_output=True,text=True,timeout=15,check=False)
        if output.returncode!=0 or len(output.stdout)>4096:
            return None
        data=json.loads(output.stdout)
        if not isinstance(data,dict):
            return None
        if not all(isinstance(data.get(field),str) and data[field]
                   for field in ("subject","issuer","thumbprint")):
            return None
        if not re.fullmatch("[0-9A-Fa-f]{40}",data["thumbprint"]):
            return None
        return {"subject":data["subject"],"issuer":data["issuer"],
                "thumbprint":data["thumbprint"].upper()}
    except (OSError,ValueError,TypeError,subprocess.TimeoutExpired):
        return None


def _signed_subject(path: Path) -> str | None:
    identity=_signed_identity(path)
    return identity["subject"] if identity else None


def trusted_installer_ready(*, publisher: str | None = None,
                            installed_exe: Path | None = None,
                            signer=None) -> bool:
    """Sem EXE assinado não há auto-update; não precisa editar o código
    quando a primeira versão comercial assinada for lançada.
    """
    if sys.platform!="win32":
        return False
    if installed_exe is None and not getattr(sys,"frozen",False):
        return False
    installed_exe = installed_exe or Path(sys.executable)
    if not installed_exe.is_file():
        return False
    if publisher is not None and (not isinstance(publisher,str)
                                  or not publisher.strip()):
        return False
    if signer is None:
        identity=_signed_identity(installed_exe)
        if not identity:
            return False
        if publisher is not None and identity["subject"] != publisher:
            return False
        return True
    if publisher is None:
        return False
    return signer(installed_exe) == publisher


def _download_release(info: dict, destination: Path, *, opener=None) -> Path:
    if destination.exists() or destination.is_symlink():
        raise UnsafeUpdate("Destino de atualização já existe.")
    request=urllib.request.Request(
        info["url"],headers={"User-Agent":"DUELTRACE-Signed-Release-Updater/0.7.5"})
    http=opener or urllib.request.build_opener(TrustedRedirect())
    digest=hashlib.sha256()
    seen=0
    try:
        with http.open(request,timeout=18) as response:
            final=urlsplit(response.geturl())
            if final.scheme!="https" or final.hostname not in TRUSTED_HOSTS:
                raise UnsafeUpdate("Servidor de download não autorizado.")
            with destination.open("xb") as file:
                while True:
                    chunk=response.read(1024*1024)
                    if not chunk:
                        break
                    seen+=len(chunk)
                    if seen>MAX_INSTALLER_BYTES or seen>info["size"]:
                        raise UnsafeUpdate("Tamanho excedeu o valor da release.")
                    digest.update(chunk)
                    file.write(chunk)
        if seen!=info["size"] or digest.hexdigest()!=info["sha256"]:
            raise UnsafeUpdate("Assinatura de integridade SHA-256 divergente.")
        return destination
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def install_new_release(*, data_home: Path,
                        current_version: str = CURRENT_VERSION,
                        release_fetcher=None, publisher: str | None = None,
                        signer=None, downloader=None, launcher=None) -> dict:
    """Executa apenas instalador oficial e assinado, após clique explícito."""
    if not trusted_installer_ready(publisher=publisher, signer=signer):
        raise UnsafeUpdate("Editor não verificado; instalação automática bloqueada.")
    release=(release_fetcher or fetch_stable_release)()
    info=select_signed_installer(release,current_version)
    if not info:
        return {"started":False,"status":"Sem release estável mais recente."}
    installed_identity = _signed_identity(Path(sys.executable)) if signer is None else None
    if signer is None and installed_identity is None:
        raise UnsafeUpdate("Assinatura de origem não verificada.")
    expected_publisher = publisher or (
        installed_identity["subject"] if installed_identity else None
    )
    home=Path(data_home).resolve()
    folder=home/"trusted_updates"
    folder.mkdir(parents=True,exist_ok=True)
    if folder.is_symlink():
        raise UnsafeUpdate("Pasta de atualizações insegura.")
    installer=folder/info["filename"]
    # Não reutilizar instalador antigo, mesmo com mesmo nome.
    if installer.is_symlink():
        raise UnsafeUpdate("Arquivo de atualização inseguro.")
    if installer.exists():
        installer.unlink()
    (downloader or _download_release)(info,installer)
    candidate_identity = _signed_identity(installer) if signer is None else None
    candidate_subject = (candidate_identity["subject"] if candidate_identity else None
                         ) if signer is None else signer(installer)
    if (candidate_subject != expected_publisher
            or (signer is None and candidate_identity != installed_identity)):
        installer.unlink(missing_ok=True)
        raise UnsafeUpdate("Certificado do instalador não corresponde ao DUELTRACE.")
    (launcher or (lambda p: subprocess.Popen([str(p)],cwd=str(p.parent),
                                              close_fds=True)))(installer)
    return {"started":True,"version":info["version"],
            "status":"Instalador oficial assinado iniciado. Confirme a instalação no Windows."}
