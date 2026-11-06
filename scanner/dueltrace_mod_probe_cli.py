#!/usr/bin/env python3
"""Local read-only multi-mod structure audit; emits no game content.

Usage (from repository root):
  python scanner/dueltrace_mod_probe_cli.py --iso "your-mod.iso" --output audit.json

This evidence probe cannot activate ranks/drops or confirm in-game IDs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from dueltrace_window_observation import correlate_observed_duels

from dueltrace_mod_family_probe import (
    MAX_BLOB_BYTES, DEFAULT_LAYOUTS, discover_weight_families,
)

MAX_RESOURCES = 4
MAX_TOTAL_RESOURCE_BYTES = 128 * 1024 * 1024
MAX_ISO_BYTES = 1_000_000_000
MIN_RESOURCE_BYTES = 225 * 1024
CLASSIC_RESOURCE_SIZE = 38_148_608


def ordered_resources(files: dict) -> list[tuple[str,int]]:
    """Identify resource candidates by bounded size/suffix, not mod name."""
    found = []
    for name, pair in files.items():
        if not isinstance(name,str) or not isinstance(pair,tuple) or len(pair)!=2:
            continue
        if type(pair[1]) is not int or not MIN_RESOURCE_BYTES<=pair[1]<=MAX_BLOB_BYTES:
            continue
        basename = name.rsplit('/',1)[-1].upper()
        if basename.endswith(('.EXE','.223','.CNF')):
            continue
        size=pair[1]
        priority=(0 if size==CLASSIC_RESOURCE_SIZE else
                  1 if basename.endswith('.MRG') else
                  2 if size>=4*1024*1024 else 3)
        found.append((priority,-size,name,size))
    found.sort()
    return [(name,size) for _,_,name,size in found]


def audit_disc(disc, *, layouts=DEFAULT_LAYOUTS) -> dict:
    """Audit a Disc-like reader; testable with synthetic in-memory media."""
    inventory = ordered_resources(disc.files)
    result = {"schema":1,"format":"dueltrace_mod_family_audit_v15",
              "status":"no_supported_matrix_family",
              "resourcesConsidered":len(inventory),
              "resourcesScanned":[],"resourceScanBudgetBytes":MAX_TOTAL_RESOURCE_BYTES,
              "modIdentityVerified":False,"rankLabelsVerified":False,
              "inGameVerified":False,"mayActivateDrops":False,
              "mayActivateRank":False,"allModsSupported":False,
              "limitations":["MIPS execution/real opponent IDs not established",
                             "Three rank-group labels require game-specific evidence",
                             "Unknown compression/encoding needs a new adapter"]}
    total=0
    for name,size in inventory:
        if len(result['resourcesScanned'])>=MAX_RESOURCES or total+size>MAX_TOTAL_RESOURCE_BYTES:
            continue
        total+=size
        raw=disc.get(name)
        probe=discover_weight_families(raw,layout_hypotheses=layouts)
        # Do not include file contents, game text, card IDs, probabilities or paths.
        result['resourcesScanned'].append({
            "resource":name[:150],"size":size,
            "sha256Prefix":hashlib.sha256(raw).hexdigest()[:12],
            "weightFamily":probe})
    families = [item for item in result['resourcesScanned']
                if item['weightFamily']['candidateCount'] > 0]
    result['resourcesWithFamily'] = len(families)
    if len(families)==1:
        report = families[0]['weightFamily']
        if report['state'] == 'unique_structural_candidate':
            result['status'] = 'unique_structural_resource_unverified'
        elif report['state'] == 'single_family_unmapped_windows':
            result['status'] = 'family_found_runtime_mapping_pending'
        else:
            result['status'] = 'ambiguous_family_unverified'
    elif len(families)>1:
        result['status'] = 'multiple_resources_with_candidate_families'
    result['resourceBytesScanned'] = total
    return result


def audit_iso(path: Path, *, layouts=DEFAULT_LAYOUTS) -> dict:
    # Disc is the existing bounded, ISO9660-aware scanner and does not
    # execute embedded code. Do not build a parallel ISO parser.
    from scanner_multiiso import Disc, inspect_system_cnf
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=MAX_ISO_BYTES:
        raise ValueError('Imagem inexistente, link ou acima do limite de 1 GB')
    disc=Disc(path)
    try:
        report=audit_disc(disc,layouts=layouts)
        boot=inspect_system_cnf(disc)
        report['geometry']=disc.geometry
        report['bootRecognized']=bool(boot.get('boot_target') and
                                      boot['boot_target'] in disc.files)
        return report
    finally:
        disc.close()


def atomic_write_json(path: Path, report: dict) -> None:
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.dueltrace-audit-',suffix='.json',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as handle:
            json.dump(report,handle,indent=2,ensure_ascii=False)
            handle.write('\n')
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)



def correlate_iso_duels(image: Path, duel_file: Path, audit: dict) -> dict:
    """Correlate private SHA-bound observations; export summary counters only."""
    duel_file = Path(duel_file)
    if (duel_file.is_symlink() or not duel_file.is_file()
            or duel_file.stat().st_size > 64 * 1024):
        raise ValueError("Observacoes ausentes, link ou arquivo acima do limite")
    observations = json.loads(duel_file.read_text(encoding="utf-8"))
    if (not isinstance(observations, dict)
            or observations.get("schema") != 1
            or not isinstance(observations.get("observations"), list)):
        raise ValueError("Manifesto de observacoes invalido")
    digest = hashlib.sha256()
    with Path(image).open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    if observations.get("rom_sha256") != digest.hexdigest():
        raise ValueError("Observacoes pertencem a outra ISO")
    candidates = [row for row in audit.get("resourcesScanned", [])
                  if isinstance(row, dict)
                  and isinstance(row.get("weightFamily"), dict)
                  and row["weightFamily"].get("candidateCount", 0) > 0]
    if len(candidates) != 1:
        return {"status": "resource_ambiguous_or_missing",
                "mayActivateDrops": False, "mayActivateRank": False}
    from scanner_multiiso import Disc
    disc = Disc(Path(image))
    try:
        name = candidates[0]["resource"]
        if name not in disc.files:
            raise ValueError("Recurso nao identificado nesta ISO")
        return correlate_observed_duels(
            disc.get(name), candidates[0]["weightFamily"],
            observations["observations"])
    finally:
        disc.close()


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iso',type=Path,required=True,
                        help='Imagem ISO/BIN local, apenas leitura')
    parser.add_argument('--output',type=Path,
                        help='Salva diagnóstico JSON sanitizado')
    parser.add_argument('--duel-observations',type=Path,
                        help='Observacoes independentes em JSON, atreladas ao SHA da ISO')
    parser.add_argument('--opponent-step',type=lambda x:int(x,0),
                        help='Hipótese adicional de passo entre blocos')
    parser.add_argument('--matrix-stride',type=lambda x:int(x,0),
                        help='Hipótese adicional de passo entre matrizes')
    args=parser.parse_args(argv)
    if (args.opponent_step is None)!=(args.matrix_stride is None):
        parser.error('Use --opponent-step junto com --matrix-stride')
    if args.output and args.iso.resolve()==args.output.resolve():
        parser.error('A saída não pode substituir a ISO')
    if (args.output and args.duel_observations and
            args.output.resolve()==args.duel_observations.resolve()):
        parser.error('A saida nao pode substituir o arquivo de observacoes')
    layouts=tuple(DEFAULT_LAYOUTS)
    if args.opponent_step is not None:
        layouts=layouts+((args.opponent_step,args.matrix_stride),)
    result=audit_iso(args.iso,layouts=layouts)
    if args.duel_observations:
        result['duelWindowCorrelation'] = correlate_iso_duels(
            args.iso,args.duel_observations,result)
    if args.output:
        atomic_write_json(args.output,result)
        print('Diagnóstico estrutural salvo:',args.output)
    else:
        print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['resourcesWithFamily'] else 2


if __name__=='__main__':
    raise SystemExit(main())