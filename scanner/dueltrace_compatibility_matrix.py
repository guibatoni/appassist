"""Matriz local, compacta e auditável de compatibilidade entre mods.

Não envia ROMs, binários, caminhos absolutos, dados da RAM ou nomes de
usuários. As funcionalidades são baseadas apenas no perfil da ISO com SHA
compatível. Evidência estrutural nunca equivale a execução verificada.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from auto_mods import ModCatalog, atomic_json
from mod_autopilot import ModAutopilot

FEATURES=("cards","opponents","drops","fusions","art","thumbnails",
          "descriptions","effects","ranks","scoring")
MAX_MODS=128
MAX_REPORT_BYTES=4*1024*1024


def _scan_evidence(catalog,profile):
    root=(catalog.home/"analises").resolve()
    raw=profile.get("scan_result_dir")
    if not isinstance(raw,str) or not raw or len(raw)>4096:
        return {}
    try:
        directory=Path(raw).resolve(strict=True)
        if not directory.is_relative_to(root):
            return {}
        report=directory/"relatorio.json"
        if (not report.is_file() or report.is_symlink()
                or report.stat().st_size>MAX_REPORT_BYTES):
            return {}
        data=json.loads(report.read_text(encoding="utf-8"))
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError,UnicodeError,json.JSONDecodeError):
        return {}


def _short_status(value):
    # Estados podem conter textos livres no relatório de um mod. Exportar
    # apenas identificadores, nunca nomes de usuário/caminhos completos.
    raw=str(value or "nao_analisado")
    token=re.sub(r"[^a-zA-Z0-9_-]+","_",raw)[:64].strip("_")
    return token or "nao_analisado"


def build_compatibility_matrix(catalog:ModCatalog)->dict:
    """Extrai apenas contagens, estados e SHA para diagnóstico reproduzível."""
    output={"schema":1,
            "generatedAt":datetime.now(timezone.utc).isoformat(),
            "format":"dueltrace_multimod_compatibility",
            "modCount":0,"featureCoverage":{x:0 for x in FEATURES},
            "mods":[],"truncated":False,
            "inGameValidationClaimed":False,
            "privacy":"sem_ROM_binarios_caminhos_ou_RAM"}
    rows=catalog.list()
    output["truncated"]=len(rows)>MAX_MODS
    for entry in rows[:MAX_MODS]:
        if not isinstance(entry,dict):
            continue
        sha=entry.get("sha256")
        if not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{64}",sha):
            continue
        profile=catalog.profile_for(entry)
        if not isinstance(profile,dict) or profile.get("rom_sha256")!=sha:
            continue
        features=profile.get("supported_features")
        if not isinstance(features,dict):
            features={}
        flags={k:features.get(k) is True for k in FEATURES}
        for key,value in flags.items():
            output["featureCoverage"][key]+=int(value)
        scan=_scan_evidence(catalog,profile)
        names=scan.get("relocated_name_layouts") or {}
        attributes=scan.get("card_attribute_layouts") or {}
        resources=scan.get("wa_resource_selection") or {}
        drops=scan.get("drop_layout_discovery") or {}
        rank=scan.get("rank_analysis") or {}
        if not all(isinstance(x,dict) for x in (
                names,attributes,resources,drops,rank)):
            names=attributes=resources=drops=rank={}
        statuses={
            "image":_short_status(scan.get("status") or
                                  ("erro" if profile.get("scanner_error")
                                   else "relatorio_indisponivel")),
            "names":_short_status(names.get("state")),
            "attributes":_short_status(attributes.get("state")),
            "resources":_short_status(resources.get("state")),
            "drops":_short_status(drops.get("state")),
            "rankPoints":_short_status(rank.get("status")),
        }
        candidates={
            "nameLayouts":len(names.get("candidates",[]))
                if isinstance(names.get("candidates"),list) else 0,
            "attributeLayouts":len(attributes.get("links",[]))
                if isinstance(attributes.get("links"),list) else 0,
            "waResources":len(resources.get("candidates",[]))
                if isinstance(resources.get("candidates"),list) else 0,
            "dropLayouts":len(drops.get("candidates",[]))
                if isinstance(drops.get("candidates"),list) else 0,
        }
        item={"sha256":sha,"level":_short_status(entry.get("level")),
              "modeAvailable":"basic" if not profile.get("scanner_error")
                  and entry.get("level")=="desconhecido" else
                  "recognized" if not profile.get("scanner_error") else
                  "scan_error",
              "features":flags,"discovery":statuses,"candidates":candidates,
              "inGameVerified":False}
        output["mods"].append(item)
    output["modCount"]=len(output["mods"])
    return output


def main(argv=None):
    p=argparse.ArgumentParser(
        description="Matriz local do DUELTRACE, sem exportar ROMs ou arquivos privados")
    p.add_argument("--home",type=Path,help="Diretório de dados do DUELTRACE")
    p.add_argument("--folder",type=Path,help="Pasta com ISOs/BINs para analisar")
    p.add_argument("--recursive",action="store_true")
    p.add_argument("--output",type=Path,help="Arquivo JSON para o relatório")
    args=p.parse_args(argv)
    catalog=ModCatalog(args.home)
    if args.folder is not None:
        ModAutopilot(catalog).analyze_folder(args.folder,recursive=args.recursive)
    report=build_compatibility_matrix(catalog)
    dest=(args.output if args.output is not None
          else catalog.home/"diagnosticos"/"matriz_compatibilidade.json")
    dest=dest.expanduser().resolve()
    dest.parent.mkdir(parents=True,exist_ok=True)
    atomic_json(dest,report)
    print("ISOs analisadas:",report["modCount"])
    print("Relatório local:",dest)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
