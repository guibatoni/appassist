"""Consulta SOMENTE metadados da última release estável do DUELTRACE.

Não executa nem baixa arquivos. Não envia dados de mods, ISO, RAM, sistema ou
identificadores do usuário. O acesso à rede acontece apenas após clique
explícito em "Verificar atualizações" na interface Windows.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
import webbrowser

from dueltrace_preview_updates import installed_preview_build_id
from dueltrace_public_distribution import PUBLIC_UPDATES_API, PUBLIC_UPDATES_WEB

CURRENT_VERSION = "0.9.7"
CURRENT_CHANNEL = "preview"
RELEASE_API = PUBLIC_UPDATES_API + "/releases/latest"
RELEASE_PAGE = PUBLIC_UPDATES_WEB + "/releases"
MAX_RESPONSE_BYTES = 256 * 1024
VERSION_PATTERN = re.compile(r"^v?(\d{1,4})\.(\d{1,4})\.(\d{1,4})$")


def parse_version(value: str) -> tuple[int, int, int] | None:
    """Versão semver simples; não faz comparação alfabética (ex. 0.10 > 0.9)."""
    if not isinstance(value, str):
        return None
    match = VERSION_PATTERN.fullmatch(value.strip())
    if not match:
        return None
    return tuple(int(x) for x in match.groups())


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Não seguir redirecionamentos externos durante a verificação."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_stable_release() -> dict:
    request = urllib.request.Request(RELEASE_API, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "DUELTRACE-VersionChecker/0.7.5",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=7) as response:
        if response.status != 200 or response.geturl() != RELEASE_API:
            raise ValueError("Resposta inesperada do servidor de versões.")
        length = response.headers.get("Content-Length")
        if length and int(length) > MAX_RESPONSE_BYTES:
            raise ValueError("Resposta de atualização excede limite.")
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("Resposta de atualização excede limite.")
    data = json.loads(body.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Metadados de atualização inválidos.")
    return data


def check_for_updates(*, fetcher=None, preview_fetcher=None, installed_run_id=None,
                      current_version=CURRENT_VERSION, channel=CURRENT_CHANNEL) -> dict:
    """Compara com release estável, sem assumir que snapshots de CI são releases."""
    current = parse_version(current_version)
    if current is None or channel not in ("preview", "stable"):
        raise ValueError("Versão local inválida.")
    result = {
        "currentVersion": current_version,
        "channel": channel,
        "latestStable": None,
        "latestPreview": None,
        "previewRunId": None,
        "previewPage": None,
        "previewBranch": None,
        "previewBuildSha": None,
        "previewVersion": None,
        "releasePage": RELEASE_PAGE,
        "automaticInstallReady": False,
        "previewError": None,
        "automaticInstallReason": "Instalação automática bloqueada: não há instalador público assinado e verificado.",
        "status": "unavailable",
        "updateAvailable": False,
        "message": "",
    }
    try:
        release = (fetcher or fetch_stable_release)()
        if not isinstance(release, dict):
            raise ValueError("Resposta de versões inválida.")
        if release.get("draft") or release.get("prerelease"):
            raise ValueError("Endpoint não retornou uma release estável.")
        tag = release.get("tag_name")
        latest = parse_version(tag)
        if latest is None:
            raise ValueError("Tag de release não reconhecida.")
        expected_page = f"{PUBLIC_UPDATES_WEB}/releases/tag/{tag}"
        if release.get("html_url") != expected_page:
            raise ValueError("Origem da release não corresponde ao repositório oficial.")
        result["latestStable"] = tag
        if latest > current:
            result["status"] = "update_available"
            result["updateAvailable"] = True
            result["message"] = (
                f"Existe uma versão estável mais recente: {tag}. "
                "A instalação não é automática."
            )
        elif latest == current and channel == "stable":
            result["status"] = "up_to_date"
            result["message"] = "Você já utiliza a versão estável mais recente."
        elif latest == current and channel == "preview":
            result["status"] = "preview"
            result["message"] = (
                "Sua prévia tem o mesmo número da release estável. "
                "O conteúdo pode ser diferente; confira as notas oficiais."
            )
        else:
            result["status"] = "preview_ahead" if channel == "preview" else "up_to_date"
            result["message"] = (
                f"Sua versão {channel} é mais nova que a última estável ({tag}). "
                "Prévias de testes não são publicadas no canal de releases estáveis."
                if channel == "preview" else
                "Nenhuma versão estável mais recente foi publicada."
            )
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError,
            urllib.error.URLError) as exc:
        result["message"] = (
            "Não foi possível consultar o GitHub. Confira a internet ou tente "
            "novamente; nenhuma alteração foi realizada."
        )
    # Preview and stable versions are BOTH discovered from PUBLIC Releases.
    # No GitHub Actions API, workflow IDs, CI artifacts or private repository
    # credentials are used by the customer-facing update checker.
    if channel == "preview" and (preview_fetcher is not None or fetcher is None):
        try:
            if preview_fetcher is not None:
                preview = preview_fetcher()
            else:
                # Import lazily: the preview installer imports parse_version.
                from dueltrace_preview_installer import fetch_latest_preview_package
                preview = fetch_latest_preview_package(
                    current_version=current_version,
                    installed_run_id=installed_run_id if type(installed_run_id) is int
                                     else installed_preview_build_id(),
                )
            if preview is not None:
                if not isinstance(preview,dict):
                    raise ValueError("Metadados públicos da Preview inválidos.")
                run_id=preview.get("run_id")
                version=preview.get("version")
                sha=preview.get("sha")
                page=preview.get("page")
                from dueltrace_public_distribution import PUBLIC_UPDATES_WEB
                tag=f"preview-v{version}-r{run_id}"
                if (type(run_id) is not int or not 0<run_id<10**15
                        or parse_version(version) is None
                        or type(sha) is not str
                        or not re.fullmatch(r"[a-f0-9]{40}",sha)
                        or page!=f"{PUBLIC_UPDATES_WEB}/releases/tag/{tag}"):
                    raise ValueError("Preview não corresponde ao canal público.")
                remote=parse_version(version)
                result["latestPreview"]=f"v{version} Preview"
                result["previewVersion"]=version
                result["previewRunId"]=run_id
                result["previewPage"]=page
                result["previewBuildSha"]=sha[:10]
                installed=(installed_run_id if type(installed_run_id) is int
                           else installed_preview_build_id())
                if result["status"]!="update_available":
                    if remote<current:
                        result["status"]="preview_older"
                        result["message"]="Nenhuma Preview mais recente publicada."
                    elif remote>current or (type(installed) is int and
                                            0<installed<run_id):
                        result["status"]="preview_update_available"
                        result["updateAvailable"]=True
                        result["message"]="Nova Preview disponível no canal público."
                    elif type(installed) is int and installed>=run_id:
                        result["status"]="preview_current"
                        result["message"]="O build instalado é igual ou mais novo."
                    else:
                        result["status"]="preview_build_unknown"
                        result["message"]="Build local não comparável; atualização requer revisão."
            elif result["status"]=="unavailable":
                result["message"]="Nenhuma versão pública disponível neste momento."
        except (OSError,ValueError,TypeError,UnicodeError,urllib.error.URLError,
                json.JSONDecodeError):
            result["previewStatus"]="unavailable"
            result["previewError"]=(
                "Canal público de versões temporariamente indisponível. "
                "Não é necessário login do GitHub.")
    return result


def open_official_releases(run_id: int | None = None) -> bool:
    """Open only the public binary releases channel, never the private source."""
    if run_id is not None and (type(run_id) is not int or not 0<=run_id<10**15):
        raise ValueError("ID do build inválido.")
    return bool(webbrowser.open(RELEASE_PAGE, new=2))
