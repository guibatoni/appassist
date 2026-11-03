"""Consulta metadados públicos de builds Preview aprovados no GitHub Actions.

A verificação é acionada pelo usuário. Não baixa, executa nem instala arquivos.
URLs são construídas apenas para o repositório e branches confiáveis do DUELTRACE.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote

REPO_API = "https://api.github.com/repos/guibatoni/appassist"
REPO_WEB = "https://github.com/guibatoni/appassist"
PREVIEW_BRANCHES = (
    "fix/dueltrace-v073-preview-update-button",
    "feature/dueltrace-v073-assets-hardening",
    "security/dueltrace-trusted-distribution-v073",
    "feature/dueltrace-v074-drops-ranks-frames",
)
ARTIFACT_NAME = "DUELTRACE-Windows-Preview-Unsigned-Security-Scanned"
BUILD_INFO_FILE = "dueltrace-build.json"
MAX_BYTES = 768 * 1024
_SHA = re.compile(r"[0-9a-f]{40}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "DUELTRACE-PreviewChecker/0.7.3",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=8) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError("Resposta inesperada da API de builds.")
        size = response.headers.get("Content-Length")
        if size and int(size) > MAX_BYTES:
            raise ValueError("Resposta muito grande.")
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Resposta muito grande.")
    decoded = json.loads(data.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Resposta inválida do GitHub.")
    return decoded


def _accepted_run(item: dict, branch: str) -> bool:
    run_id = item.get("id")
    sha = item.get("head_sha")
    return (
        type(run_id) is int and 0 < run_id < 10**15
        and item.get("head_branch") == branch
        and item.get("status") == "completed"
        and item.get("conclusion") == "success"
        and item.get("event") in ("pull_request", "push")
        and isinstance(sha, str) and bool(_SHA.fullmatch(sha))
        and item.get("html_url") == f"{REPO_WEB}/actions/runs/{run_id}"
    )


def fetch_latest_preview() -> dict | None:
    """Localiza o build mais novo COM artefato não expirado, não só CI verde."""
    candidates = []
    for branch in PREVIEW_BRANCHES:
        url = f"{REPO_API}/actions/runs?branch={quote(branch, safe='')}&per_page=8"
        data = _get_json(url)
        runs = data.get("workflow_runs")
        if not isinstance(runs, list):
            raise ValueError("Lista de builds inválida.")
        candidates.extend(
            item for item in runs if isinstance(item, dict) and _accepted_run(item, branch)
        )
    candidates.sort(key=lambda item: item["id"], reverse=True)
    for item in candidates[:12]:
        run_id = item["id"]
        data = _get_json(f"{REPO_API}/actions/runs/{run_id}/artifacts?per_page=100")
        artifacts = data.get("artifacts")
        if not isinstance(artifacts, list):
            continue
        found = next((x for x in artifacts
                      if isinstance(x, dict) and x.get("name") == ARTIFACT_NAME
                      and x.get("expired") is False), None)
        if found is not None:
            return {
                "run_id": run_id,
                "head_sha": item["head_sha"],
                "branch": item["head_branch"],
                "page": item["html_url"],
                "artifact_name": ARTIFACT_NAME,
            }
    return None


def installed_preview_build_id() -> int | None:
    """Lê número do build gravado no executável; antigos são desconhecidos."""
    bundle = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    path = bundle / BUILD_INFO_FILE
    try:
        if not path.is_file() or path.stat().st_size > 2048:
            return None
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        run_id = data.get("run_id")
        if data.get("schema") != 1 or type(run_id) is not int:
            return None
        if 0 < run_id < 10**15:
            return run_id
    except (OSError, ValueError, TypeError):
        pass
    return None
