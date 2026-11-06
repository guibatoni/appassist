"""Compare structural decoder outcomes across PS1 mods without ROM data.

This is a diagnostic adapter *around* the existing scanner, not a replacement.
Neither a positive baseline nor a coherent 117-matrix layout proves opponent
identity, RANK labels, rewards, fusion semantics or MIPS execution.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

MAX_REPORT_BYTES = 4 * 1024 * 1024
MAX_COMPARISONS = 12
HEX64 = re.compile(r"^[a-fA-F0-9]{64}$")
STAGES = ("cards", "opponents", "resources", "drops", "fusion")


def _count(v, maximum):
    return v if type(v) is int and 0 <= v <= maximum else 0


def _allowed_status(v, allowed, fallback="not_assessed"):
    return v if isinstance(v, str) and v in allowed else fallback


def _clean_sha(value):
    return value.lower()[:12] if isinstance(value, str) and HEX64.fullmatch(value) else None


def fingerprint_scan(info: dict | None) -> dict:
    """Allowlisted, content-free evidence for comparing different ISO families.

    Input is scanner_multiiso.process()'s local relatorio.json; no card text,
    names, offsets, executable bytes, filenames or source paths are copied.
    """
    if not isinstance(info, dict):
        info = {}
    sha = _clean_sha(info.get("sha256"))
    cards = _count(info.get("cartas"), 722)
    opponents = _count(info.get("oponentes"), 39)
    matrices = _count(info.get("tabelas_drops"), 200)
    wa = info.get("wa_resource_selection")
    wa = wa if isinstance(wa, dict) else {}
    layout = info.get("layout_discovery")
    layout = layout if isinstance(layout, dict) else {}
    executables = layout.get("executables")
    executables = executables if isinstance(executables, list) else []
    resources = layout.get("resources")
    resources = resources if isinstance(resources, list) else []
    exe_coherent = sum(
        isinstance(r, dict) and
        isinstance(r.get("executableHeader"), dict) and
        r["executableHeader"].get("headerCoherent") is True
        for r in executables[:20])
    family = info.get("mod_family_evidence")
    family = family if isinstance(family, dict) else {}
    audit = info.get("mod_family_audit")
    audit = audit if isinstance(audit, dict) else {}
    opponent_disc = info.get("independent_opponent_discovery")
    opponent_disc = opponent_disc if isinstance(opponent_disc, dict) else {}
    fd = opponent_disc.get("inlineFdEvidence")
    fd = fd if isinstance(fd, dict) else {}
    clusters = family.get("clusters")
    clusters = clusters if isinstance(clusters, list) else []
    max_blocks = max((_count(r.get("consecutiveBlockCount"), 128)
                      for r in clusters if isinstance(r, dict)), default=0)
    max_windows = max((_count(r.get("possible39BlockWindows"), 128)
                       for r in clusters if isinstance(r, dict)), default=0)
    fusion = info.get("fusion_profile_evidence")
    fusion = fusion if isinstance(fusion, dict) else {}
    fusion_count = _count(fusion.get("count"), 100000)
    fusion_state = (
        "seven_consistent_banks_not_individually_tested"
        if fusion_count > 0 and fusion.get("sevenConsistentBanks") is True
        else "observed_individual_recipes"
        if fusion_count > 0 and fusion.get("manuallyObserved") is True
        else "profile_recipes_unverified"
        if fusion_count > 0 else
        "no_recipes_in_profile"
        if fusion.get("inspected") is True
        else "not_assessed_by_multiiso_scan"
    )
    opponent_origin = _allowed_status(info.get("opponent_identification"),
        {"extraidos_estruturalmente", "verificado", "identificados_por_tabela"})
    wa_state = _allowed_status(wa.get("state"), {
        "sem_recurso", "candidatos_excedem_limite", "matrizes_ambiguas",
        "recurso_candidato_estrutural", "recurso_candidato_nao_validado",
        "recursos_ambiguos_ou_incompativeis", "recurso_alterado_durante_leitura",
        "falha_releitura_recurso",
    })
    drops_group = _allowed_status(info.get("drop_group_mapping_status"),
        {"grupos_nao_identificados", "grupos_validados"})
    return {
        "schema": 1,
        "kind": "DUELTRACE ISO structural comparison",
        "romFingerprint": sha,
        "scannerRevision": _count(info.get("scan_parser_revision"), 10_000),
        "discIndexed": type(info.get("tipo_setor")) is int
                       and info["tipo_setor"] in (2048, 2336, 2352, 2448),
        "bootIndexed": info.get("boot_alvo_indexado") is True,
        "coherentExecutables": exe_coherent,
        "executablesExamined": min(len(executables), 20),
        "resourceCandidatesExamined": min(len(resources), 20),
        "resourceSelection": wa_state,
        "resourceLimitReached": wa.get("limitReached") is True,
        "cards": {
            "count": cards,
            "state": "complete_722" if cards == 722 else
                     "incomplete" if cards else "not_extracted",
        },
        "opponents": {
            "count": opponents,
            "origin": opponent_origin,
            "state": ("structural_names_only"
                      if opponents == 39 and opponent_origin == "extraidos_estruturalmente"
                      else "names_extracted_id_unverified" if opponents == 39
                      else "incomplete" if opponents else "not_extracted"),
            "inGameIdentityVerified": False,
            "inlineFd39Records": fd.get("unique39RecordRun") is True,
        },
        "resources": {
            "state": wa_state,
            "structural117Found": matrices == 117,
            "candidateFamilyCount": _count(family.get("candidateCount"), 1000),
            "longestConsecutiveBlockRun": max_blocks,
            "maxPossible39BlockWindows": max_windows,
            "familyScanStatus": _allowed_status(family.get("state"), {
                "not_found", "invalid_input", "invalid_layout",
                "incomplete_or_ambiguous_scan",
                "unique_structural_candidate",
                "single_family_unmapped_windows",
            }),
            "fallbackAuditStatus": _allowed_status(audit.get("status"), {
                "no_supported_matrix_family", "unique_structural_resource_unverified",
                "family_found_runtime_mapping_pending",
                "ambiguous_family_unverified",
                "multiple_resources_with_candidate_families",
            }),
        },
        "drops": {
            "matrixCount": matrices,
            "state": ("117_matrices_rank_mapping_pending"
                      if matrices == 117 and drops_group == "grupos_nao_identificados"
                      else "117_matrices_unverified" if matrices == 117
                      else "not_fully_extracted"),
            "rankGroupsVerified": info.get("rotulos_ranks_confirmados") is True,
            "opponentToBlockVerified": False,
        },
        "fusion": {
            "state": fusion_state, "recipeCount": fusion_count,
            # Count of recorded recipes is not proof all of them work in-game.
            "recipesVerified": False,
        },
        "missingIndependentEvidence": [
            "GOG/runtime opponent ID to names/blocks",
            "RANK group selection from executed code or observed rewards",
            "fusion inputs/results or validated executable tables",
        ],
    }


def compare_structures(baseline: dict, others: list[dict]) -> dict:
    """Acknowledge the user's successful ISO as a positive observation.

    Differences are diagnostic questions, never automatic adapters or
    permissions to activate ranks, drops or fusions.
    """
    if not isinstance(baseline, dict) or not isinstance(others, list):
        raise ValueError("Invalid structural reports")
    if len(others) > MAX_COMPARISONS:
        raise ValueError("Too many ISO comparisons")
    base = fingerprint_scan(baseline)
    out = []
    for row in others:
        target = fingerprint_scan(row)
        differences = []
        for stage, paths in (
            ("cards", ("state",)),
            ("opponents", ("state", "origin", "inlineFd39Records")),
            ("resources", ("state", "structural117Found",
                           "longestConsecutiveBlockRun", "maxPossible39BlockWindows")),
            ("drops", ("state", "rankGroupsVerified")),
            ("fusion", ("state",)),
        ):
            for key in paths:
                left = base[stage].get(key)
                right = target[stage].get(key)
                if left != right:
                    differences.append({
                        "stage": stage, "feature": key,
                        "baseline": left, "comparison": right,
                    })
        if base["resourceLimitReached"] != target["resourceLimitReached"]:
            differences.append({
                "stage": "resources", "feature": "limitReached",
                "baseline": base["resourceLimitReached"],
                "comparison": target["resourceLimitReached"],
            })
        out.append({
            "romFingerprint": target["romFingerprint"],
            "differences": differences,
            "structurallySameInComparedFields": not differences,
            "inGameValidated": False,
            "suggestedNextAction": (
                "inspect_decoder_boundaries_and_local_report" if differences
                else "trace_runtime_mapping_and_rank_or_fusion_execution"
            ),
        })
    return {
        "schema": 1,
        "kind": "DUELTRACE cross-ISO differential",
        "positiveBaselineFingerprint": base["romFingerprint"],
        "baseline": base,
        "compared": out,
        "automaticallyActivatesFeatures": False,
        "note": "A reference ISO can prove non-regression by testing; report similarity does not prove gameplay mapping.",
    }


def _load(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError("Invalid local report")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not _clean_sha(data.get("sha256")):
        raise ValueError("Report does not include a valid ISO SHA-256")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare local scan reports; never reads or uploads ISO bytes")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--compare", type=Path, nargs="+", required=True)
    options = parser.parse_args(argv)
    if len(options.compare) > MAX_COMPARISONS:
        parser.error("Maximum number of comparisons exceeded")
    print(json.dumps(compare_structures(
        _load(options.baseline), [_load(p) for p in options.compare]
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
