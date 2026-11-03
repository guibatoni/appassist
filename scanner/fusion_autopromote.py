"""Importador automático de fusões diretamente de 7 bancos WA_MRG idênticos.

Não usa a opinião do Ollama e não diz que as receitas foram executadas no
ePSXe. Receitas são disponibilizadas com status de validação ESTRUTURAL.
Somente ISO cadastrada + arquivo não modificado + relatório assinado pelos
7 bancos + catálogo de 722 cartas podem liberar o banco completo.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from auto_mods import atomic_json, load_json, supported_for_runtime


def validate_structural_fusions(report: dict, *, sha256: str) -> tuple[list[dict], str]:
    """Rejeita bancos incompletos, divergentes, inconsistentes e resultados ambíguos."""
    if report.get("rom_sha256") != sha256:
        raise ValueError("Relatório pertence a outra ISO.")
    banks = report.get("banks")
    if not isinstance(banks, list) or len(banks) != 7:
        raise ValueError("É necessário comparar os sete bancos de fusões.")
    if (report.get("valid_banks") != 7 or report.get("matching_banks") != 7
            or report.get("divergent_banks") is not False
            or report.get("bank_conflicts") != 0):
        raise ValueError("Bancos incompletos, divergentes ou conflitantes.")
    fp = report.get("candidate_fingerprint")
    if not isinstance(fp, str) or len(fp) != 64:
        raise ValueError("Assinatura de receitas ausente.")
    if not all(row.get("status") == "decodificado"
               and row.get("recipelist_sha256") == fp
               and row.get("conflict_count") == 0
               for row in banks):
        raise ValueError("Bancos WA_MRG não possuem a mesma assinatura.")
    rows = report.get("candidates")
    if not isinstance(rows, list) or not 50 <= len(rows) <= 50000:
        raise ValueError("Quantidade suspeita de fusões.")
    recipes=set()
    symmetric={}
    for row in rows:
        if not isinstance(row,dict) or not all(type(row.get(k)) is int for k in ("a","b","result")):
            raise ValueError("Receita malformada.")
        a,b,r=(row[k] for k in ("a","b","result"))
        if not all(1 <= v <= 722 for v in (a,b,r)):
            raise ValueError("Receita com IDs fora de 1..722.")
        key=(min(a,b),max(a,b))
        if key in symmetric and symmetric[key] != r:
            raise ValueError("Fusões simétricas conflitantes.")
        symmetric[key]=r
        recipes.add((a,b,r))
    ordered=sorted(recipes)
    calculated=hashlib.sha256(json.dumps(ordered,separators=(",",":")).encode("ascii")).hexdigest()
    if calculated != fp or len(ordered) != report.get("candidate_count"):
        raise ValueError("Conteúdo não corresponde à assinatura dos bancos.")
    if any(row.get("unique_recipe_count") != len(ordered) for row in banks):
        raise ValueError("Contagem dos bancos não confere com a lista.")
    return ([{"a":a,"b":b,"result":r} for a,b,r in ordered], fp)


def import_structural_fusions(catalog, sha256: str) -> dict:
    """Atualiza o perfil local sem converter extrações em confirmação no jogo."""
    with catalog._lock:
        entries=catalog.list()
        entry=next((x for x in entries if x.get("sha256")==sha256),None)
        if not entry:
            raise ValueError("ISO não cadastrada.")
        profile=catalog.profile_for(entry)
        if not profile or profile.get("rom_sha256") != sha256:
            raise ValueError("Perfil incompatível.")
        if (profile.get("verified",{}).get("cartas") != "verificado"
                or len(profile.get("cards",[])) != 722):
            raise ValueError("Catálogo de 722 cartas ainda não validado.")
        src=Path(entry.get("source_path",""))
        if not src.is_file():
            raise ValueError("ISO original não encontrada.")
        stat=src.stat()
        if (stat.st_size != entry.get("size")
                or stat.st_mtime_ns != entry.get("mtime_ns")):
            raise ValueError("ISO modificada desde a extração.")
        pending=catalog.home/"investigacoes"/(sha256+".fusoes.json")
        report=load_json(pending,{})
        rows, fp=validate_structural_fusions(report,sha256=sha256)
        previous=profile.get("fusion_recipes",[])
        old_review=profile.get("fusion_review") or {}
        if (old_review.get("candidate_fingerprint")==fp
                and len(previous)==len(rows)
                and profile.get("supported_features",{}).get("fusions")):
            return {"status":"cache","count":len(rows),"fingerprint":fp}
        results={}
        for row in rows:
            key=tuple(sorted((row["a"],row["b"])))
            results[key]=row["result"]
        manual={}
        for row in previous:
            if row.get("validation") != "observada_manualmente_no_jogo":
                continue
            try:
                a,b,r=(int(row[k]) for k in ("a","b","result"))
            except (TypeError,ValueError,KeyError) as exc:
                raise ValueError("Confirmação manual inconsistente.") from exc
            key=tuple(sorted((a,b)))
            if results.get(key) != r:
                raise ValueError("Banco novo diverge de uma fusão confirmada no jogo.")
            manual[(a,b,r)]=True
        updated=dict(profile)
        updated["fusion_recipes"]=[
            {**row,
             "validation":("observada_manualmente_no_jogo"
                           if (row["a"],row["b"],row["result"]) in manual
                           else "extraida_sete_bancos_consistentes"),
             "fusion_candidate_fingerprint":fp}
            for row in rows
        ]
        updated["supported_features"]=dict(profile.get("supported_features",{}),fusions=True)
        updated["verified"]=dict(profile.get("verified",{}),
                                 fusoes="extraidas_sete_bancos_nao_testadas_no_jogo")
        updated["fusion_review"]={
            "status":"extraidas_estruturalmente_nao_testadas_no_jogo",
            "candidate_fingerprint":fp,
            "rom_sha256":sha256,
            "recipe_count":len(rows),
            "in_game_individually_verified":sum(
                r["validation"]=="observada_manualmente_no_jogo"
                for r in updated["fusion_recipes"]),
            "imported_at":datetime.now(timezone.utc).isoformat(),
        }
        profile_path=Path(entry["profile_path"])
        backup=profile_path.with_name("profile.json.bak.before_structural_fusions")
        if not backup.exists():
            shutil.copy2(profile_path,backup)
        atomic_json(profile_path,updated)
        entry["verified"]=updated["verified"]
        entry["features"]=supported_for_runtime(updated)
        atomic_json(catalog.registry_file,{"schema":1,"entries":entries})
        active=load_json(catalog.active_file,{})
        if active.get("sha256")==sha256:
            active["features"]=entry["features"]
            active["fusion_revision"]=int(active.get("fusion_revision",0))+1
            active["fusion_review_fingerprint"]=fp
            atomic_json(catalog.active_file,active)
        return {"status":"importadas","count":len(rows),"fingerprint":fp,
                "manual_count":updated["fusion_review"]["in_game_individually_verified"]}
