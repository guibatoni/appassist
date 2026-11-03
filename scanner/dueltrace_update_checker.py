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

CURRENT_VERSION = "0.7.3"
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
        "User-Agent": "DUELTRACE-VersionChecker/0.7.3",
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


def check_for_updates(*, fetcher=None, current_version=CURRENT_VERSION,
                      channel=CURRENT_CHANNEL) -> dict:
    """Compara com release estável, sem assumir que snapshots de CI são releases."""
    current = parse_version(current_version)
    if current is None or channel not in ("preview", "stable"):
        raise ValueError("Versão local inválida.")
    result = {
        "currentVersion": current_version,
        "channel": channel,
        "latestStable": None,
        "releasePage": RELEASE_PAGE,
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
    return result


def open_official_releases() -> bool:
    """Somente o domínio/página oficial; abre navegador padrão, sem executar ZIP."""
    return bool(webbrowser.open(RELEASE_PAGE, new=2))
