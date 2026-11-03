"""Diagnóstico por ISO do DUELTRACE — não inventa dados nem mostra caminhos privados."""
from __future__ import annotations

from pathlib import Path

from auto_mods import load_json

ART_EXPECTED = 722


def art_diagnostic(profile: dict) -> dict:
    """Diferencia não solicitada, erro, parcial e completa."""
    directory = profile.get("scan_result_dir")
    report = load_json(Path(directory) / "relatorio.json", {}) if directory else {}
    n = report.get("artes_extraidas")
    count = n if type(n) is int and n >= 0 else None
    requested = report.get("art_requested")
    if requested is None and count is None:
        state = "sem registro"
    elif requested is False:
        state = "não solicitada"
    elif count is None:
        state = "tentativa sem contagem"
    elif count == ART_EXPECTED:
        state = "extraída"
    elif count == 0:
        state = "nenhuma arte extraída"
    else:
        state = "parcial"
    explanation = str(report.get("artes_obs") or "")[:220]
    if requested and count is None and report.get("problema"):
        explanation = str(report["problema"])[:220]
    return {"state": state, "count": count, "requested": bool(requested),
            "description": explanation, "expected": ART_EXPECTED}


def mod_diagnostic(entry: dict, profile: dict | None, *,
                   intelligence: dict | None = None) -> dict:
    profile = profile or {}
    features = profile.get("supported_features") or {}
    verified = profile.get("verified") or {}
    cards = profile.get("cards") or [] if features.get("cards") else []
    # Nunca confundir fusões candidatas da investigação com receitas verificadas.
    fusions = profile.get("fusion_recipes") or [] if features.get("fusions") else []
    scan_dir = profile.get("scan_result_dir")
    scan = load_json(Path(scan_dir) / "relatorio.json", {}) if scan_dir else {}
    indexed = scan.get("arquivos_discos")
    if not isinstance(indexed, list):
        indexed = []
    art = art_diagnostic(profile)
    info = intelligence or {}
    return {
        "file_name": str(entry.get("file_name") or "")[:200],
        "sha256": str(entry.get("sha256") or "")[:64],
        "level": str(entry.get("level") or "desconhecido")[:80],
        "cards": len(cards),
        "opponents": len(profile.get("opponents") or []) if features.get("opponents") else 0,
        "drop_entries": len(profile.get("drops") or []) if features.get("drops") else 0,
        "effects": sum(bool(c.get("effect_text") and c.get("effect_source")) for c in cards),
        "fusions_verified": len(fusions),
        "art": art,
        "iso_files": len(indexed),
        "ai": str(info.get("ai") or "sem análise recente")[:80],
        "fusion_review":str((profile.get("fusion_review") or {}).get("status")
                             or "sem banco importado")[:120],
        "effect_scan":str((info.get("effects_audit") or {}).get("status")
                           or "sem auditoria recente")[:100],
        "verified": {k: str(verified.get(k, "não informado"))[:100]
                     for k in ("cartas", "oponentes", "tabelas_drops", "fusoes",
                               "efeitos", "artes")},
    }


def format_diagnostic(item: dict) -> str:
    art = item["art"]
    if art["state"] == "não solicitada":
        art_line = "não solicitadas neste relatório"
    elif art["state"] == "sem registro":
        art_line = "nenhuma tentativa de extração registrada"
    elif art["count"] is None:
        art_line = "extração sem contagem"
    else:
        art_line = f"{art['count']}/{art['expected']} imagens exportadas ({art['state']})"
    lines = [
        "DUELTRACE · DIAGNÓSTICO LOCAL DO MOD",
        f"Arquivo: {item['file_name']}",
        f"SHA-256: {item['sha256']}",
        f"Reconhecimento: {item['level']}",
        f"Arquivos indexados no disco: {item['iso_files']}",
        f"Cartas disponíveis: {item['cards']}",
        f"Oponentes disponíveis: {item['opponents']}",
        f"Entradas de drops extraídas: {item['drop_entries']}",
        f"Efeitos com fonte: {item['effects']}",
        f"Fusões disponibilizadas: {item['fusions_verified']}",
        f"Artes: {art_line}",
    ]
    if art["description"]:
        lines.append(f"Diagnóstico de artes: {art['description']}")
    lines.extend([
        f"Ollama: {item['ai']} (hipóteses não validam tabelas)",
        f"Origem das fusões: {item['fusion_review']}",
        f"Auditoria de efeitos: {item['effect_scan']}",
        "Fusões estruturais podem ser usadas no assistente, mas não",
        "representam testes individuais realizados no ePSXe.",
        "",
        "Critérios do scanner:",
    ])
    for key, value in item["verified"].items():
        lines.append(f"  {key}: {value}")
    lines.extend(["", "As tabelas candidatas de fusão não são contadas como fusões verificadas.",
                  "Não modifique a ISO nem dados do jogo com base em hipóteses."])
    return "\n".join(lines)
