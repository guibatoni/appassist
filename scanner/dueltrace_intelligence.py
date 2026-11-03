"""Análise MultiMod automática, local, auditável e assistida por Ollama.

A ISO nunca é enviada ao modelo. Parsers determinísticos produzem dados e
evidências; Ollama pode sugerir INVESTIGAÇÕES, não criar cartas/drops/efeitos
ou validar o funcionamento de mecânicas. Arte é extraída do mod do usuário
somente por adaptadores conhecidos e permanece na máquina local.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from auto_mods import ModCatalog, atomic_json, load_json
from ia_local import DEFAULT_MODEL, analyse_with_local_ai, save_suggestion
from investigador_iso import investigate

MODEL_LIST_URL = "http://127.0.0.1:11434/api/tags"
REPORT_SCHEMA = 1
MAX_FILE_RECORDS = 80


def ollama_status(model: str = DEFAULT_MODEL, *, timeout: float = 1.5) -> dict:
    """Detecta o servidor e o modelo instalado sem iniciar serviços ou baixar dados."""
    if not isinstance(model, str) or not model or len(model) > 96:
        return {"available": False, "state": "modelo_invalido"}
    try:
        req = Request(MODEL_LIST_URL, headers={"Accept": "application/json"})
        with urlopen(req, timeout=max(.2, min(timeout, 6))) as response:
            if response.status != 200:
                return {"available": False, "state": "http_erro"}
            payload = json.loads(response.read(128_000).decode("utf-8"))
        names = {str(row.get("name", "")) for row in payload.get("models", [])
                 if isinstance(row, dict)}
        if model not in names:
            return {
                "available": False, "state": "modelo_ausente",
                "message": f"Instale o modelo local: ollama pull {model}",
            }
        return {"available": True, "state": "pronto", "model": model}
    except (OSError, HTTPError, URLError, TimeoutError, ValueError, UnicodeError):
        return {
            "available": False, "state": "ollama_indisponivel",
            "message": "Ollama local não está disponível; análise estrutural continua.",
        }


def inventory_from_profile(profile: dict) -> dict:
    """Índice recuperado dos arquivos já escaneados; nunca lê/retorna binário."""
    directory = profile.get("scan_result_dir")
    meta = {}
    if isinstance(directory, str) and directory:
        meta = load_json(Path(directory) / "relatorio.json", {})
    entries = meta.get("arquivos_discos", [])
    if not isinstance(entries, list):
        entries = []
    records = []
    for row in entries[:MAX_FILE_RECORDS]:
        if not isinstance(row, dict):
            continue
        records.append({
            "name": str(row.get("nome", ""))[:150],
            "size": row.get("tamanho") if type(row.get("tamanho")) is int else None,
        })
    features = profile.get("supported_features", {})
    cards = profile.get("cards", []) if features.get("cards") else []
    return {
        "iso_files_indexed": len(entries),
        "files_sample": records,
        "cards": len(cards),
        "opponents": len(profile.get("opponents", [])) if features.get("opponents") else 0,
        "drop_entries": len(profile.get("drops", [])) if features.get("drops") else 0,
        "validated_fusions": len(profile.get("fusion_recipes", []))
        if features.get("fusions") else 0,
        "effects_with_provenance": sum(bool(c.get("effect_source") and
                                            c.get("effect_text")) for c in cards),
        "art_extracted": bool(features.get("art")),
        "art_path": profile.get("art_root") if features.get("art") else None,
        "verification": profile.get("verified", {}),
    }


class MultiModIntelligence:
    """Roda exclusivamente em worker, nunca na thread de widgets Tkinter."""

    def __init__(self, catalog: ModCatalog):
        self.catalog = catalog

    def inspect(self, image: Path, *, model: str = DEFAULT_MODEL,
                use_ollama: bool = True, emit=None) -> dict:
        image = Path(image).resolve()
        entry = self.catalog.lookup(image)
        if not entry:
            return {"state": "sem_perfil", "ai": "não_iniciada"}
        profile = self.catalog.profile_for(entry)
        if not profile:
            return {"state": "perfil_invalido", "ai": "não_iniciada"}
        sha = entry["sha256"]
        work_dir = self.catalog.home / "investigacoes"
        report_path = work_dir / f"{sha}.json"
        cached = load_json(report_path, {})
        if (cached.get("hash_rom") == sha and
                cached.get("analysis_schema") == REPORT_SCHEMA):
            report = dict(cached)
            report_state = "cache"
        else:
            if emit:
                emit({"event": "intelligence", "message": "Investigando evidências do mod…"})
            # Pode falhar para mods não reconhecidos. Não suspende o catálogo.
            try:
                report = investigate(image, profile)
            except (OSError, ValueError, RuntimeError) as exc:
                report = {
                    "file": image.name, "hash_rom": sha,
                    "uncertainties": [{"field": "investigacao",
                                       "status": "erro",
                                       "reason": str(exc)[:220]}],
                    "evidence": [], "features": profile.get("verified", {}),
                    "candidates": {},
                }
            report_state = "analisado"
        report["analysis_schema"] = REPORT_SCHEMA
        report["hash_rom"] = sha
        report["inventory"] = inventory_from_profile(profile)
        report["analysis_notice"] = (
            "Ollama não valida tabelas. Candidatos não são importados "
            "ao catálogo sem critérios independentes."
        )
        atomic_json(report_path, report)
        result = {
            "state": report_state,
            "report_path": str(report_path),
            "ai": "desativada",
            "inventory": report["inventory"],
        }
        if not use_ollama:
            return result
        status = ollama_status(model=model)
        result["ai"] = status["state"]
        if not status["available"]:
            result["ai_message"] = status.get("message", "")
            return result

        safe_model = re.sub(r"[^a-zA-Z0-9_.-]", "_", model)[:100]
        ai_path = work_dir / f"{sha}.{safe_model}.ollama.json"
        previous = load_json(ai_path, {})
        if previous.get("model") == model and previous.get("rom_sha256") == sha:
            result.update({"ai": "hipoteses_em_cache",
                           "ai_report_path": str(ai_path)})
            return result
        if emit:
            emit({"event": "intelligence", "message": f"Ollama ({model}): analisando evidências…"})
        try:
            suggestion = analyse_with_local_ai(report, model=model, timeout=120)
        except (ConnectionError, ValueError, RuntimeError) as exc:
            result["ai"] = "erro_na_investigacao"
            result["ai_message"] = str(exc)[:220]
            return result
        suggestion.update({
            "model": model,
            "rom_sha256": sha,
            "verified_data_changed": False,
        })
        save_suggestion(ai_path, suggestion)
        result.update({"ai": "hipoteses_salvas",
                       "ai_report_path": str(ai_path)})
        return result
