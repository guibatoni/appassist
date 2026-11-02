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
    weights_ok = (len(checks) == 117 and all(
        integer(r.get("peso_total")) == 2048 for r in checks
    ) and len(drops) > 0)

    groups = []
    if weights_ok:
        for r in checks:
            rank = r.get("rank", "")
            if rank and rank not in groups:
                groups.append(rank)

    status = {
        "cartas": "verificado" if card_ok else "pendente",
        "oponentes": "verificado" if opponent_ok else "pendente",
        "tabelas_drops": "verificado" if weights_ok else "pendente",
        "nomes_dos_ranks": "verificado" if known_x15 else "não_identificado",
        "regras_de_pontuacao": "verificado_x15" if known_x15 else "não_extraídas",
        "fusoes": "não_extraídas",
        "artes": "extraídas" if result.get("artes_extraidas") == 722 else "indisponíveis",
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
            "ranks": known_x15, "scoring": known_x15, "fusions": False,
            "art": result.get("artes_extraidas") == 722,
        },
        "rank_labels": LABELS_X15 if known_x15 else None,
        "drop_group_labels": groups if weights_ok else [],
        "art_root": str((extracted / "artes_722").resolve()) if status["artes"] == "extraídas" else None,
        "cards": [
            {"id": integer(r["id"]), "name": r["nome"],
             "atk": integer(r["atk"]), "def": integer(r["def"]),
             "type_id": integer(r.get("tipo"))}
            for r in cards
        ] if card_ok else [],
        "opponents": [
            {"id": integer(r["id"]), "name": r["nome"]} for r in opponents
        ] if opponent_ok else [],
        "drops": [
            {"opponent_id": integer(r["oponente_id"]), "group": r["rank"],
             "card_id": integer(r["carta_id"]), "weight": integer(r["peso"]),
             "probability_percent": float(r["chance_percentual"])}
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
            "Drops foram validados apenas como grupos brutos quando o rank não é conhecido.",
            "Fusões não são herdadas de outros mods nem presumidas iguais.",
            "Imagem original nunca é alterada; as artes permanecem em pasta local.",
        ],
    }
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


def import_rom(path: Path, output: Path, art: bool = False):
    # Scanner padrão mantém o arquivo de entrada em modo somente leitura.
    fingerprint = sha256(path)
    tmp = output / "analises"
    result = process(path, tmp, art)
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in path.stem)[:42]
    extracted = tmp / (safe_name + "_" + fingerprint[:10])
    if not extracted.exists():
        raise RuntimeError("O scanner não encontrou a pasta correspondente ao SHA esperado.")
    p = analyse(extracted, result, path)
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
