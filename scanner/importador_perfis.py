#!/usr/bin/env python3
"""Importador MultiMod local: extrai dados comprováveis de imagens de PS1.

Não modifica ISOs, não baixa ROMs nem presume que novos mods sejam X15.
Execute com Python 3.10+ na mesma pasta de scanner_multiiso.py.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from scanner_multiiso import process, sha256, X15_SHA
from card_catalog import enrich_cards, attach_effect_manifest, effect_sidecar_path, category_summary
from mod_effects_iso import extract_embedded_effects
from dueltrace_rank_profiles import rank_profile_for_image
from dueltrace_rank_system import CLASSIC_RANKS

SCHEMA = 1
LABELS_X15 = ["Z-POW", "S-POW", "S-TEC"]


def rows(path: Path):
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def integer(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def analyse(extracted: Path, result: dict, iso: Path) -> dict:
    cards = rows(extracted / "cartas.csv")
    opponents = rows(extracted / "oponentes.csv")
    drops = rows(extracted / "drops_por_oponente.csv")
    decks = rows(extracted / "decks.csv")
    checks = rows(extracted / "validacao_pesos.csv")
    known_x15 = result["sha256"].lower() == X15_SHA.lower()

    ids = [integer(r.get("id")) for r in cards]
    opp_ids = [integer(r.get("id")) for r in opponents]
    card_ok = len(cards) == 722 and ids == list(range(1, 723)) and all(
        r.get("nome", "").strip() and integer(r.get("atk")) is not None
        and integer(r.get("def")) is not None for r in cards
    )
    opponent_ok = len(opponents) == 39 and opp_ids == list(range(1, 40)) and all(
        r.get("nome", "").strip() for r in opponents
    )
    # O formato das matrizes pode ser estruturalmente coerente mesmo quando
    # as cartas e os oponentes da ISO ainda não foram identificados.
    # Não expor esses IDs como drops confiáveis para o cliente: IDs e nomes
    # podem ter sido remapeados e os grupos de RANK podem ter outra ordem.
    weights_structural_ok = (len(checks) == 117 and all(
        integer(r.get("peso_total")) == 2048 for r in checks
    ) and len(drops) > 0)
    weights_ok = weights_structural_ok and card_ok and opponent_ok

    # Códigos de tipo extraídos do executável; não inferimos por nome.
    # Textos de efeito são opcionais e externos quando o mod os fornece.
    catalog = enrich_cards([
        {"id": integer(r["id"]), "name": r["nome"],
         "atk": integer(r["atk"]), "def": integer(r["def"]),
         "type_id": integer(r.get("tipo")),
         "level": integer(r.get("nivel")),
         "attribute_id": integer(r.get("atributo")),
         "guardian_star_1": integer(r.get("estrela_1")),
         "guardian_star_2": integer(r.get("estrela_2"))}
        for r in cards
    ], known_fm_layout=True) if card_ok else []
    from fm_card_text import attach_descriptions
    candidate_descriptions={
        integer(row.get("id")):{"text":row["descricao"],"source":row["descricao_fonte"]}
        for row in cards if row.get("descricao") and row.get("descricao_fonte")
    }
    catalog,description_info=attach_descriptions(catalog,candidate_descriptions)
    effects_info = {"status": "nao_identificados", "count": 0, "sources": [],
                    "effects_executed_in_game_verified": False}
    if description_info["effect_descriptions_attached"]:
        effects_info["sources"].append({
            "status":"slus_card_text",
            "count":description_info["effect_descriptions_attached"],
            "source":result.get("executavel"),
            "effects_executed_in_game_verified":False})
    effect_warnings=[]
    if card_ok:
        # A primeira fonte é o próprio ISO, APENAS quando traz um arquivo
        # estruturado e reconhecível. Não varrer textos binários às cegas.
        if result.get("executavel") and result.get("wa_prefix_bytes"):
            try:
                catalog, embedded=extract_embedded_effects(
                    iso,catalog,rom_sha256=result["sha256"])
                if embedded["count"]:
                    effects_info["sources"].append(embedded)
            except (OSError,ValueError,UnicodeError) as exc:
                effect_warnings.append("Metadados embutidos ignorados: "+str(exc)[:220])
        sidecar=effect_sidecar_path(iso)
        if sidecar.is_file():
            try:
                catalog, external=attach_effect_manifest(
                    catalog,sidecar,rom_sha256=result["sha256"])
                if external["count"]:
                    effects_info["sources"].append(external)
            except (OSError,ValueError,UnicodeError) as exc:
                effect_warnings.append("Manifesto local ignorado: "+str(exc)[:220])
        effects_info["count"]=sum(bool(c.get("effect_text")) for c in catalog)
        if effects_info["count"]:
            effects_info["status"]="texto_declarado_com_procedencia_nao_validado_no_jogo"


    groups = []
    if weights_ok:
        for r in checks:
            rank = r.get("rank", "")
            if rank and rank not in groups:
                groups.append(rank)

    status = {
        "cartas": "verificado" if card_ok else "pendente",
        "oponentes": "verificado" if opponent_ok else "pendente",
        "tabelas_drops": (
            "verificado_estruturalmente" if weights_ok else
            "matrizes_candidatas_sem_identidade" if weights_structural_ok else
            "pendente"),
        "nomes_dos_ranks": "verificado" if known_x15 else "padrao_original_presumido",
        "regras_de_pontuacao": "verificado_x15" if known_x15 else "não_extraídas",
        "fusoes": "não_extraídas",
        "artes": "extraídas" if result.get("artes_extraidas") == 722 else "indisponíveis",
        "categorias": "codigo_fm_padrao" if card_ok else "nao_identificadas",
        "efeitos": effects_info["status"],
        "descricoes":"texto_slus_extraido" if description_info["descriptions_attached"] else "não_identificadas",
        "molduras":"extraidas_do_WA" if result.get("molduras_extraidas")==6 else "indisponiveis",
    }

    payload = {
        "schema": SCHEMA,
        "name": "Remaster X15 1.2.1" if known_x15 else "Mod local — " + iso.stem,
        "rom_sha256": result["sha256"],
        "exe_sha256": result.get("hash_executavel"),
        "wa_sha256": result.get("hash_wa"),
        "source": "ISO/BIN fornecida pelo usuário; extração estritamente local",
        "verified": status,
        "supported_features": {
            "cards": card_ok, "opponents": opponent_ok, "drops": weights_ok,
            "ranks": bool(weights_ok), "scoring": known_x15, "fusions": False,
            "art": result.get("artes_extraidas") == 722,
            "thumbnails": result.get("miniaturas_extraidas") == 722,
            "card_frames": result.get("molduras_extraidas") == 6,
            "composed_cards": result.get("cartas_com_moldura") == 722,
            "descriptions": description_info["descriptions_attached"] > 0,
            "categories": card_ok,
            "effects": effects_info["count"] > 0,
        },
        "rank_labels": LABELS_X15 if known_x15 else list(CLASSIC_RANKS),
        "rank_system":("x15" if known_x15 else "classic"),
        "rank_system_verification":("sha_x15_confirmado" if known_x15
                                    else "layout_original_presumido"),
        "rank_points": rank_profile_for_image(result["sha256"],result.get("rank_analysis")),
        "rank_mips_evidence": result.get("rank_mips_evidence", {
            "status":"not_scanned","rank_routine_confirmed":False,"candidates":[]}),
        "drops_provenance": {"source": result.get("drops_source") or "DATA/WA_MRG.MRG",
                             "opponent_names_source": result.get("executavel"),
                             "table_count": len(checks) if weights_ok else 0,
                             "weight_total": 2048 if weights_ok else None,
                             "rank_label_verified": bool(known_x15 and weights_ok),
                             "candidate_table_count": len(checks) if weights_structural_ok else 0,
                             "candidate_entry_count": len(drops) if weights_structural_ok else 0,
                             "candidate_weight_total": 2048 if weights_structural_ok else None,
                             "candidate_status": (
                                 "nao_verificados_sem_cartas_e_oponentes"
                                 if weights_structural_ok and not weights_ok else
                                 "associados_catalogo" if weights_ok else
                                 "estrutura_nao_reconhecida"),
                             "labels_unknown": not known_x15,
                             "in_game_verified":False},
        "drop_group_labels": groups if weights_ok else [],
        "art_root": str((extracted / "artes_722").resolve()) if status["artes"] == "extraídas" else None,
        "cards": catalog,
        "category_counts": category_summary(catalog),
        "effects_provenance": effects_info,
        "descriptions_provenance": {
            **description_info,
            "slus_report":result.get("descricoes_slus",{}),
            "source":result.get("executavel")},
        "graphic_assets": {
            "art_count":result.get("artes_extraidas",0),
            "thumbnails":result.get("miniaturas_extraidas",0),
            "frames":result.get("molduras_extraidas",0),
            "composed_cards":result.get("cartas_com_moldura",0),
            "manifest":"recursos_wa.json" if result.get("miniaturas_extraidas") else None},
        "opponents": [
            {"id": integer(r["id"]), "name": r["nome"]} for r in opponents
        ] if opponent_ok else [],
        "drops": [
            {"opponent_id": integer(r["oponente_id"]), "group": r["rank"],
             "card_id": integer(r["carta_id"]), "weight": integer(r["peso"]),
             "probability_percent": float(r["chance_percentual"]),
             "source_offset": integer(r.get("source_offset"))}
            for r in drops
        ] if weights_ok else [],
        "decks": [
            {"opponent_id": integer(r["oponente_id"]), "card_id": integer(r["carta_id"]),
             "weight": integer(r["peso"])}
            for r in decks
        ] if opponent_ok else [],
        "fusion_recipes": [],
        "notes": [
            "IDs do mesmo jogo podem ter nomes diferentes em outros mods.",
            "As tabelas de drops podem ter pesos coerentes, mas não identificam cartas ou oponentes por si só.",
            "Grupos de RANK e resultados reais precisam ser confirmados na ISO ativa.",
            "Fusões não são herdadas de outros mods nem presumidas iguais.",
            "Imagem original nunca é alterada; as artes permanecem em pasta local.",
        ],
    }
    for warning in effect_warnings:
        payload["notes"].append(warning)
    if weights_structural_ok and not weights_ok:
        payload["notes"].append(
            f"{len(checks)} matrizes e {len(drops)} entradas de drops candidatas "
            "foram decodificadas; catálogo de cartas/oponentes não verificado. "
            "Dados provisórios não disponíveis para uso em Drops ou RANK.")
    if effects_info["count"]:
        payload["notes"].append("Textos de efeitos extraídos de fonte declarada no ISO ou manifesto vinculado ao SHA; sua execução no jogo NÃO foi confirmada.")
    if not all([card_ok, opponent_ok, weights_ok]):
        payload["notes"].append("Perfil incompleto: informações ausentes NÃO são inferidas.")
    return payload


def diff_profiles(a: dict, b: dict) -> dict:
    def mapping(p, key, value):
        return {int(x["id"]): x[value] for x in p.get(key, [])}
    ca, cb = mapping(a, "cards", "name"), mapping(b, "cards", "name")
    oa, ob = mapping(a, "opponents", "name"), mapping(b, "opponents", "name")
    diff = {
        "a": a["rom_sha256"], "b": b["rom_sha256"],
        "cards_renamed": [
            {"id": n, "a": ca[n], "b": cb[n]}
            for n in sorted(ca.keys() & cb.keys()) if ca[n] != cb[n]
        ],
        "opponents_renamed": [
            {"id": n, "a": oa[n], "b": ob[n]}
            for n in sorted(oa.keys() & ob.keys()) if oa[n] != ob[n]
        ],
    }
    for key, label in (("drops", "drop_entries"), ("decks", "deck_entries")):
        diff[label] = {"a": len(a.get(key, [])), "b": len(b.get(key, []))}
    return diff


def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(path)


def import_rom(path: Path, output: Path, art: bool = False, progress=None):
    # Hash uma única vez; processamento reutiliza a assinatura calculada.
    fingerprint = sha256(path, progress=progress)
    tmp = output / "analises"
    result = process(path, tmp, art, digest=fingerprint, progress=progress)
    # Caminho canônico fornecido pelo scanner. Não reconstruir com outra
    # normalização de nomes: espaços, pontos, acentos e colchetes divergem.
    raw_extracted = result.get("resultado_dir")
    if not raw_extracted:
        raise RuntimeError("O scanner não informou o destino dos resultados.")
    extracted = Path(raw_extracted).resolve()
    if not extracted.is_relative_to(tmp.resolve()):
        raise RuntimeError("O scanner retornou uma pasta fora do diretório de análise.")
    report_file = extracted / "relatorio.json"
    if not report_file.is_file():
        raise RuntimeError("Relatório não encontrado na pasta devolvida pelo scanner.")
    saved_result = json.loads(report_file.read_text(encoding="utf-8"))
    if saved_result.get("sha256") != fingerprint or saved_result.get("arquivo") != path.name:
        raise RuntimeError("A pasta de análise não corresponde à imagem selecionada.")
    # Se a extração falhou, manter o diagnóstico e criar perfil sem tabelas.
    # Nunca reutilizar nomes/drops de uma tentativa antiga.
    p = analyse(extracted, result, path)
    if result.get("status") == "erro/estrutura incompatível":
        p["notes"].append("Falha na leitura da ROM: " + str(result.get("problema","erro sem detalhes")))
        p["scanner_error"] = str(result.get("problema","erro sem detalhes"))
    p["scan_result_dir"] = str(extracted)
    profile_path = output / "profiles" / fingerprint[:16] / "profile.json"
    save_json(profile_path, p)
    return p, profile_path


def main():
    cli = argparse.ArgumentParser(description="Criar perfis MultiMod sem inventar tabelas")
    cli.add_argument("roms", nargs="+", type=Path, help="Imagens .bin/.iso possuídas pelo usuário")
    cli.add_argument("--output", type=Path, default=Path("meus_perfis"))
    cli.add_argument("--artes", action="store_true", help="Extrair imagens com Pillow")
    args = cli.parse_args()
    profiles = []
    for rom in args.roms:
        if not rom.is_file() or rom.suffix.lower() not in (".iso", ".bin"):
            print("Ignorado:", rom, "(arquivo inexistente ou extensão inválida)")
            continue
        print("Analisando", rom.name, flush=True)
        try:
            p, location = import_rom(rom, args.output, args.artes)
            profiles.append(p)
            print("Perfil:", location)
            print("Estado:", p["verified"])
        except Exception as e:
            print("Falha na análise de", rom.name, ":", e)
    for i in range(len(profiles)):
        for j in range(i + 1, len(profiles)):
            d = diff_profiles(profiles[i], profiles[j])
            save_json(args.output / "comparacoes" /
                      (profiles[i]["rom_sha256"][:12] + "_vs_" +
                       profiles[j]["rom_sha256"][:12] + ".json"), d)
    if profiles:
        save_json(args.output / "index.json", [{
            "name": p["name"], "sha256": p["rom_sha256"],
            "verified": p["verified"]
        } for p in profiles])
    print("Concluído:", len(profiles), "imagem(ns)")


if __name__ == "__main__":
    main()
