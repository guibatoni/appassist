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

from dueltrace_preview_updates import (
    fetch_latest_preview, installed_preview_build_id, BRANCH_VERSIONS
)

CURRENT_VERSION = "0.7.5"
CURRENT_CHANNEL = "preview"
RELEASE_API = "https://api.github.com/repos/guibatoni/appassist/releases/latest"
RELEASE_PAGE = "https://github.com/guibatoni/appassist/releases/latest"
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
        expected_page = f"https://github.com/guibatoni/appassist/releases/tag/{tag}"
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
    # As versões Preview são compiladas no Actions, não em releases/latest.
    # Se um teste fornecer apenas o fetcher estável, não consulte a rede
    # indiretamente durante os testes. Em produção, ambos são consultados.
    if channel == "preview" and (preview_fetcher is not None or fetcher is None):
        try:
            preview = (preview_fetcher or fetch_latest_preview)()
            if preview is not None:
                if not isinstance(preview, dict):
                    raise ValueError("Dados Preview inválidos.")
                run_id = preview.get("run_id")
                branch = preview.get("branch")
                sha = preview.get("head_sha")
                if (type(run_id) is not int or not 0 < run_id < 10**15
                        or branch not in (
                            "security/dueltrace-trusted-distribution-v073",
                            "feature/dueltrace-v074-drops-ranks-frames",
                            "feature/dueltrace-v075-rank-forensics-safe-updater",
                            "feature/dueltrace-v073-assets-hardening",
                            "fix/dueltrace-v073-preview-update-button")
                        or not isinstance(sha, str)
                        or not re.fullmatch(r"[0-9a-f]{40}", sha)
                        or preview.get("page") !=
                        f"https://github.com/guibatoni/appassist/actions/runs/{run_id}"):
                    raise ValueError("Build Preview com origem inválida.")
                remote_label = preview.get("version", BRANCH_VERSIONS.get(branch))
                remote_version = parse_version(remote_label)
                if remote_version is None or remote_label != BRANCH_VERSIONS.get(branch):
                    raise ValueError("Versão Preview não corresponde à branch publicada.")
                result["latestPreview"] = f"v{remote_label} Preview (não assinado)"
                result["previewVersion"] = remote_label
                result["previewRunId"] = run_id
                result["previewPage"] = preview["page"]
                result["previewBranch"] = branch
                result["previewBuildSha"] = sha[:10]
                installed = (installed_run_id if installed_run_id is not None
                             else installed_preview_build_id())
                if result["status"] == "update_available":
                    # Release estável mais nova permanece prioritária.
                    pass
                elif remote_version < current:
                    result["status"] = "preview_older"
                    result["message"] = (
                        "A prévia publicada no Actions é de uma versão anterior "
                        "à instalação atual. Nenhuma atualização necessária."
                    )
                elif remote_version > current:
                    result["status"] = "preview_update_available"
                    result["updateAvailable"] = True
                    result["message"] = (
                        f"Nova prévia v{remote_label} identificada. O pacote ainda "
                        "não é assinado: o aplicativo NÃO irá baixá-lo nem "
                        "instalá-lo automaticamente. Consulte o GitHub."
                    )
                elif type(installed) is int and installed >= run_id:
                    result["status"] = "preview_current"
                    result["message"] = "Este build já é igual ou mais recente que a prévia publicada."
                elif type(installed) is int and 0 < installed < run_id:
                    result["status"] = "preview_update_available"
                    result["updateAvailable"] = True
                    result["message"] = (
                        "Novo build Preview identificado. A versão é experimental "
                        "e não assinada; a instalação automática permanece "
                        "bloqueada por segurança."
                    )
                else:
                    result["status"] = "preview_build_unknown"
                    result["message"] = (
                        "Uma prévia foi encontrada, mas o build instalado não "
                        "possui identidade comparável. Consulte os detalhes "
                        "antes de atualizar manualmente."
                    )
            elif result["status"] == "unavailable" and not result["latestStable"]:
                result["message"] = (
                    "Nenhum pacote Preview foi identificado. Use os links "
                    "oficiais do GitHub para verificar manualmente."
                )
        except (OSError, ValueError, TypeError, UnicodeError,
                urllib.error.URLError, json.JSONDecodeError):
            # Se a API de Actions falhar, preserve a comparação estável.
            result["previewStatus"] = "unavailable"
            if result["status"] == "unavailable":
                result["message"] = (
                    "A consulta automática falhou. Você ainda pode abrir "
                    "as versões e builds no GitHub manualmente."
                )
    return result


def open_official_releases(run_id: int | None = None) -> bool:
    """Abre apenas releases ou um ID numérico de Actions do repositório oficial."""
    if run_id is not None:
        if type(run_id) is not int or not 0 <= run_id < 10**15:
            raise ValueError("ID do build inválido.")
        url = (f"https://github.com/guibatoni/appassist/actions/runs/{run_id}"
               if run_id else
               "https://github.com/guibatoni/appassist/actions/workflows/validar-webui-desktop.yml")
    else:
        url = RELEASE_PAGE
    return bool(webbrowser.open(url, new=2))
