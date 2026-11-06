"""Análise MultiMod automática, local, auditável e assistida por Ollama.

A ISO nunca é enviada ao modelo. Parsers determinísticos produzem dados e
evidências; Ollama pode sugerir INVESTIGAÇÕES, não criar cartas/drops/efeitos
ou validar o funcionamento de mecânicas. Arte é extraída do mod do usuário
somente por adaptadores conhecidos e permanece na máquina local.
"""
from __future__ import annotations

import json
import re
import hashlib
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from auto_mods import ModCatalog, atomic_json, load_json
from ia_local import DEFAULT_MODEL, analyse_with_local_ai, save_suggestion, minimal_evidence
from investigador_iso import investigate
from fusion_autopromote import import_structural_fusions
from effects_audit import audit_effect_sources
from dueltrace_mod_diagnostic import diagnose_layout

MODEL_LIST_URL = "http://127.0.0.1:11434/api/tags"
REPORT_SCHEMA = 7
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
    drops = profile.get("drops", []) if features.get("drops") else []
    opponents = profile.get("opponents", []) if features.get("opponents") else []
    effect_samples = [
        {"id": c.get("id"),
         "text": str(c.get("effect_text") or "")[:320],
         "source": str(c.get("effect_source") or "")[:100]}
        for c in cards if c.get("effect_text") and c.get("effect_source")
    ][:8]
    return {
        "iso_files_indexed": len(entries),
        "files_sample": records,
        "card_samples": [
            {"id": c.get("id"), "name": str(c.get("name") or "")[:80],
             "category": c.get("category"),
             "atk": c.get("atk"), "def": c.get("def")}
            for c in cards[:16]
        ],
        "effect_samples": effect_samples,
        "opponent_samples": [
            {"id": x.get("id"), "name": str(x.get("name") or "")[:80]}
            for x in opponents[:12]
        ],
        "drop_samples": [
            {"opponent_id": x.get("opponent_id"),
             "card_id": x.get("card_id"), "group": str(x.get("group") or "")[:80],
             "weight": x.get("weight")}
            for x in drops[:12]
        ],
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


def local_report_fingerprint(entry: dict, profile: dict) -> str:
    """Invalida diagnósticos após atualização local, mesmo com SHA da ISO igual."""
    items = []
    for path in (
        Path(entry.get("profile_path") or "profile-missing"),
        Path(profile.get("scan_result_dir") or "analysis-missing") / "relatorio.json",
    ):
        try:
            stat = path.stat()
            items.append([stat.st_size, stat.st_mtime_ns])
        except OSError:
            items.append(None)
    raw = json.dumps({
        "schema": REPORT_SCHEMA,
        "rom": entry.get("sha256"),
        "files": items,
    },sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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
        fusion_path = work_dir / f"{sha}.fusoes.json"
        effects_path = work_dir / f"{sha}.efeitos-auditoria.json"
        cached = load_json(report_path, {})
        profile_digest = local_report_fingerprint(entry, profile)
        if (cached.get("hash_rom") == sha and
                cached.get("analysis_schema") == REPORT_SCHEMA and
                cached.get("profile_digest") == profile_digest):
            report = dict(cached)
            report_state = "cache"
        else:
            if emit:
                emit({"event": "intelligence", "message": "Investigando evidências do mod…"})
            # Pode falhar para mods não reconhecidos. Não suspende o catálogo.
            try:
                report = investigate(image, profile, output_path=report_path)
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
        fusion_status={"status":"sem_banco_validado","count":0}
        # New imports can now probe seven banks automatically, including a
        # renamed resource, but ONLY if cards belong to the exact ISO and
        # are fully validated. Do not invent fusion results from a partial
        # catalog or import a single merely plausible bank.
        probe_state=work_dir / f"{sha}.fusoes-probe-status.json"
        if (not fusion_path.is_file()
                and profile.get("verified",{}).get("cartas")=="verificado"
                and len(profile.get("cards",[]))==722
                and type(entry.get("size")) is int
                and type(entry.get("mtime_ns")) is int):
            stamp={"schema":1,"revision":1,"sha256":sha,
                   "size":entry["size"],"mtime_ns":entry["mtime_ns"]}
            cached_probe=load_json(probe_state,{})
            if any(cached_probe.get(k)!=v for k,v in stamp.items()):
                try:
                    from extrator_fusoes import (
                        analyze_fusion_banks, save_fusion_report)
                    found=analyze_fusion_banks(
                        image,expected_size=entry["size"],
                        expected_mtime_ns=entry["mtime_ns"])
                    if (found.get("valid_banks")==7
                            and found.get("matching_banks")==7
                            and found.get("divergent_banks") is False
                            and found.get("bank_conflicts")==0):
                        found["rom_sha256"]=sha
                        save_fusion_report(fusion_path,found)
                        atomic_json(probe_state,{
                            **stamp,"status":"seven_mirrors_consistent"})
                    else:
                        atomic_json(probe_state,{
                            **stamp,"status":"unsupported_or_divergent"})
                except (OSError, ValueError, RuntimeError, OverflowError):
                    # An unsupported fusion layout is not a failed card scan.
                    atomic_json(probe_state,{
                        **stamp,"status":"unsupported_or_unknown"})
        if fusion_path.is_file():
            try:
                fusion_status=import_structural_fusions(self.catalog,sha)
                profile=self.catalog.profile_for(entry) or profile
            except (OSError, ValueError, RuntimeError) as exc:
                fusion_status={"status":"revisao_necessaria","count":0,
                               "reason":str(exc)[:200]}
        audit_state={"status":"não_inspecionado","candidate_files":[]}
        if report_state!="cache" or not effects_path.is_file():
            try:
                audit_state=audit_effect_sources(image,rom_sha256=sha)
                atomic_json(effects_path,audit_state)
            except (OSError,ValueError,RuntimeError) as exc:
                audit_state={"status":"não_inspecionado","reason":str(exc)[:180]}
        else:
            audit_state=load_json(effects_path,{"status":"sem_auditoria"})
        report["effects_audit_status"]=audit_state.get("status","sem_auditoria")
        report["effects_audit_candidate_sources"]=len(audit_state.get("candidate_files",[]))
        report["analysis_schema"] = REPORT_SCHEMA
        report["profile_digest"] = local_report_fingerprint(entry,profile)
        report["hash_rom"] = sha
        report["inventory"] = inventory_from_profile(profile)
        # Não prometer que o LLM extrai dados binários. Relatar claramente
        # o motivo do parser rejeitar nomes, drops, artes e executáveis.
        scan_dir=profile.get("scan_result_dir")
        scan_info=(load_json(Path(scan_dir)/"relatorio.json",{})
                   if isinstance(scan_dir,str) and scan_dir else {})
        report["scan_diagnostic"]=diagnose_layout(scan_info,profile)
        report["analysis_notice"] = (
            "Ollama não valida fusões. Somente sete bancos idênticos e "
            "sem conflitos permitem importar receitas com status estrutural; "
            "não equivalem a teste dentro do jogo."
        )
        atomic_json(report_path, report)
        result = {
            "state": report_state,
            "sha256": sha,
            "report_path": str(report_path),
            "ai": "desativada",
            "inventory": report["inventory"],
            "fusions": fusion_status,
            "effects_audit": {
                "status": audit_state.get("status"),
                "candidate_sources":len(audit_state.get("candidate_files",[])),
                "report_path":str(effects_path) if effects_path.is_file() else None,
            },
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
        evidence_fingerprint = hashlib.sha256(
            json.dumps(minimal_evidence(report),ensure_ascii=False,
                       sort_keys=True).encode("utf-8")
        ).hexdigest()
        previous = load_json(ai_path, {})
        if (previous.get("model") == model and previous.get("rom_sha256") == sha
                and previous.get("evidence_sha256") == evidence_fingerprint):
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
            "evidence_sha256": evidence_fingerprint,
            "verified_data_changed": False,
        })
        save_suggestion(ai_path, suggestion)
        result.update({"ai": "hipoteses_salvas",
                       "ai_report_path": str(ai_path)})
        return result
