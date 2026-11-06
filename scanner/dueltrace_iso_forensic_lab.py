"""DUELTRACE ISO Forensic Lab — opt-in, read-only, source-bound inspection.

This probe never changes a ROM, profile, active mod, or gameplay feature.
No ISO bytes, filenames, card names, fusion recipes, paths, PID, or RAM are
returned to the UI; only reproducible structural evidence/counters.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import stat as stat_module

from scanner_multiiso import (
    Disc, sha256, decode_names, decode_drops,
    SLUS_PTR_BASE, SLUS_TEXT_BASE, SLUS_GLYPHS, WA_OPP_BASE,
    WA_OPP_STEP, WA_RANK_STRIDE, CARD_COUNT, OPP_COUNT,
    select_known_executable_layout, inspect_system_cnf,
)
from dueltrace_exe_sector_padding import load_executable_sector_padding
from dueltrace_independent_opponents import discover_independent_opponents
from dueltrace_mod_family_probe import discover_weight_families
from dueltrace_full_resource_drop_bridge import use_unique_weight_family
from fm_rank_mips_evidence import inspect_mips_rank_routines
from extrator_fusoes import analyze_fusion_banks, select_fusion_resource

SHA64 = re.compile(r"^[a-f0-9]{64}$")
MAX_ROM_BYTES = 2 * 1024 * 1024 * 1024
MAX_WA_BYTES = 96 * 1024 * 1024


class IsoForensicError(ValueError):
    """Expected, user-facing diagnostic error without local paths."""


def _snapshot(path: Path) -> tuple[int, int, int, int]:
    st = path.stat()
    if (not stat_module.S_ISREG(st.st_mode)
            or not 2048 <= st.st_size <= MAX_ROM_BYTES):
        raise IsoForensicError("Imagem fora dos limites de leitura segura.")
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns


def _candidate_exes(disc) -> list[str]:
    indexed=[]
    for name, (_, size) in disc.files.items():
        if 2048 <= size <= 8 * 1024 * 1024:
            try:
                if disc.get(name, limit_bytes=8).startswith(b"PS-X EXE"):
                    indexed.append(name)
            except (ValueError, OSError, KeyError):
                continue
    cnf=inspect_system_cnf(disc)
    boot=cnf.get("boot_target")
    return sorted(indexed, key=lambda n:(n!=boot, n.rsplit("/",1)[-1]!="SLUS_014.11",n))


def _resource(disc):
    exact=[name for name in disc.files
           if name.rsplit("/",1)[-1].upper()=="WA_MRG.MRG"]
    if len(exact)==1:
        name=exact[0]
        size=disc.files[name][1]
        if not 0 < size <= MAX_WA_BYTES:
            return None, "resource_outside_budget"
        return name,"unique_canonical_resource"
    if len(exact)>1:
        return None, "multiple_canonical_resources"
    # Content-based fallback: seven conflict-free identical fusion banks,
    # never an arbitrary file selected by size or extension alone.
    try:
        name,method=select_fusion_resource(disc)
        return name,"seven_bank_structural_resource" if method!=(
            "canonical_name") else "unique_canonical_resource"
    except (OSError,ValueError,KeyError,OverflowError):
        return None,"resource_name_or_structure_unknown"


def _art_integrity(wa: bytes) -> dict:
    """Check *every* card and duplicated thumbnail, without writing PNGs."""
    try:
        from fm_deep_assets import _large, _small, _has_detail
        from PIL import Image  # noqa: F401 — availability gate
    except ImportError:
        return {"state":"pillow_unavailable","large":0,"thumbnails":0,
                "duplicateDifferences":0,"checked":0}
    good_large=good_small=duplicates=0
    checked=0
    for cid in range(1, CARD_COUNT+1):
        checked+=1
        try:
            art,_ = _large(wa,cid)
            thumb, matches,_ = _small(wa,cid)
            good_large+=int(_has_detail(art))
            good_small+=int(_has_detail(thumb))
            duplicates+=int(not matches)
        except (OSError,ValueError,IndexError):
            continue
    return {
        "state":"complete" if good_large==good_small==CARD_COUNT else "partial",
        "large":good_large,"thumbnails":good_small,
        "duplicateDifferences":duplicates,"checked":checked,
    }


def _safe_fusions(iso:Path,stamp:tuple[int,int,int,int]) -> dict:
    try:
        f=analyze_fusion_banks(iso,expected_size=stamp[2],
                               expected_mtime_ns=stamp[3])
    except (OSError,ValueError,RuntimeError,OverflowError):
        return {"state":"unknown_layout","validBanks":0,"matchingBanks":0,
                "recipes":0,"conflictingPairs":0,
                "unambiguousPairs":0,"mayActivate":False}
    valid=int(f.get("valid_banks") or 0)
    matching=int(f.get("matching_banks") or 0)
    conflicted=int(f.get("unordered_pairs_with_conflicting_results") or 0)
    count=int(f.get("candidate_count") or 0)
    return {
        "state":("seven_consistent_conflicts_quarantined"
                 if valid==matching==7 and conflicted else
                 "seven_consistent_unverified" if valid==matching==7 and not
                 f.get("divergent_banks") and f.get("bank_conflicts")==0 else
                 "partial_or_divergent"),
        "validBanks":valid,"matchingBanks":matching,"recipes":count,
        "conflictingPairs":conflicted,
        "unambiguousPairs":int(f.get("unique_unordered_pairs_without_conflict") or 0),
        "resourceMethod":("canonical" if f.get("resource_selection_method")=="canonical_name"
                          else "structural_candidate"),
        "mayActivate":False,
    }


def inspect_iso(path: Path, expected_sha: str) -> dict:
    """Re-open ISO and independently re-evaluate each stage on exact SHA.

    Caller must restrict path to a registered, user-selected image.
    """
    if (type(expected_sha) is not str or
            not SHA64.fullmatch(expected_sha)):
        raise IsoForensicError("Identificador SHA-256 inválido.")
    path=Path(path).resolve(strict=True)
    stamp=_snapshot(path)
    if sha256(path)!=expected_sha:
        raise IsoForensicError("SHA da imagem não corresponde ao mod cadastrado.")
    disc=None
    try:
        disc=Disc(path)
        exes=_candidate_exes(disc)
        executable={"state":"not_found","coherent":False,
                    "physicalPaddingVerified":False}
        cards={"state":"not_found","count":0}
        opponents={"state":"not_found","count":0,"namesStructural":0,
                   "affineLengthException":False,
                   "inGameIdentityVerified":False}
        rank={"state":"not_found","staticCandidates":0,
              "executionConfirmed":False}
        selected=None
        if exes:
            selected,sl,decoded_opps,decoded_cards,_message,attempts=(
                select_known_executable_layout(disc,exes))
            exe_meta=next((a for a in attempts if a.get("name")==selected),{})
            executable={
                "state":"structural_psx_exe" if sl.startswith(b"PS-X EXE") else "unrecognized",
                "coherent": bool(exe_meta.get("executableSectorPadding",{}).get(
                    "headerCoherent")),
                "physicalPaddingVerified": bool(
                    exe_meta.get("executableSectorPadding",{}).get("state")==
                    "padding_zero_verificado"),
                "candidatesTried":len(attempts),
            }
            cards={"state":"complete_722" if len(decoded_cards)==722
                   else "partial_or_unknown", "count":len(decoded_cards)}
            opponents={
                "state":"classic_name_table" if len(decoded_opps)==39 else "not_found",
                "count":len(decoded_opps),"namesStructural":len(decoded_opps),
                "affineLengthException":False,"inGameIdentityVerified":False,
            }
            if len(decoded_opps)!=39:
                indirect=discover_independent_opponents(
                    sl,pointer_base=SLUS_PTR_BASE,
                    text_base=SLUS_TEXT_BASE,glyph_base=SLUS_GLYPHS,
                    rom_sha256=expected_sha)
                selected_names=indirect.get("selected")
                if isinstance(selected_names,dict):
                    names=selected_names.get("opponents",[])
                    opponents["count"]=len(names)
                    opponents["namesStructural"]=len(names)
                    opponents["state"]="independent_structural_39"
                    opponents["affineLengthException"]=bool(
                        selected_names.get("lengthFieldAnomaly"))
                else:
                    opponents["state"]="unmapped_candidates"
            ranked=inspect_mips_rank_routines(sl)
            rank={"state":str(ranked.get("status") or "unknown")[:80],
                  "staticCandidates":int(ranked.get("candidate_count") or 0),
                  "executionConfirmed":False}
        resource_name,selection=_resource(disc)
        family={"state":"not_found","matrixCount":0,
                "distinct39Windows":0,"ambiguous":False,
                "base":None,"opponentStep":None,"matrixStride":None,
                "distributionEncoding":None,
                "opponentMappingVerified":False,
                "rankGroupLabelsVerified":False,
                "mayActivateDrops":False}
        drops={"state":"not_found","validatedStructuralMatrices":0,
               "labelsVerified":False,"opponentMappingVerified":False}
        images={"state":"not_scanned","large":0,"thumbnails":0,
                "duplicateDifferences":0,"checked":0}
        wa_bytes=0
        if resource_name is not None:
            wa=disc.get(resource_name)
            wa_bytes=len(wa)
            images=_art_integrity(wa)
            evidence=discover_weight_families(wa)
            clusters=evidence.get("clusters",[])
            windows=max((int(x.get("possible39BlockWindows") or 0)
                         for x in clusters if isinstance(x,dict)),default=0)
            full=evidence.get("selected")
            if not isinstance(full,dict) and len(evidence.get("candidates",[]))==1:
                full=evidence["candidates"][0]
            family={
                "state":str(evidence.get("state") or "not_found")[:80],
                "matrixCount":max((int(x.get("matrixCount") or 0)
                                   for x in evidence.get("candidates",[])
                                   if isinstance(x,dict)),default=0),
                "distinct39Windows":windows,
                "ambiguous": bool(evidence.get("ambiguous39BlockWindows")),
                "base":int(full["base"]) if isinstance(full,dict) else None,
                "opponentStep":int(full["opponentStep"]) if isinstance(full,dict) else None,
                "matrixStride":int(full["matrixStride"]) if isinstance(full,dict) else None,
                "distributionEncoding":full.get("encoding") if isinstance(full,dict) else None,
                "opponentMappingVerified":False,
                "rankGroupLabelsVerified":False,"mayActivateDrops":False,
            }
            unknown=("GRUPO_1","GRUPO_2","GRUPO_3")
            decoded,_ = decode_drops(wa,unknown)
            if decoded is None and evidence.get("state")=="unique_structural_candidate":
                bridge=use_unique_weight_family(evidence,lambda base,step,stride:
                    decode_drops(wa,unknown,opp_base=base,
                                 opp_step=step,rank_stride=stride))
                if bridge is not None:
                    hit=bridge["selected"]
                    decoded,_=decode_drops(wa,unknown,
                        opp_base=hit["opponentBase"],
                        opp_step=hit["opponentStep"],rank_stride=hit["rankStride"])
            count=(len(decoded.get("verificacao",[]))
                   if isinstance(decoded,dict) else 0)
            drops={
                "state":("ambiguous_39_window" if family["ambiguous"] else
                         "117_structural_unlabeled" if count==117 else
                         "unrecognized"),
                "validatedStructuralMatrices":count,
                "labelsVerified":False,"opponentMappingVerified":False,
            }
        else:
            selection=str(selection)
        # Fusion checks are independent; do not erase cards on WA failures.
        fusions=_safe_fusions(path,stamp)
        report={
            "schema":1,"subject":"DUELTRACE ISO Forensic Lab",
            "inspectedAtUTC":datetime.now(timezone.utc).isoformat(
                timespec="seconds"),
            "romFingerprint":expected_sha[:12],
            "exactSha256Matched":True,
            "fileSizeBytes":stamp[2],
            "disc":{"sectorBytes":disc.sector,"indexedFiles":len(disc.files),
                    "resourceSelection":selection,"resourceBytesRead":wa_bytes},
            "executable":executable,"cards":cards,
            "opponents":opponents,"rank":rank,
            "drops":drops,"weightFamily":family,"fusions":fusions,
            "images":images,
            "verifiedInGame":False,
            "mayActivateDrops":False,"mayActivateRank":False,
            "mayActivateFusions":False,"networkTransmission":False,
            "note":"A leitura estrutural da ISO nao confirma IDs ou grupos RANK no jogo.",
        }
        if _snapshot(path)!=stamp:
            raise IsoForensicError("ISO alterada durante a análise; resultados descartados.")
        return report
    finally:
        if disc is not None:
            disc.close()
