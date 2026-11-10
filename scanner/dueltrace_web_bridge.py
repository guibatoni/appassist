"""Bridge local do design v0 para o motor Python do DUELTRACE.

Não envia ISO, cartas, RAM nem chaves para a nuvem. Objetos JSON contêm
somente dados do perfil validado e deixam explícita a origem dos efeitos.
O JavaScript da interface acessa os métodos via pywebview.api, não por uma
API HTTP aberta para comandos. As imagens são lidas localmente.
"""
from __future__ import annotations

import threading
import json
import hashlib
import re
from uuid import uuid4
from unicodedata import combining, normalize
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

from auto_mods import ModCatalog, load_json, atomic_json
from mod_autopilot import ModAutopilot, profile_summary
from dueltrace_intelligence import MultiModIntelligence
from dueltrace_mod_diagnostic import diagnose_layout
from dueltrace_card_matcher import compare_profiles
from dueltrace_card_match_ai import review_card_candidates
from dueltrace_live_hand import (read_hand_from_epsxe, build_fusion_index,
                                 suggest_hand_pairs)
from dueltrace_private_evidence_sync import PrivateEvidenceSync, EvidenceSyncError
from dueltrace_fusion_planner import plan_fusion_chains
from dueltrace_rank_live import (model_available, read_rank_candidate,
                                 read_rank_from_verified_binding, project_lp_win_rank,
                                 project_spoils_with_adjustment)
from dueltrace_rank_profile_live import (
    validate_live_rank_binding, project_rank_for_mod, x15_compatible_runtime
)
from epsxe_launcher import launch_epsxe
from dueltrace_drops import get_drop_catalog, get_card_drop_sources
from dueltrace_alpha_reward_pools import GROUPS as ALPHA_REWARD_GROUPS
from dueltrace_dynamic_reward_discovery import discover_dynamic_reward_pools
from dueltrace_iso_layout_hints import recover_scan_resource
from dueltrace_drop_rank_evidence import rank_drop_report
from dueltrace_rank_system import available_ranks,rank_system,rank_label_for_existing_score
from dueltrace_mips_duel_trace import inspect_duel_mips_trace, MAX_TRACE_BYTES
from dueltrace_opponent_mips_trace import inspect_opponent_mips_trace
from dueltrace_rank_memory_trace import inspect_rank_memory_trace
from dueltrace_rank_export import build_rank_evidence_report
from dueltrace_rank_duel_verification import compare_rank_observations
from dueltrace_rank_diagnostic import diagnose_rank_profile
from dueltrace_rank_legacy_probe import start_legacy_trial, update_legacy_trial
from dueltrace_spoils_manual import calculate_manual_spoils
from scanner_multiiso import X15_SHA
from dueltrace_library_sort import validate_sort,matches_type,sort_key
from dueltrace_update_checker import (
    check_for_updates, open_official_releases, fetch_stable_release, CURRENT_VERSION
)
from dueltrace_signed_install import (
    trusted_installer_ready, select_signed_installer, install_new_release
)
from dueltrace_preview_installer import (
    fetch_latest_preview_package, install_preview_release,
    fetch_portable_stable_package, install_portable_stable_release
)
from dueltrace_preview_updates import installed_preview_build_id
from dueltrace_private_update_source import PrivateUpdateUnavailable


class DueltraceWebBridge:
    def __init__(self, catalog: ModCatalog | None = None, *,
                 file_picker=None, ram_reader=None, rank_reader=None,
                 rank_mod_reader=None):
        self.catalog = catalog or ModCatalog()
        self._file_picker = file_picker
        self._ram_reader = ram_reader or read_hand_from_epsxe
        self._rank_reader = rank_reader or read_rank_candidate
        self._rank_mod_reader = rank_mod_reader or read_rank_from_verified_binding
        self._rank_calibration = None
        self._rank_auto_probe = None
        self._rank_legacy_trial = None
        self._rank_gap_started = None
        self._rank_lp_session = None
        self._rank_last_turns = None
        self._rank_last_snapshot = None
        self._rank_pending_capture = None
        # Opt-in temporário: nunca comprova compatibilidade nem persiste entre sessões.
        self._rank_experimental_sha = None
        self._process = None
        self._launched_rom_sha = None
        self._lock = threading.RLock()
        self._live_diagnostics = None
        self._live_diagnostics_stop = None
        self._live_diagnostics_thread = None
        # Separate, opt-in remote channel; disabled until configured by user.
        self._private_evidence_sync = PrivateEvidenceSync(
            self.catalog.home / "live_diagnostics")
        self._private_sync_pending = False
        self._private_sync_again = False
        self._fusion_cache_key = None
        self._fusion_cache = {}
        self._alpha_bundle_key = None
        self._alpha_bundle_cache = {}
        self._hand_suggestions_key = None
        self._hand_suggestions = None
        self._cross_mod_cards_cache_key = None
        self._cross_mod_cards_cache = None
        self.settings_path = self.catalog.home / "dueltrace_desktop_settings.json"

    def get_alpha_preferences(self):
        """Return only allowlisted UI preferences, not emulator settings."""
        with self._lock:
            prefs=load_json(self.settings_path,{})
            if not isinstance(prefs,dict):
                prefs={}
            return {"fusionTipsVisible":
                    prefs.get("fusion_tips_visible") is not False}

    def set_alpha_preferences(self, fusion_tips_visible):
        """Persist user choice even when pywebview uses private mode."""
        if type(fusion_tips_visible) is not bool:
            raise ValueError("Preferência de dicas inválida.")
        with self._lock:
            prefs=load_json(self.settings_path,{})
            if not isinstance(prefs,dict):
                prefs={}
            prefs["fusion_tips_visible"]=fusion_tips_visible
            atomic_json(self.settings_path,prefs)
            return {"fusionTipsVisible":fusion_tips_visible}

    def _active(self):
        active = self.catalog.current() or {}
        entry = next((x for x in self.catalog.list()
                      if x.get("sha256") == active.get("sha256")), None)
        profile = self.catalog.profile_for(entry) if entry else None
        return active, entry, profile

    def _cards(self, profile):
        if not profile or not profile.get("supported_features", {}).get("cards"):
            return []
        prepared = []
        for item in profile.get("cards", []):
            try:
                cid = int(item["id"])
            except (ValueError, KeyError, TypeError):
                continue
            if not 1 <= cid <= 722:
                continue
            effect = (str(item.get("effect_text")) if
                      item.get("effect_text") and item.get("effect_source")
                      else None)
            prepared.append({
                "id": cid, "name": str(item.get("name") or f"Carta #{cid}")[:150],
                "type": str(item.get("type_label") or "")[:100],
                "category": str(item.get("category") or "Não identificada")[:100],
                "attribute": str(item.get("attribute") or "")[:60],
                "atk": item.get("atk") if type(item.get("atk")) is int else None,
                "def": item.get("def") if type(item.get("def")) is int else None,
                "effect": effect,
                "effectSource": str(item["effect_source"])[:150] if effect else None,
                "effectStatus": str(item.get("effect_status") or "não_confirmado")[:120]
                    if effect else None,
                "description":str(item.get("description_text") or "")[:550] or None,
                "descriptionSource":str(item.get("description_source") or "")[:150] or None,
                "level":item.get("level") if type(item.get("level")) is int else None,
                "attributeId":item.get("attribute_id") if type(item.get("attribute_id")) is int else None,
                "guardianStar1":item.get("guardian_star_1") if type(item.get("guardian_star_1")) is int else None,
                "guardianStar2":item.get("guardian_star_2") if type(item.get("guardian_star_2")) is int else None,
            })
        return sorted(prepared,key=lambda x:x["id"])

    def _mod_family_summary(self, profile):
        """Expose only bounded structural counters from THIS mod's cached scan.

        No ROM bytes, filenames, paths, SHA values, card identifiers or
        speculative RANK labels enter the UI. These counters never unlock
        game features. Check the canonical local analysis directory first.
        """
        if not isinstance(profile, dict):
            return None
        scan_dir = profile.get("scan_result_dir")
        if not isinstance(scan_dir, str) or not scan_dir:
            return None
        try:
            root = (self.catalog.home / "analises").resolve()
            folder = Path(scan_dir).resolve()
            report_file = (folder / "relatorio.json").resolve()
            if (not folder.is_relative_to(root)
                    or not report_file.is_relative_to(root)
                    or not report_file.is_file()
                    or report_file.stat().st_size > 8 * 1024 * 1024):
                return None
            meta = load_json(report_file, {})
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(meta, dict):
            return None
        revision = meta.get("scan_parser_revision")
        if type(revision) is not int or revision < 29:
            return None
        evidence = meta.get("mod_family_evidence")
        if not isinstance(evidence, dict):
            audit = meta.get("mod_family_audit")
            scanned = audit.get("resourcesScanned", []) if isinstance(audit, dict) else []
            if not isinstance(scanned, list):
                return None
            families = [row.get("weightFamily") for row in scanned[:4]
                        if isinstance(row, dict)
                        and isinstance(row.get("weightFamily"), dict)
                        and type(row["weightFamily"].get("candidateCount")) is int
                        and row["weightFamily"]["candidateCount"] > 0]
            if len(families) != 1:
                return None
            evidence = families[0]
        valid_states = {
            "unique_structural_candidate", "single_family_unmapped_windows",
            "ambiguous_candidates", "incomplete_or_ambiguous_scan",
            "not_found",
        }
        state = evidence.get("state")
        if not isinstance(state, str) or state not in valid_states:
            return None
        clusters = evidence.get("clusters", [])
        if not isinstance(clusters, list):
            return None
        runs = [row for row in clusters[:8] if isinstance(row, dict)
                and type(row.get("consecutiveBlockCount")) is int
                and 39 <= row["consecutiveBlockCount"] <= 128]
        blocks = max((row["consecutiveBlockCount"] for row in runs), default=0)
        windows = max((row.get("possible39BlockWindows", 0) for row in runs
                       if type(row.get("possible39BlockWindows")) is int
                       and 0 <= row["possible39BlockWindows"] <= 128), default=0)
        count = evidence.get("candidateCount")
        count = count if type(count) is int and 0 <= count <= 8 else 0
        return {
            "state": state,
            "scanRevision": revision,
            "candidateCount": count,
            "consecutiveBlocks": blocks,
            "structuralMatrices": blocks * 4,
            "possible39Windows": windows,
            "ambiguous": bool(evidence.get("ambiguous39BlockWindows") is True
                              or windows > 1 or state in
                              {"ambiguous_candidates", "incomplete_or_ambiguous_scan"}),
            "scanComplete": evidence.get("scanComplete") is True,
            "inGameVerified": False,
            "mayActivateDrops": False,
            "mayActivateRank": False,
        }

    def _structural_opponent_choices(self, profile):
        """39 names from THIS mod, with structural positions, never game IDs."""
        if not isinstance(profile, dict):
            return []
        verified = profile.get("verified", {})
        flags = profile.get("supported_features", {})
        if (not isinstance(verified, dict) or not isinstance(flags, dict)
                or verified.get("oponentes") != "extraidos_estruturalmente"
                or flags.get("opponents") is not True):
            return []
        rows = profile.get("opponents", [])
        if not isinstance(rows, list) or len(rows) != 39:
            return []
        choices = []
        for item in rows:
            if not isinstance(item, dict):
                return []
            slot, name = item.get("id"), item.get("name")
            if (type(slot) is not int or not 1 <= slot <= 39
                    or not isinstance(name, str) or not name.strip()
                    or len(name) > 96
                    or any(ord(c) < 32 for c in name)):
                return []
            choices.append({"slot": slot, "name": name})
        if {item["slot"] for item in choices} != set(range(1, 40)):
            return []
        return sorted(choices, key=lambda item: item["slot"])

    def _mod(self, entry):
        profile = self.catalog.profile_for(entry)
        summary = profile_summary(entry, profile)
        return {
            "sha256":entry.get("sha256",""),
            "name":entry.get("display_name") or entry.get("file_name") or summary.get("name") or "Mod local",
            "level":entry.get("level","desconhecido"),
            "scanParserRevision":entry.get("scan_parser_revision") if
                type(entry.get("scan_parser_revision")) is int else None,
            "modFamilyEvidence":self._mod_family_summary(profile),
            "structuralOpponentChoices":self._structural_opponent_choices(profile),
            "cards":summary.get("cards_total",0),
            "candidateCards":max(0,min(722,int((profile or {}).get("candidate_catalogue",{}).get("cards",0))))
                if isinstance((profile or {}).get("candidate_catalogue"),dict) else 0,
            "cardEvidence":str((profile or {}).get("verified",{}).get("cartas") or "pendente"),
            "nameDiscoveryStatus":str((profile or {}).get("name_discovery_status") or "")[:180],
            "fusions":summary.get("fusion_count",0),
            "effects":summary.get("effect_count",0),
            "descriptions":len([c for c in (profile or {}).get("cards",[])
                                if c.get("description_text") and c.get("description_source")]),
            "framedCards":(profile or {}).get("graphic_assets",{}).get("composed_cards",0),
            "frameStyles":(profile or {}).get("graphic_assets",{}).get("frames",0),
            "opponents":len((profile or {}).get("opponents",[]))
                if (profile or {}).get("supported_features",{}).get("opponents") else 0,
            "opponentCandidateCount":(
                (profile or {}).get("opponent_layout_discovery",{})
                .get("candidateOpponentCount",0)),
            "opponentDiscoveryState":(
                (profile or {}).get("opponent_layout_discovery",{})
                .get("state","nao_analisado")),
            "opponentDiagnosticCode":(
                (profile or {}).get("opponent_layout_discovery",{})
                .get("reasonCode","nao_analisado")),
            "opponentDiagnosticReason":(
                str((profile or {}).get("opponent_layout_discovery",{})
                    .get("reason",""))[:220]),
            "opponentEvidence":(
                (profile or {}).get("verified",{}).get("oponentes","pendente")),
            "dropEntries":len((profile or {}).get("drops",[]))
                if (profile or {}).get("supported_features",{}).get("drops") else 0,
            "dropCandidateEntries":((profile or {}).get("drops_provenance",{})
                                     .get("candidate_entry_count",0)
                                     if not (profile or {}).get("supported_features",{})
                                     .get("drops") else 0),
            "dropCandidateTables":((profile or {}).get("drops_provenance",{})
                                    .get("candidate_table_count",0)
                                    if not (profile or {}).get("supported_features",{})
                                    .get("drops") else 0),

            "dropTables":(profile or {}).get("drops_provenance",{}).get("table_count",0)
                if (profile or {}).get("supported_features",{}).get("drops") else 0,
            "rankDetected":(profile or {}).get("rank_points",{}).get("available") is True,
            "rankBinaryVerified":(profile or {}).get("rank_points",{}).get("binary_verified") is True,
            "rankOffset":(profile or {}).get("rank_points",{}).get("first_offset"),
            "rankMipsCandidates":len((profile or {}).get("rank_mips_evidence",{}).get("candidates",[])),
            "rankMipsConfirmed":(profile or {}).get("rank_mips_evidence",{}).get("rank_routine_confirmed") is True,
            "requiresReview":summary.get("requires_review",True),
            "verified":summary.get("validated",{}),
        }

    def check_updates(self):
        """Identifica apenas atualizações oficiais verificáveis da pasta atual."""
        status=check_for_updates(preview_fetcher=lambda:None)
        status["automaticPreviewReady"]=False
        status["automaticPortableReady"]=False
        status["patchNotes"]=[]
        status["patchNotesVersion"]=None

        # Prefere release estável portátil quando for mais recente e válida.
        # Não usa instalador tradicional, que pode criar outra instalação.
        stable_available=status.get("status")=="update_available"
        if stable_available:
            try:
                candidate=fetch_portable_stable_package(
                    current_version=CURRENT_VERSION)
                if candidate is not None:
                    status["automaticPortableReady"]=True
                    status["patchNotes"]=candidate.get("patchNotes",[])
                    status["patchNotesVersion"]=candidate["version"]
                    status["automaticInstallReason"]=(
                        "ZIP estável verificado para substituir arquivos na pasta atual.")
            except (OSError,ValueError,TypeError):
                status["automaticInstallReason"]=(
                    "Não foi encontrado ZIP estável com integridade verificável.")

        try:
            candidate=fetch_latest_preview_package(
                current_version=CURRENT_VERSION,
                installed_run_id=installed_preview_build_id())
            if candidate is not None:
                status.update({
                    "latestPreview":f"v{candidate['version']} Preview",
                    "previewVersion":candidate["version"],
                    "previewRunId":candidate["run_id"],
                    "previewBuildSha":candidate["sha"][:10],
                    "previewPage":candidate["page"],
                    "automaticPreviewReady":True,
                    "previewError":None,
                })
                if not status["automaticPortableReady"]:
                    status.update({
                        "updateAvailable":True,
                        "status":"preview_update_available",
                        "patchNotes":candidate.get("patchNotes",[]),
                        "patchNotesVersion":candidate["version"],
                        "message":(
                            f"Preview v{candidate['version']} verificada no GitHub "
                            "Releases. Clique em Atualizar agora para instalar."),
                        "automaticInstallReason":(
                            "Preview oficial com SHA-256 disponível para "
                            "substituição na pasta atual."),
                    })
        except (OSError,ValueError,TypeError) as exc:
            status["previewError"]=(
                str(exc) if isinstance(exc,PrivateUpdateUnavailable) else
                "Pré-lançamentos temporariamente indisponíveis. "
                "Nenhum download foi iniciado.")

        # Sem pacote portátil verificável, o botão não pode instalar uma
        # versão só porque foi detectada no GitHub.
        if not (status["automaticPortableReady"] or status["automaticPreviewReady"]):
            status["automaticInstallReason"]=(
                status["previewError"] or
                "Não há pacote ZIP oficial verificável para atualização "
                "na pasta atual.")
        return status

    def install_signed_update(self):
        """Somente após autorização explícita do usuário na WebUI."""
        return install_new_release(data_home=self.catalog.home)

    def install_preview_update(self):
        """Baixa pré-release pública com SHA-256, instala após confirmação na UI."""
        result=install_preview_release(data_home=self.catalog.home)
        if result.get("started") and callable(getattr(self,"_request_shutdown",None)):
            self._request_shutdown()
        return result

    def install_portable_update(self):
        """Atualiza ZIP estável oficial sem assinatura, exigindo SHA e commit."""
        result=install_portable_stable_release(data_home=self.catalog.home)
        if result.get("started") and callable(getattr(self,"_request_shutdown",None)):
            self._request_shutdown()
        return result

    def open_updates_page(self, run_id=None):
        """Abre no navegador padrão releases ou o build Preview oficial."""
        if not open_official_releases(run_id):
            raise RuntimeError("Não foi possível abrir o navegador padrão.")
        return {"opened":True}

    def get_state(self):
        with self._lock:
            active, entry, profile = self._active()
            settings = load_json(self.settings_path,{})
            mods = [self._mod(e) for e in self.catalog.list()]
            return {
                "connected":True,"source":"DUELTRACE Windows / dados locais",
                "activeSha":active.get("sha256") if profile else None,
                "activeName":(entry.get("display_name") or entry.get("file_name"))
                    if entry and profile else None,
                "mods":mods,
                "cards":self._cards(profile),
                "fusionCount":len(profile.get("fusion_recipes",[]))
                    if profile and profile.get("supported_features",{}).get("fusions")
                    else 0,
                "epsxeConfigured":bool(settings.get("epsxe_executable")),
                "warning":"O DUELTRACE não confirma automaticamente qual ISO o ePSXe abriu.",
            }

    def rename_mod(self, sha, display_name):
        with self._lock:
            return self.catalog.rename_display(sha,display_name)

    def remove_mod(self, sha):
        with self._lock:
            removed=self.catalog.remove_from_library(sha)
            # Não deixar RANK/fusões/estado do mod anterior em memória.
            if removed.get("wasActive"):
                self._reset_rank_read_state()
                self._rank_experimental_sha=None
                self._fusion_cache_key=None
                self._fusion_cache={}
                self._alpha_bundle_key=None
                self._alpha_bundle_cache={}
                self._hand_suggestions_key=None
                self._hand_suggestions=None
            return removed

    def _alpha_bundle(self, sha, entry, profile):
        """Source-bound, lazy alpha preview; never persists or activates data.

        The full ISO SHA is checked once per source mtime/size and profile
        revision. This path is only reached from an already registered and
        active mod. No arbitrary caller can select another user's file.
        """
        if (not isinstance(profile, dict) or not isinstance(entry, dict)
                or type(sha) is not str or
                not re.fullmatch(r"[a-f0-9]{64}", sha)
                or profile.get("rom_sha256") != sha):
            return {}
        try:
            source = Path(entry.get("source_path") or "").resolve(strict=True)
            stamp = source.stat()
            if (source.suffix.lower() not in (".iso", ".bin")
                    or not 2048 <= stamp.st_size <= 2*1024*1024*1024):
                return {}
            profile_path = (Path(self.catalog.home) / "profiles" /
                            sha[:16] / "profile.json")
            try:
                revision = profile_path.stat().st_mtime_ns
            except OSError:
                revision = 0
            key = (sha, stamp.st_size, stamp.st_mtime_ns, revision)
            if self._alpha_bundle_key == key:
                return self._alpha_bundle_cache
            # Never return stale ISO-derived rows if source was replaced.
            from scanner_multiiso import Disc, sha256 as hash_image
            from extrator_fusoes import analyze_fusion_banks, select_fusion_resource
            if hash_image(source) != sha:
                return {}
            disc = Disc(source)
            try:
                hinted = recover_scan_resource(
                    self.catalog.home, profile, sha, disc.files)
                if hinted is not None:
                    resource_name, family = hinted
                else:
                    resource_name, _method = select_fusion_resource(disc)
                    family = None
                resource_size = disc.files[resource_name][1]
                if (type(resource_size) is not int or
                        not 40*0x1800 <= resource_size <= 96*1024*1024):
                    return {}
                wa = disc.get(resource_name)
                rewards = discover_dynamic_reward_pools(wa, family)
            finally:
                disc.close()
            if (source.stat().st_size, source.stat().st_mtime_ns) != (
                    stamp.st_size, stamp.st_mtime_ns):
                return {}
            provisional = None
            card_list = profile.get("cards", [])
            opponents = profile.get("opponents", [])
            if (rewards.get("available") is True
                    and isinstance(card_list, list) and len(card_list) == 722
                    and isinstance(opponents, list) and len(opponents) == 39
                    and profile.get("supported_features", {}).get("cards") is True
                    and profile.get("verified", {}).get("cartas") == "verificado"):
                provisional = {
                    **profile,
                    "alpha_discovery": {
                        "state": "retail_sentinel_39_reward_records",
                        "source": "local_iso_sha256_matched",
                        "candidateMode": rewards.get("candidateMode"),
                        "rom_sha256": sha,
                    },
                    "drop_group_labels": list(ALPHA_REWARD_GROUPS),
                    "drops": rewards["rows"],
                }
            # Seven mirror banks and a single canonical resource are required
            # before offering *provisional* recipes in the Alpha library.
            fusions = []
            try:
                raw = analyze_fusion_banks(
                    source, expected_size=stamp.st_size,
                    expected_mtime_ns=stamp.st_mtime_ns,
                    resource_name=resource_name)
                if (raw.get("valid_banks") == 7
                        and raw.get("matching_banks") == 7
                        and raw.get("divergent_banks") is False
                        and profile.get("verified", {}).get("cartas") == "verificado"
                        and isinstance(card_list, list)
                        and len(card_list) == 722):
                    results = {}
                    for row in raw.get("candidates", []):
                        a, b, out = (row.get(k) for k in ("a", "b", "result"))
                        if (not all(type(x) is int and 1 <= x <= 722
                                    for x in (a, b, out))):
                            continue
                        results.setdefault((min(a,b), max(a,b)), set()).add(out)
                    # The three contradictory Rising pairs remain QUARANTINED.
                    fusions = [
                        {**row, "validation": "alpha_seven_matching_iso_banks"}
                        for row in raw.get("candidates", [])
                        if ((min(row["a"],row["b"]),max(row["a"],row["b"]))
                            in results
                            and len(results[(
                                min(row["a"],row["b"]),
                                max(row["a"],row["b"]))]) == 1)
                    ]
            except (OSError, ValueError, KeyError, TypeError, RuntimeError,
                    OverflowError):
                fusions = []
            self._alpha_bundle_key = key
            self._alpha_bundle_cache = {
                "rewardProfile": provisional,
                "rewardEvidence": {k:v for k,v in rewards.items() if k!="rows"},
                "fusions": fusions,
                "sourceSha": sha,
                "runtimeVerified": False,
                "provisionalMapping": rewards.get("candidateMode"),
                "resourceMethod": ("source_bound_scan_family"
                                   if hinted is not None else "seven_fusion_banks"),
            }
            return self._alpha_bundle_cache
        except (OSError, ValueError, KeyError, TypeError, RuntimeError,
                OverflowError):
            return {}

    def get_alpha_discovery(self, sha):
        """Inspect one registered local mod when its row is opened in the UI.

        Return counters only. No RAW ROM, names, fusion recipes, probabilities,
        filesystem paths or tokens cross this interface. All results come
        from the exact same registered image and are NEVER game verified.
        """
        if type(sha) is not str or not re.fullmatch(r"[a-f0-9]{64}",sha):
            raise ValueError("Identificador de mod inválido")
        with self._lock:
            entry=next((item for item in self.catalog.list()
                        if item.get("sha256")==sha),None)
            profile=self.catalog.profile_for(entry) if entry else None
            if profile is None:
                return {"available":False,"status":"mod_not_registered",
                        "fusionCandidates":0,"dropCandidates":0,
                        "opponentCount":0,"candidateMode":"unavailable",
                        "verifiedInGame":False}
            bundle=self._alpha_bundle(sha,entry,profile)
            rewards=bundle.get("rewardEvidence",{})
            return {
                "available":bool(bundle.get("rewardProfile")
                                 or bundle.get("fusions")),
                "status":str(rewards.get("status") or "not_decoded")[:100],
                "dropCandidates":int(rewards.get("rowCount") or 0)
                    if bundle.get("rewardProfile") else 0,
                "fusionCandidates":len(bundle.get("fusions",[])),
                "opponentCount":len(profile.get("opponents",[])),
                "candidateMode":str(rewards.get("candidateMode")
                                   or "unavailable")[:80],
                "possible39Windows":int(rewards.get("possible39Windows") or 0),
                "verifiedInGame":False,
                "mayActivateDrops":False,
                "mayActivateRank":False,
            }

    def _combined_fusion_recipes(self, sha, entry, profile):
        """Keep same-SHA curated recipes and add conflict-free ISO candidates.

        A manually verified fusion is never replaced by a contradictory
        structural candidate. The output remains a UI suggestion, NOT a new
        verified profile. Source-specific provenance is kept per recipe.
        """
        if not isinstance(profile, dict):
            return [], False
        curated = (profile.get("fusion_recipes", [])
                   if profile.get("supported_features", {}).get("fusions") else [])
        curated = curated if isinstance(curated, list) else []
        alpha = self._alpha_bundle(sha, entry, profile)
        candidates = alpha.get("fusions", [])
        candidates = candidates if isinstance(candidates, list) else []
        result = []
        pairs = {}
        for row in curated:
            if not isinstance(row, dict):
                continue
            a,b,r=(row.get("a"),row.get("b"),row.get("result"))
            if not all(type(v) is int and 1<=v<=722 for v in (a,b,r)):
                continue
            key=(min(a,b),max(a,b))
            pairs.setdefault(key,set()).add(r)
            result.append(row)
        existing={(r["a"],r["b"],r["result"]) for r in result}
        from_alpha = False
        for row in candidates:
            a,b,r=(row.get("a"),row.get("b"),row.get("result"))
            if not all(type(v) is int and 1<=v<=722 for v in (a,b,r)):
                continue
            key=(min(a,b),max(a,b))
            if key in pairs and r not in pairs[key]:
                continue  # preserve curated/observed behavior
            item=(a,b,r)
            if item in existing:
                continue
            result.append(row)
            existing.add(item)
            pairs.setdefault(key,set()).add(r)
            from_alpha = True
        return result, from_alpha

    def _fusion_index(self, sha, profile):
        profile_path=Path(self.catalog.home)/"profiles"/sha[:16]/"profile.json"
        try:
            stamp=profile_path.stat().st_mtime_ns
        except OSError:
            stamp=0
        _active,entry,_profile=self._active()
        try:
            source=Path(entry["source_path"]).stat()
            source_stamp=(source.st_size,source.st_mtime_ns)
        except (OSError,KeyError,TypeError,ValueError):
            source_stamp=None
        key=(sha,stamp,source_stamp)
        if self._fusion_cache_key != key:
            recipes,_alpha=self._combined_fusion_recipes(sha,entry,profile)
            self._fusion_cache=build_fusion_index(recipes)
            self._fusion_cache_key=key
            self._hand_suggestions_key=None
            self._hand_suggestions=None
        return self._fusion_cache

    def get_hand(self):
        with self._lock:
            active,entry,profile=self._active()
            if not profile:
                return {"ready":False,"status":"Ative uma ISO na Biblioteca de Mods",
                        "hand":[],"pairs":[],"chains":[]}
            preferred=(self._process.pid if self._process is not None and
                       self._process.poll() is None else None)
            try:
                sample=self._ram_reader(preferred_pid=preferred)
            except (OSError,RuntimeError,ValueError) as exc:
                sample={"ready":False,"status":f"Leitura não disponível: {exc}",
                        "hand_ids":None}
            ids=sample.get("hand_ids") if sample.get("ready") else None
            if not (isinstance(ids,list) and len(ids)==5):
                return {"ready":False,"status":sample.get("status","Mão indisponível"),
                        "hand":[],"pairs":[],"chains":[]}
            cards={c["id"]:c for c in self._cards(profile)}
            enriched=[{"slot":i+1,**cards.get(cid,{
                "id":cid,"name":f"Carta #{cid}","atk":None,"def":None,
                "effect":None,"effectSource":None})}
                for i,cid in enumerate(ids)]
            index=self._fusion_index(active["sha256"],profile)
            hand_key=(self._fusion_cache_key,tuple(ids))
            if hand_key!=self._hand_suggestions_key or self._hand_suggestions is None:
                pairs=suggest_hand_pairs(ids,index,cards,limit=24)
                chains=plan_fusion_chains(ids,index,cards,min_cards=2,max_cards=5,limit=16)
                self._hand_suggestions={"pairs":pairs,
                                        "chains":chains["routes"],
                                        "chainsComplete":chains["complete"]}
                self._hand_suggestions_key=hand_key
            return {"ready":True,"status":sample.get("status","Mão identificada"),
                    "hand":enriched,**self._hand_suggestions}

    def get_rank_diagnostic(self):
        """Explica o bloqueio sem ler o ePSXe nem ativar modelo provisório."""
        with self._lock:
            active,_entry,profile=self._active()
            return diagnose_rank_profile(active.get("sha256"),profile)

    def _reset_rank_read_state(self):
        """Não reaproveitar calibração/captura quando a autorização mudou."""
        self._rank_calibration=None
        self._rank_auto_probe=None
        self._rank_legacy_trial=None
        self._rank_gap_started=None
        self._rank_lp_session=None
        self._rank_last_turns=None
        self._rank_last_snapshot=None
        self._rank_pending_capture=None

    def _rank_sample(self):
        active,entry,profile=self._active()
        sha=active.get("sha256") if profile else None
        binding=validate_live_rank_binding(profile)
        if (not isinstance(profile,dict) or type(sha) is not str
                or not re.fullmatch(r"[0-9a-f]{64}",sha)):
            self._reset_rank_read_state()
            return None,sha,{"state":"unsupported","ready":False,
                "status":"Selecione uma ISO com perfil antes de tentar ler o RANK.",
                "rankSystem":rank_system(sha),
                "score":None,"category":None,"counters":None}
        # Conferir LP ou observar alterações plausíveis não prova a identidade
        # do registro RAM. O endereço legado nunca é presumido para outro mod,
        # nem quando apenas o executável e a tabela estática coincidem.
        experimental=(binding is None and not model_available(sha)
                      and self._rank_experimental_sha==sha)
        if (profile.get("rom_sha256") != sha or
                (binding is None and not model_available(sha) and not experimental)):
            self._reset_rank_read_state()
            return None,sha,{"state":"unsupported","ready":False,
                "status":"RANK automático não validado para esta ISO. "
                         "Para investigar a RAM antiga, ative o teste experimental "
                         "e confira os LP; ou use o cálculo manual.",
                "sourceMode":"unsupported","rankSystem":rank_system(sha),
                "score":None,"category":None,"counters":None}
        preferred=(self._process.pid if self._process is not None and
                   self._process.poll() is None else None)
        try:
            sample=(self._rank_mod_reader(binding, preferred_pid=preferred)
                    if binding is not None else
                    self._rank_reader(preferred_pid=preferred))
        except (OSError,RuntimeError,ValueError) as exc:
            sample={"ready":False,"status":str(exc)[:150],"pid":None,"counters":None}
        if not sample.get("ready"):
            # Um frame ilegível não deve apagar a conferência dos LP e obrigar
            # a clicar Confirmar a cada oscilação. Preservar APENAS por até
            # 2,5 s e APENAS quando o leitor identificou o mesmo PID.
            # Nenhum score antigo é mostrado enquanto a RAM está indisponível.
            calibration=self._rank_calibration
            same_process=(isinstance(calibration,dict)
                          and calibration.get("sha")==sha
                          and type(sample.get("pid")) is int
                          and sample["pid"]==calibration.get("pid"))
            if same_process:
                now=monotonic()
                if self._rank_gap_started is None:
                    self._rank_gap_started=now
                if now-self._rank_gap_started<=2.5:
                    if self._rank_pending_capture is not None:
                        self._rank_pending_capture["ram_gap"]=True
                    return None,sha,{
                        "state":"unavailable","ready":False,
                        "status":"Leitura RAM instável; conferência de LP mantida "
                                 "temporariamente para o mesmo processo.",
                        "sourceMode":"experimental" if experimental else "verified",
                        "rankSystem":rank_system(sha),
                        "score":None,"category":None,"counters":None}
            self._rank_gap_started=None
            self._rank_calibration=None
            self._rank_lp_session=None
            self._rank_legacy_trial=None
            self._rank_last_turns=None
            # Captura explícita sobrevive à tela de resultado/transição,
            # mesmo que o registro RAM desapareça. Ainda expira em 10 min.
            if self._rank_pending_capture is not None:
                self._rank_pending_capture["ram_gap"]=True
            return None,sha,{"state":"unavailable","ready":False,
                "status":sample.get("status","Leitura indisponível"),
                "sourceMode":"experimental" if experimental else "verified",
                "rankSystem":rank_system(sha),
                "score":None,"category":None,"counters":None}
        self._rank_gap_started=None
        sample["experimental"]=experimental
        return sample,sha,None

    def set_rank_experimental(self, enabled):
        """Habilita a leitura antiga somente após opt-in explícito nesta sessão/ISO.

        Não cria binding validado e nunca utiliza a hipótese como evidência.
        """
        if type(enabled) is not bool:
            raise ValueError("Opção de leitura experimental inválida.")
        with self._lock:
            active,_entry,profile=self._active()
            sha=active.get("sha256")
            if enabled:
                if (type(sha) is not str or
                        not re.fullmatch(r"[0-9a-f]{64}",sha) or
                        not isinstance(profile,dict) or
                        profile.get("rom_sha256")!=sha):
                    raise ValueError("Selecione uma ISO com perfil local para testar a RAM.")
                if model_available(sha) or validate_live_rank_binding(profile) is not None:
                    return {"enabled":False, "status":
                            "Esta ISO já possui um leitor específico de RANK; use a leitura normal."}
                self._rank_experimental_sha=sha
            else:
                self._rank_experimental_sha=None
            self._reset_rank_read_state()
            return {"enabled":bool(enabled),
                    "status":("Leitura experimental habilitada apenas para esta ISO. "
                              "Abra um duelo, confira os LP e faça duas ações. "
                              "Resultado provisório, nunca validado automaticamente."
                              if enabled else "Leitura experimental desativada.")}

    def calibrate_rank(self):
        """Reinicia a calibração automática usando o leitor da ISO ativa.

        Para ISO sem binding validado, o clique autoriza apenas a leitura
        experimental desta sessão, com as verificações de LP e de mudanças
        coerentes já existentes. Não valida o modelo nem altera os RANKs.
        """
        with self._lock:
            active,_entry,profile=self._active()
            sha=active.get("sha256")
            if (type(sha) is not str or not re.fullmatch(r"[0-9a-f]{64}",sha)
                    or not isinstance(profile,dict)
                    or profile.get("rom_sha256")!=sha):
                raise ValueError("Selecione uma ISO com perfil antes de calibrar.")
            if model_available(sha) or validate_live_rank_binding(profile) is not None:
                self._rank_experimental_sha=None
                self._reset_rank_read_state()
            else:
                # Reutiliza o consentimento e o leitor já implementados.
                self.set_rank_experimental(True)
            return {"started":True,"status":"Calibração iniciada."}

    def calculate_spoils(self, counters, victory, reference="classic"):
        """Calculadora manual funciona mesmo sem perfil ativo; nunca lê RAM."""
        if reference not in ("classic","x15") or type(reference) is not str:
            raise ValueError("Sistema de RANK de referência inválido.")
        with self._lock:
            active,_entry,profile=self._active()
            sha=active.get("sha256")
            if (isinstance(profile,dict) and type(sha) is str
                    and re.fullmatch(r"[0-9a-f]{64}",sha)
                    and profile.get("rom_sha256")==sha):
                # Uma ISO realmente selecionada sempre define a classificação.
                return calculate_manual_spoils(counters,victory,sha)
            # Sem ISO: exemplo de referência declarado, sem atribuir o resultado a um mod.
            ref_sha=X15_SHA if reference=="x15" else "0"*64
            result=calculate_manual_spoils(counters,victory,ref_sha)
            result["referenceOnly"]=True
            result["note"]=("Estimativa de referência sem ISO selecionada, "
                            "sem leitura do ePSXe e sem validação neste mod. "
                            + result["note"])
            return result


    def get_rank(self):
        """Sem pontuação até o usuário validar os LP do duelo atual."""
        with self._lock:
            sample,sha,issue=self._rank_sample()
            if issue is not None:
                return issue
            counters=sample["counters"]
            pid=sample["pid"]
            _a,_e,profile=self._active()
            binding=validate_live_rank_binding(profile)
            experimental=sample.get("experimental") is True
            turns=counters[binding["turns_criterion"]] if binding else counters["turns"]
            capture=self._rank_pending_capture
            if isinstance(capture,dict):
                if capture.get("rom_sha256")!=sha or capture.get("pid")!=pid:
                    self._rank_pending_capture=None
                elif capture.get("returned_to_menu") and turns>0:
                    self._rank_pending_capture=None  # outro duelo iniciou
                elif capture.get("ram_gap") and turns>0:
                    self._rank_pending_capture=None  # retomou com novo duelo
            if (self._rank_last_turns is not None and
                    (self._rank_last_turns[0]!=(sha,pid) or
                     turns < self._rank_last_turns[1])):
                same_process=self._rank_last_turns[0]==(sha,pid)
                new_duel=same_process and turns<self._rank_last_turns[1]
                if (same_process and self._rank_pending_capture is not None):
                    self._rank_pending_capture["returned_to_menu"]=True
                # Após uma conferência manual válida dos LP, outras partidas
                # da MESMA sessão ePSXe podem reusar o valor inicial se o
                # contador de turnos reiniciou e os LP voltaram exatamente
                # ao valor conferido. Nunca liberar outra ISO ou PID.
                remembered=self._rank_lp_session
                resume=(experimental and new_duel
                        and isinstance(remembered,dict)
                        and remembered.get("sha")==sha
                        and remembered.get("pid")==pid
                        and remembered.get("lp")==counters["remaining_lp"]
                        and monotonic()-remembered.get("at",0)<7200)
                self._rank_calibration=None  # novo duelo ou contador reiniciado
                self._rank_gap_started=None
                self._rank_legacy_trial=None
                self._rank_last_snapshot=None
                if resume:
                    self._rank_calibration={"sha":sha,"pid":pid,"at":monotonic()}
                    self._rank_legacy_trial=start_legacy_trial(sha,pid,counters)
                else:
                    self._rank_lp_session=None
            self._rank_last_turns=((sha,pid),turns)
            calibrated=(self._rank_calibration is not None and
                self._rank_calibration["sha"]==sha and
                self._rank_calibration["pid"]==pid and
                monotonic()-self._rank_calibration["at"]<7200)
            if not calibrated:
                self._rank_calibration=None
                return {"ready":False,"state":"needs_lp_confirmation",
                    "status":("Leitura experimental do Assistente antigo detectada. "
                              "Confirme os LP do jogo para testar as mudanças dos contadores."
                              if experimental else
                              "Confirme os LP exibidos pelo jogo neste duelo para habilitar a projeção."),
                    "sourceMode":"experimental" if experimental else "verified",
                    "rankSystem":rank_system(sha),
                    "candidateLp":counters[binding["life_points_criterion"]] if binding else counters["remaining_lp"],
                    "score":None,"category":None,"counters":None}
            if experimental:
                verdict,events=update_legacy_trial(
                    self._rank_legacy_trial,sha,pid,counters)
                if verdict=="invalid":
                    self._rank_calibration=None
                    self._rank_legacy_trial=None
                    self._rank_lp_session=None
                    self._rank_last_snapshot=None
                    return {"ready":False,"state":"needs_lp_confirmation",
                            "sourceMode":"experimental","rankSystem":rank_system(sha),
                            "status":"Contadores mudaram de forma incoerente ou o processo mudou. "
                                     "Confira os LP e inicie nova validação experimental.",
                            "candidateLp":counters["remaining_lp"],
                            "score":None,"category":None,"counters":None}
                if verdict=="observing":
                    return {"ready":False,"state":"needs_ram_validation",
                            "sourceMode":"experimental","rankSystem":rank_system(sha),
                            "status":"LP confirmados. Faça ações normais no duelo; "
                                     "aguardando duas alterações coerentes da RAM antiga.",
                            "validationProgress":events,"validationRequired":2,
                            "candidateLp":counters["remaining_lp"],
                            "score":None,"category":None,"counters":None}
            # O Assistente X15 v10.5 usa o primeiro byte assinado da
            # estrutura do duelista como ajuste de resultado. Somente a ISO
            # X15 exata pode ativar esta inferência; não transportar os
            # endereços ou marcadores para FM13/original por semelhança.
            marker=(sample.get("result_adjustment")
                    if binding is None and model_available(sha) else None)
            observed_adjustment=marker if marker in (2,-40) else None
            result=(project_rank_for_mod(profile,counters)
                    if binding else
                    project_spoils_with_adjustment(counters,observed_adjustment)
                    if observed_adjustment is not None else
                    project_lp_win_rank(counters))
            if experimental:
                result["model"]=(
                    "Modelo de SPOILS legado em teste nesta ISO; "
                    "pontuação ainda não validada no jogo.")
            # A classificação é SEMPRE decidida pelo SHA da ISO selecionada.
            # Mesmo que os pontos e as tabelas numéricas sejam iguais, Z-POW
            # não é exibido para Original, FM13 nem outros mods.
            display_category=rank_label_for_existing_score(sha,result["score"])
            visible_counters=dict(counters)
            if binding:
                visible_counters["turns"]=counters[binding["turns_criterion"]]
                visible_counters["remaining_lp"]=counters[binding["life_points_criterion"]]
            compatible=(binding is None and not model_available(sha) and
                        x15_compatible_runtime(profile))
            if experimental:
                status=("Leitura experimental do registro antigo: LP conferidos e "
                        "duas alterações de contadores observadas. A pontuação "
                        "é provisória e a ISO no ePSXe não foi confirmada.")
            elif observed_adjustment==2:
                status=("Marcador de vitória por LP (+2) detectado em duas "
                        "leituras estáveis do X15; não é o score oficial do jogo.")
            elif observed_adjustment==-40:
                status=("Marcador de deck-out (-40) detectado em duas "
                        "leituras estáveis do X15; não é o score oficial do jogo.")
            elif compatible:
                status=("SLUS e tabela RANK idênticos ao X15; LP confirmado, "
                        "mas resultado final do jogo ainda não verificado.")
            else:
                status=("Projeção se vencer por LP; resultado e mapeamento RAM "
                        "ainda exigem comparação no jogo.")
            if not experimental:
                self._rank_last_snapshot={
                    "rom_sha256":sha,"pid":pid,"monotonic_at":monotonic(),
                    "score":result["score"],"category":display_category,
                    "counters":visible_counters.copy(),
                }
            else:
                # Projeção experimental NUNCA pode ser usada como evidência
                # para desbloquear o binding ou confirmar um drop.
                self._rank_last_snapshot=None
            return {"ready":True,"state":"provisional",
                    "status":status,
                    "sourceMode":"experimental" if experimental else "verified",
                    "validationProgress":2 if experimental else None,
                    "candidateLp":counters[binding["life_points_criterion"]] if binding else counters["remaining_lp"],
                    "score":result["score"],"category":display_category,
                    "counters":visible_counters,"breakdown":result["breakdown"],
                    "model":result["model"],"rankSystem":rank_system(sha),
                    "victorySource":("ram_lp" if observed_adjustment==2
                                     else "ram_deckout" if observed_adjustment==-40
                                     else "projected_lp"),
                    "victoryBonus":(
                        observed_adjustment
                        if observed_adjustment is not None else
                        binding["victory_bonuses"]["lp"] if binding else 2),
                    "final":False}


    def get_rank_auto(self):
        """Projeta automaticamente por ISO e PID, preservando a fórmula SPOILS.

        Requer duas consultas separadas com LP idênticos; o leitor de RAM
        faz duas leituras internas estáveis em cada consulta. Sem binding
        validado, a leitura depende de opt-in e de duas ações reais no jogo.
        Esse consenso é provisório, NÃO prova que a ISO aberta no ePSXe
        corresponde à ISO selecionada no DUELTRACE.
        """
        with self._lock:
            state=self.get_rank()
            # Sem botão de calibração: só iniciar leitura legada se houver
            # um duelo plausível no emulador. Preserva as verificações de
            # LP/PID, duas leituras estáveis e mudanças dos contadores já
            # implementadas. Nunca registra como binding validado.
            if (state.get("state")=="unsupported"
                    and self._rank_experimental_sha is None):
                active, _entry, profile=self._active()
                sha=active.get("sha256")
                if (type(sha) is str and re.fullmatch(r"[0-9a-f]{64}",sha)
                        and isinstance(profile,dict)
                        and profile.get("rom_sha256")==sha
                        and validate_live_rank_binding(profile) is None
                        and not model_available(sha)):
                    preferred=(self._process.pid if self._process is not None
                               and self._process.poll() is None else None)
                    try:
                        observed=self._rank_reader(preferred_pid=preferred)
                    except (OSError,RuntimeError,ValueError,TypeError,KeyError):
                        observed=None
                    if isinstance(observed,dict) and observed.get("ready") is True:
                        fields=observed.get("counters")
                        pid=observed.get("pid")
                        if (isinstance(fields,dict)
                                and type(pid) is int and pid>0
                                and type(fields.get("turns")) is int
                                and fields["turns"]>=1
                                and type(fields.get("remaining_lp")) is int
                                and 0<fields["remaining_lp"]<=32766):
                            self._rank_experimental_sha=sha
                            self._reset_rank_read_state()
                            state=self.get_rank()
            if state.get("ready") is True:
                self._rank_auto_probe=None
                if (isinstance(self._rank_calibration,dict)
                        and self._rank_calibration.get("automatic") is True):
                    return {**state,"autoCalibrated":True,
                            "calibrationMode":"automatic_provisional"}
                return state
            if state.get("state") != "needs_lp_confirmation":
                self._rank_auto_probe=None
                return state
            sha=(self._active()[0] or {}).get("sha256")
            lp=state.get("candidateLp")
            process=self._rank_last_turns
            if (type(sha) is not str or not re.fullmatch(r"[0-9a-f]{64}",sha)
                    or type(lp) is not int or not 0<lp<=32766
                    or not isinstance(process,tuple) or len(process)!=2
                    or not isinstance(process[0],tuple) or process[0][0]!=sha
                    or type(process[0][1]) is not int
                    or type(process[1]) is not int or process[1]<1):
                self._rank_auto_probe=None
                return {**state,"state":"auto_calibrating",
                        "status":"Aguardando duelo ativo e LP legíveis na RAM.",
                        "autoCalibrated":False}
            pid=process[0][1]
            # Mudanças de LP, ISO, processo ou tipo de leitura zeram a série.
            key=(sha,pid,lp,state.get("sourceMode"))
            previous=self._rank_auto_probe
            count=(min(2,previous["count"]+1)
                   if isinstance(previous,dict) and previous.get("key")==key
                   else 1)
            self._rank_auto_probe={"key":key,"count":count}
            if count<2:
                return {**state,"state":"auto_calibrating",
                        "status":"Conferindo LP automaticamente no ePSXe (1/2). "
                                 "Projeção liberada após leituras coerentes.",
                        "autoCalibrated":False,
                        "validationProgress":count,"validationRequired":2}
            self._rank_auto_probe=None
            verified=self.confirm_rank_lp(lp)
            # A confirmação relê a RAM; não autorizar a troca silenciosa de PID.
            calibration=self._rank_calibration
            if (not isinstance(calibration,dict)
                    or calibration.get("sha")!=sha or calibration.get("pid")!=pid):
                self._reset_rank_read_state()
                return {**state,"ready":False,"state":"auto_calibrating",
                        "score":None,"category":None,"counters":None,
                        "status":"ePSXe ou duelo mudou durante a conferência. "
                                 "Aguardando uma nova leitura estável.",
                        "autoCalibrated":False}
            calibration["automatic"]=True
            if verified.get("ready") is True:
                return {**verified,"autoCalibrated":True,
                        "calibrationMode":"automatic_provisional"}
            return {**verified,"autoCalibrated":False}

    def capture_rank_prediction(self):
        """Congela uma previsão de vitória LP com clique explícito no duelo.

        Não confirma o resultado do jogo, nem reconhece qual ISO o ePSXe abriu.
        Só compara com o resultado manual informado posteriormente.
        """
        with self._lock:
            current=self.get_rank()
            snap=self._rank_last_snapshot
            if current.get("sourceMode")=="experimental":
                raise ValueError("Uma leitura experimental não pode ser capturada "
                                 "como RANK validado. Confirme em duelos reais.")
            if not current.get("ready") or not isinstance(snap,dict):
                raise ValueError("Confirme os LP e obtenha um RANK válido antes de capturar.")
            sha=snap["rom_sha256"]
            capture={
                "id":str(uuid4()),"rom_sha256":sha,
                "pid":snap["pid"],"at":monotonic(),
                "score":snap["score"],"category":snap["category"],
                "counters":dict(snap["counters"]),
            }
            self._rank_pending_capture=capture
            return self.get_pending_rank_capture()

    def get_pending_rank_capture(self):
        """Exibe somente metadados da captura ativa; sem RAM bruta ou PID."""
        with self._lock:
            active,_entry,profile=self._active()
            capture=self._rank_pending_capture
            if (not profile or not isinstance(capture,dict)
                    or capture.get("rom_sha256")!=active.get("sha256")
                    or monotonic()-capture.get("at",-1e9)>600):
                self._rank_pending_capture=None
                return {"ready":False,"captureId":None,"score":None,"category":None,
                        "status":"Nenhuma previsão capturada neste duelo."}
            return {"ready":True,"captureId":capture["id"],
                    "score":capture["score"],"category":capture["category"],
                    "status":"Previsão capturada para conferência após a partida (vitória LP)."}

    def confirm_rank_lp(self, life_points):
        if type(life_points) is not int or not 0<=life_points<=32766:
            raise ValueError("Informe os LP exatos mostrados no duelo (0 a 32766).")
        with self._lock:
            sample,sha,issue=self._rank_sample()
            if issue is not None:
                return issue
            _a,_e,profile=self._active()
            binding=validate_live_rank_binding(profile)
            lp_key=binding["life_points_criterion"] if binding else "remaining_lp"
            turns_key=binding["turns_criterion"] if binding else "turns"
            if sample["counters"][lp_key]!=life_points:
                self._rank_calibration=None
                self._rank_legacy_trial=None
                self._rank_lp_session=None
                self._rank_last_snapshot=None
                self._rank_pending_capture=None
                return {"ready":False,"state":"lp_mismatch",
                    "sourceMode":"experimental" if sample.get("experimental") else "verified",
                    "rankSystem":rank_system(sha),
                    "status":"LP do jogo divergentes do candidato RAM. Contador não habilitado.",
                    "candidateLp":sample["counters"][lp_key],
                    "score":None,"category":None,"counters":None}
            self._rank_calibration={"sha":sha,"pid":sample["pid"],"at":monotonic()}
            self._rank_lp_session=(
                {"sha":sha,"pid":sample["pid"],"lp":life_points,"at":monotonic()}
                if sample.get("experimental") is True else None)
            self._rank_gap_started=None
            self._rank_legacy_trial=(
                start_legacy_trial(sha,sample["pid"],sample["counters"])
                if sample.get("experimental") is True else None)
            self._rank_last_turns=((sha,sample["pid"]),sample["counters"][turns_key])
            return self.get_rank()

    def get_fusions(self, query="", offset=0, limit=100,
                    sort="id", card_type="", search_scope="all"):
        """Busca em resultado e/ou materiais da ISO ativa antes da paginação.

        'all' mantém a pesquisa legada (inclui efeito e descrição);
        'result' e 'material' procuram apenas nome ou ID da carta escolhida.
        """
        if type(query) is not str or len(query)>100:
            raise ValueError("Consulta inválida")
        if type(offset) is not int or offset<0 or offset>1000000:
            raise ValueError("Página inválida")
        if type(limit) is not int or not 1<=limit<=150:
            raise ValueError("Limite inválido")
        validate_sort(sort,card_type)
        if type(search_scope) is not str or search_scope not in ("all","result","material"):
            raise ValueError("Campo de pesquisa de fusões inválido")
        with self._lock:
            active,entry,profile=self._active()
            if not profile:
                return {"total":0,"offset":offset,"rows":[]}
            recipes,alpha_added=self._combined_fusion_recipes(
                active.get("sha256"),entry,profile)
            if not recipes:
                return {"total":0,"offset":offset,"rows":[]}
            cards={c["id"]:c for c in self._cards(profile)}
            def search_text(text):
                return "".join(ch for ch in normalize("NFKD",text.casefold())
                               if not combining(ch))
            q=search_text(query.strip())
            rows=[]
            for item in recipes:
                try:
                    a,b,result=(int(item[k]) for k in ("a","b","result"))
                except (KeyError,ValueError,TypeError):
                    continue
                if not all(1<=v<=722 for v in (a,b,result)):
                    continue
                dest=cards.get(result,{})
                if not matches_type(dest,card_type):
                    continue
                names=[cards.get(cid,{}).get("name") or f"Carta #{cid}"
                       for cid in (a,b,result)]
                if search_scope=="result":
                    search_ids=(result,)
                    texts=[names[2]]
                elif search_scope=="material":
                    search_ids=(a,b)
                    texts=names[:2]
                else:
                    search_ids=(a,b,result)
                    texts=list(names)
                    # Busca geral existente: inclui efeitos e descrições.
                    for cid in (a,b,result):
                        card=cards.get(cid,{})
                        for field in ("effect","description"):
                            value=card.get(field)
                            if isinstance(value,str):
                                texts.append(value)
                searched_id=q.removeprefix("#")
                if q and not (any(q in search_text(text) for text in texts)
                              or searched_id in tuple(str(cid) for cid in search_ids)):
                    continue
                rows.append({
                    "a":a,"b":b,"result":result,
                    "nameA":names[0],"nameB":names[1],
                    "nameResult":names[2],
                    "atk":dest.get("atk"),"def":dest.get("def"),
                    "type":dest.get("type") or dest.get("category") or "",
                    "source":str(item.get("validation") or "Não informada"),
                })
            if sort=="id":
                rows.sort(key=lambda row:(row["result"],row["a"],row["b"]))
            else:
                rows.sort(key=lambda row:(
                    sort_key(cards.get(row["result"]),row["result"],
                             row["nameResult"],sort),
                    row["a"],row["b"]))
            total=len(rows)
            return {
                "total":total,"offset":offset,"rows":rows[offset:offset+limit],
                "provisional": alpha_added,
                "status": ("Fusões da ISO ativa: candidatas de sete bancos "
                           "idênticos e receitas já cadastradas. Pares "
                           "conflitantes omitidos, sem prova individual no jogo."
                           if alpha_added else "Receitas do perfil ativo."),
            }

    def compare_mod_cards(self, source_sha, target_sha, query="",
                          offset=0, limit=40, confidence="todas"):
        """Retorna somente IDs/nomes/evidências: nenhuma arte/ISO é transmitida."""
        if (type(source_sha) is not str or type(target_sha) is not str
                or not re.fullmatch(r"[0-9a-f]{64}", source_sha)
                or not re.fullmatch(r"[0-9a-f]{64}", target_sha)
                or source_sha == target_sha):
            raise ValueError("Selecione duas ISOs diferentes importadas.")
        if (type(query) is not str or len(query)>100
                or type(offset) is not int or not 0<=offset<=722
                or type(limit) is not int or not 1<=limit<=75
                or confidence not in ("todas","alta","revisar","sem_correspondencia")):
            raise ValueError("Filtro de comparação inválido.")
        with self._lock:
            entries={row.get("sha256"):row for row in self.catalog.list()
                     if isinstance(row,dict)}
            if source_sha not in entries or target_sha not in entries:
                raise ValueError("Importe e analise as duas ISOs antes de comparar.")
            left_entry,right_entry=entries[source_sha],entries[target_sha]
            left=self.catalog.profile_for(left_entry)
            right=self.catalog.profile_for(right_entry)
            if not left or not right:
                raise ValueError("Os perfis das ISOs não estão disponíveis.")
            try:
                a=Path(left_entry["profile_path"]).stat()
                b=Path(right_entry["profile_path"]).stat()
                signature=(source_sha,target_sha,a.st_size,a.st_mtime_ns,
                           b.st_size,b.st_mtime_ns)
            except (OSError,KeyError,TypeError,ValueError):
                raise ValueError("Não foi possível ler a revisão dos perfis.")
            if self._cross_mod_cards_cache_key!=signature:
                self._cross_mod_cards_cache=compare_profiles(left,right,self.catalog.home)
                self._cross_mod_cards_cache_key=signature
            data=self._cross_mod_cards_cache
            def wanted(row):
                if confidence!="todas" and row["confidence"]!=confidence:
                    return False
                if not query.strip():
                    return True
                text=(str(row["sourceId"])+" "+str(row.get("targetId") or "")+" "+
                      row["sourceName"]+" "+(row["targetName"] or "")).casefold()
                return query.strip().casefold() in text
            filtered=[row for row in data["rows"] if wanted(row)]
            filtered.sort(key=lambda row:(
                0 if row["confidence"]=="alta" and row["sameId"] is False else
                1 if row["confidence"]=="revisar" else
                2 if row["confidence"]=="alta" else 3,
                row["sourceId"]))
            return {
                "sourceSha":source_sha,"targetSha":target_sha,
                "sourceName":str(left_entry.get("file_name") or "ISO")[:150],
                "targetName":str(right_entry.get("file_name") or "ISO")[:150],
                "summary":dict(data["summary"]),
                "sourceCards":data["sourceCards"],
                "targetCards":data["targetCards"],
                "total":len(filtered),"offset":offset,
                "rows":filtered[offset:offset+limit],
                "status":data["status"],
                "verifiedInGame":False,
            }

    def review_card_matches(self, source_sha, target_sha):
        """Ollama revisa apenas candidatas existentes, não recebe ISO nem PNG.

        Nunca aceita novos IDs produzidos pelo LLM e não promove resultados
        a correspondências verificadas ou alterações de perfil.
        """
        self.compare_mod_cards(source_sha,target_sha,limit=1)
        with self._lock:
            data=self._cross_mod_cards_cache
            if not isinstance(data,dict):
                raise ValueError("Execute primeiro a comparação dos perfis.")
            evidence={**data,"rows":[dict(row) for row in data["rows"]]}
        return review_card_candidates(evidence)

    def get_drops(self, opponent_id=0, group="", query="", offset=0, limit=36,
                  sort="id", card_type="", rank=""):
        """Catalog confirmed tables, or explicitly labeled local ISO Alpha candidates."""
        with self._lock:
            active, entry, profile = self._active()
            original = get_drop_catalog(
                profile, opponent_id=opponent_id, group=group,
                query=query, offset=offset, limit=limit,
                sort=sort,card_type=card_type,rank=rank)
            if original["available"] or not profile:
                return original
            provisional = self._alpha_bundle(
                active.get("sha256"), entry, profile).get("rewardProfile")
            return get_drop_catalog(
                provisional, opponent_id=opponent_id, group=group,
                query=query,offset=offset,limit=limit,
                sort=sort,card_type=card_type,rank=rank)

    def get_card_drop_sources(self, card_id):
        """Consulta somente o perfil da ISO ativa."""
        with self._lock:
            active, _entry, profile = self._active()
            result = get_card_drop_sources(profile, card_id)
            if not result["available"]:
                provisional = self._alpha_bundle(
                    active.get("sha256"), _entry, profile).get("rewardProfile")
                result = get_card_drop_sources(provisional, card_id)
            if result["romSha"] != active.get("sha256"):
                return {**result, "available": False, "rows": [], "total": 0,
                        "status": "Perfil não corresponde à ISO ativa"}
            return result

    def export_rank_audit(self):
        """Exporta evidências numéricas locais para validar uma ISO no Windows."""
        if self._file_picker is None:
            raise RuntimeError("Exportação disponível apenas no aplicativo Windows.")
        with self._lock:
            active,entry,profile=self._active()
            sha=active.get("sha256")
            if not profile or not isinstance(sha,str):
                raise ValueError("Selecione uma ISO para exportar diagnóstico.")
            obs=load_json(self._observations_path(sha),{})
            traces=load_json(self._trace_results_path(sha),{})
            rows=obs.get("observations",[]) if isinstance(obs,dict) else []
            trace_rows=traces.get("records",[]) if isinstance(traces,dict) else []
            drop_summary=rank_drop_report(profile,rows)
            report=build_rank_evidence_report(profile,rows,trace_rows,drop_summary)
            output=json.dumps(report,ensure_ascii=False,indent=2)
            if len(output.encode("utf-8"))>2*1024*1024:
                raise ValueError("Relatório ultrapassou o limite de exportação.")
        selected=self._file_picker("rank_report")
        if not selected:
            return {"cancelled":True}
        path=Path(selected[0] if isinstance(selected,(list,tuple))
                  else selected).expanduser().resolve()
        if path.suffix.lower()!=".json":
            raise ValueError("Selecione um destino com extensão .json.")
        # Modo exclusivo: relatório nunca substitui documentos existentes.
        try:
            with path.open("x",encoding="utf-8") as stream:
                stream.write(output+"\n")
        except FileExistsError as exc:
            raise FileExistsError("Arquivo já existe. Escolha um nome novo.") from exc
        return {"cancelled":False,"file":str(path),
                "reportSha256":report["report_sha256"],
                "bytes":path.stat().st_size,
                "status":"Relatório salvo localmente sem ROM, SLUS, WA ou dados brutos de RAM."}

    def _trace_results_path(self, sha):
        if type(sha) is not str or not re.fullmatch("[0-9a-f]{64}",sha):
            raise ValueError("SHA da ISO inválido")
        return self.catalog.home / "rank_observations" / (sha+".mips.json")

    def get_rank_trace_status(self):
        with self._lock:
            active,entry,profile=self._active()
            sha=active.get("sha256")
            if not profile or not isinstance(sha,str):
                return {"available":False,"records":0,"last":None}
            data=load_json(self._trace_results_path(sha),{})
            records=data.get("records",[]) if isinstance(data,dict) else []
            observations=load_json(self._observations_path(sha),{})
            duels={r.get("duel_id"):r for r in observations.get("observations",[])
                   if isinstance(r,dict)} if isinstance(observations,dict) else {}
            linked=0
            for record in records:
                if not isinstance(record,dict) or not record.get("executionEvidence"):
                    continue
                duel=duels.get(record.get("duel_id"))
                snap=duel.get("rank_snapshot") if isinstance(duel,dict) else None
                if (isinstance(snap,dict) and
                        duel.get("victory_type")=="lp" and
                        type(duel.get("observed_points")) is int and
                        duel["observed_points"]==snap.get("projected_score") and
                        duel.get("observed_rank")==snap.get("projected_rank")):
                    linked+=1
            return {"available":True,"records":len(records),
                    "tableReadReports":sum(
                        bool(x.get("rankTableEvidence",{}).get("tableReadsObserved"))
                        for x in records if isinstance(x,dict)),
                    "correlatedDuels":linked,
                    "rankRoutineConfirmed":False,
                    "last":records[-1] if records else None}

    def import_rank_trace(self, duel_id=None):
        """Lê log do depurador durante duelo; não importa código do jogo."""
        if self._file_picker is None:
            raise RuntimeError("Importação de trace disponível somente no Windows.")
        if duel_id is not None and (type(duel_id) is not str or
                                    not re.fullmatch("[0-9a-f-]{36}",duel_id)):
            raise ValueError("Identificador do duelo inválido.")
        files=self._file_picker("trace")
        if not files:
            return {"cancelled":True}
        path=Path(files[0]).expanduser().resolve(strict=True)
        if path.suffix.casefold() not in (".log",".txt"):
            raise ValueError("Selecione um log de execução MIPS .log ou .txt.")
        if not 0<path.stat().st_size<=MAX_TRACE_BYTES:
            raise ValueError("Log de execução vazio ou acima de 8 MiB.")
        with self._lock:
            active,entry,profile=self._active()
            sha=active.get("sha256")
            if not profile or not sha:
                raise ValueError("Selecione um mod antes de validar a execução.")
            if duel_id is not None:
                obs=load_json(self._observations_path(sha),{})
                valid=obs.get("observations",[]) if isinstance(obs,dict) else []
                if not any(isinstance(x,dict) and x.get("duel_id")==duel_id and
                           x.get("rom_sha256")==sha for x in valid):
                    raise ValueError("O duelo selecionado não pertence à ISO ativa.")
            raw_trace=path.read_bytes()
            report=inspect_duel_mips_trace(
                raw_trace,profile.get("rank_mips_evidence"))
            table_evidence=inspect_rank_memory_trace(
                raw_trace,profile.get("rank_points"),
                profile.get("rank_mips_evidence"))
            opponent_evidence=inspect_opponent_mips_trace(raw_trace)
            if not report["available"] and not opponent_evidence["available"]:
                return {"cancelled":False,**report,
                        "opponentFieldEvidence":opponent_evidence}
            result={
                "record_id":str(uuid4()),
                "duel_id":duel_id,
                "created_at":datetime.now(timezone.utc).isoformat(),
                "source":"trace_exportado_do_emulador",
                "status":(report["status"] if report["available"] else
                          "opponent_field_trace_only"),
                "executionEvidence":report["executionEvidence"],
                "executedCandidates":report["executedCandidates"],
                "instructionSamples":report["instructionSamples"],
                "distinctPCs":report["distinctPCs"],
                "rankRoutineConfirmed":False,
                "traceSha256":report.get("traceSha256") or hashlib.sha256(raw_trace).hexdigest(),
                "rankTableEvidence":table_evidence,
                "opponentFieldEvidence":opponent_evidence,
                "note":report["note"],
            }
            dest=self._trace_results_path(sha)
            prior=load_json(dest,{})
            records=list(prior.get("records",[])) if isinstance(prior,dict) else []
            records.append(result)
            atomic_json(dest,{"schema":1,"rom_sha256":sha,"records":records[-50:]})
            return {"cancelled":False,**result}

    def _window_observation_path(self, sha):
        if type(sha) is not str or not re.fullmatch(r"[a-f0-9]{64}", sha):
            raise ValueError("SHA da ISO inválido")
        return self.catalog.home / "window_observations" / (sha + ".json")

    def get_window_observations(self, sha):
        """Return only non-promoting statistics for a selected registered mod."""
        with self._lock:
            entry = next((row for row in self.catalog.list()
                          if row.get("sha256") == sha), None)
            if entry is None:
                raise ValueError("Mod não cadastrado")
            path = self._window_observation_path(sha)
            if path.is_file() and path.stat().st_size > 128 * 1024:
                raise ValueError("Registro de duelos excede o limite")
            raw = load_json(path, {})
            if not isinstance(raw, dict) or raw.get("rom_sha256") != sha:
                raw = {}
            rows = raw.get("observations", [])
            rows = rows if isinstance(rows, list) else []
            report = raw.get("last_analysis", {})
            report = report if isinstance(report, dict) else {}
            return self._window_observation_summary(rows, report)

    def _window_observation_summary(self, records, report):
        """Expose only manually entered card IDs and aggregate diagnostics."""
        from dueltrace_window_observation import _parse_observation
        safe_entries = []
        for i, row in enumerate(records[-200:]):
            observed = _parse_observation(row)
            if observed is None:
                continue
            safe_entries.append({
                "index": i + 1,
                "opponentSlot": observed["slot"],
                "rank": observed["rank"],
                "rewardCardId": observed["reward"],
                "playedCardIds": list(observed["played"]),
            })
        return {
            "observationCount": len(safe_entries),
            "entries": safe_entries,
            "analysis": report if isinstance(report, dict) else {},
            "mayActivateDrops": False,
            "mayActivateRank": False,
            "inGameVerified": False,
        }

    def _load_structural_family(self, sha, entry, profile):
        """Read original ISO for this SHA; no cached or foreign ROM arrays."""
        from scanner_multiiso import Disc, sha256 as hash_image
        source = Path(entry.get("source_path") or "").resolve(strict=True)
        if source.suffix.lower() not in (".iso", ".bin") or not source.is_file():
            raise ValueError("Imagem de jogo indisponível")
        result_dir = profile.get("scan_result_dir")
        root = (self.catalog.home / "analises").resolve()
        if not isinstance(result_dir, str) or not result_dir:
            raise ValueError("Análise local indisponível")
        folder = Path(result_dir).resolve()
        if not folder.is_relative_to(root):
            raise ValueError("Relatório fora da pasta permitida")
        metadata_file = (folder / "relatorio.json").resolve()
        if (not metadata_file.is_relative_to(root) or
                not metadata_file.is_file() or
                metadata_file.stat().st_size > 8 * 1024 * 1024):
            raise ValueError("Relatório estrutural indisponível")
        meta = load_json(metadata_file, {})
        if (not isinstance(meta, dict)
                or meta.get("sha256") != sha
                or type(meta.get("scan_parser_revision")) is not int
                or meta["scan_parser_revision"] < 29):
            raise ValueError("Reanalise o mod com o scanner revisão 29")
        # O scanner usa DOIS formatos de evidência: quando localiza um
        # recurso WA único, grava mod_family_evidence; para mídias em
        # que WA não foi selecionado, grava mod_family_audit. Antes este
        # método aceitava apenas o segundo formato e recusava o GOG
        # mesmo com seus 40 blocos comprovados no próprio relatório.
        family = meta.get("mod_family_evidence")
        selected_resource = meta.get("wa_resource_selection")
        resource_name = (selected_resource.get("source")
                         if isinstance(selected_resource, dict) else None)
        if (not isinstance(family, dict)
                or not isinstance(resource_name, str)
                or not resource_name):
            audit = meta.get("mod_family_audit")
            resources = (audit.get("resourcesScanned", [])
                         if isinstance(audit, dict) else [])
            candidates = [item for item in resources
                          if isinstance(item, dict)
                          and isinstance(item.get("weightFamily"), dict)
                          and type(item["weightFamily"].get("candidateCount")) is int
                          and item["weightFamily"]["candidateCount"] > 0
                          and isinstance(item.get("resource"), str)
                          and item["resource"]]
            if len(candidates) != 1:
                raise ValueError(
                    "Uma família de matrizes foi exibida, mas sua fonte "
                    "não pôde ser determinada. Reanalise a ISO.")
            family = candidates[0]["weightFamily"]
            resource_name = candidates[0]["resource"]
        if (type(family.get("candidateCount")) is not int
                or family["candidateCount"] < 1
                or family.get("scanComplete") is not True):
            raise ValueError("Família de matrizes incompleta; reanalise a ISO.")
        if hash_image(source) != sha:
            raise ValueError("A ISO mudou desde a análise. Perfil preservado")
        disc = Disc(source)
        try:
            if resource_name not in disc.files:
                raise ValueError("Contêiner original não encontrado")
            blob = disc.get(resource_name)
            # Evita reutilizar evidência de um recurso trocado depois da
            # análise, inclusive quando o SHA total da ISO foi informado
            # por um catálogo local incorreto.
            selected_hash = meta.get("hash_wa")
            if (isinstance(selected_hash, str) and len(selected_hash) == 64
                    and hashlib.sha256(blob).hexdigest() != selected_hash):
                raise ValueError("Contêiner mudou desde a análise. Reanalise o mod.")
            return blob, family
        finally:
            disc.close()

    def _evaluate_window_records(self, sha, entry, profile, records):
        """Re-evaluate after a save or undo; never promotes inferred IDs."""
        from dueltrace_window_observation import correlate_observed_duels
        blob, family = self._load_structural_family(sha, entry, profile)
        report = correlate_observed_duels(blob, family, records)
        if report["status"] in ("invalid_input", "invalid_observation",
                                "unusable_family_layout"):
            raise ValueError("Evidências inconsistentes; nenhuma alteração salva")
        return report

    def _collect_live_diagnostics_once(self, recorder):
        """Use existing, tested readers; never probe arbitrary RAM or alter rank."""
        with self._lock:
            active, _entry, profile = self._active()
            current_sha = active.get("sha256") if profile else None
        if current_sha != recorder.sha:
            recorder.stop()
            return False
        try:
            hand = self.get_hand()
        except (OSError, RuntimeError, ValueError, TypeError):
            hand = {"ready": False, "hand": []}
        try:
            opponent = self.get_live_opponent()
        except (OSError, RuntimeError, ValueError, TypeError):
            opponent = {"ready": False, "status": "runtime_probe_unavailable"}
        # Only consume the *existing* RANK observation (when the main
        # screen has made one). Calling get_rank_auto here would change
        # calibration state and could modify the normal duel experience.
        with self._lock:
            last = self._rank_last_snapshot
            rank = {"ready": False, "state": "unavailable"}
            if (isinstance(last, dict)
                    and last.get("rom_sha256") == current_sha
                    and type(last.get("monotonic_at")) in (float, int)
                    and 0 <= monotonic() - last["monotonic_at"] <= 4):
                rank = {
                    "ready": True, "state": "provisional",
                    "score": last.get("score"), "category": last.get("category"),
                }
        return recorder.observe(hand, opponent, rank, current_sha)

    def _queue_private_evidence_upload(self, recorder):
        """Coalesce periodic and final uploads; never block RAM sampling."""
        if not self._private_evidence_sync.status()["enabled"]:
            return
        with self._lock:
            if self._private_sync_pending:
                self._private_sync_again = True
                return
            self._private_sync_pending = True

        def transmit():
            while True:
                try:
                    self._private_evidence_sync.upload(recorder)
                except (EvidenceSyncError, OSError, RuntimeError, ValueError):
                    # The remote channel is optional. Never break RAM reading.
                    pass
                with self._lock:
                    if self._private_sync_again:
                        self._private_sync_again = False
                    else:
                        self._private_sync_pending = False
                        return
        threading.Thread(target=transmit, daemon=True,
                         name="dueltrace-private-evidence-sync").start()

    def _live_diagnostics_loop(self, recorder, stop_event):
        last_sync = monotonic()
        try:
            while not stop_event.is_set() and recorder.running:
                self._collect_live_diagnostics_once(recorder)
                if monotonic() - last_sync >= 60:
                    self._queue_private_evidence_upload(recorder)
                    last_sync = monotonic()
                if stop_event.wait(3.0):
                    break
        finally:
            recorder.stop()
            self._queue_private_evidence_upload(recorder)

    def configure_private_evidence_sync(self, repository, token, consent):
        """User's explicit action; accepts only verified private GitHub repo."""
        return self._private_evidence_sync.configure(repository, token, consent)

    def disable_private_evidence_sync(self):
        return self._private_evidence_sync.disable()

    def get_private_evidence_sync_status(self):
        return self._private_evidence_sync.status()

    def start_live_diagnostics(self):
        """User opt-in only: sample locally, no cloud and no ROM dumps."""
        from dueltrace_live_diagnostics import LiveDiagnosticsRecorder
        with self._lock:
            active, _entry, profile = self._active()
            sha = active.get("sha256") if profile else None
            if (type(sha) is not str
                    or not re.fullmatch(r"[a-f0-9]{64}", sha)
                    or profile.get("rom_sha256") != sha):
                raise ValueError("Ative uma ISO cadastrada antes de iniciar o diagnóstico")
            current = self._live_diagnostics
            if current and current.running:
                if current.sha == sha:
                    return self.get_live_diagnostics_status()
                raise ValueError("Encerre o diagnóstico anterior antes de trocar de mod")
            recorder = LiveDiagnosticsRecorder(
                self.catalog.home / "live_diagnostics", sha)
            stop_event = threading.Event()
            self._live_diagnostics = recorder
            self._live_diagnostics_stop = stop_event
            self._live_diagnostics_thread = threading.Thread(
                target=self._live_diagnostics_loop,
                args=(recorder, stop_event),
                name="dueltrace-live-diagnostics", daemon=True)
            self._live_diagnostics_thread.start()
            return self.get_live_diagnostics_status()

    def stop_live_diagnostics(self):
        with self._lock:
            if self._live_diagnostics_stop is not None:
                self._live_diagnostics_stop.set()
            if self._live_diagnostics is not None:
                self._live_diagnostics.stop()
                self._queue_private_evidence_upload(self._live_diagnostics)
            return self.get_live_diagnostics_status()

    def get_live_diagnostics_status(self):
        from dueltrace_live_forensics import summarize_live_report
        with self._lock:
            recorder = self._live_diagnostics
            if recorder is None:
                return {
                    "running": False, "sampleCount": 0,
                    "changeCount": 0, "lastObservedAtUTC": None,
                    "opponentStatuses": {}, "readyToCopy": False,
                    "networkTransmission": False,
                    "forensicReview": summarize_live_report(None),
                }
            report = recorder.report()
            return {
                "running": report["running"],
                "romFingerprint": report["romFingerprint"],
                "sampleCount": report["sampleCount"],
                "changeCount": report["changeCount"],
                "lastObservedAtUTC": report["lastObservedAtUTC"],
                "opponentStatuses": report["opponentStatuses"],
                "readyToCopy": report["sampleCount"] > 0,
                "networkTransmission": False,
                # Aggregate-only, local interpretation. No game proof.
                "forensicReview": summarize_live_report(report),
            }

    def export_live_diagnostics(self):
        """Return sanitized text to copy locally; never uploads it."""
        with self._lock:
            if self._live_diagnostics is None:
                raise ValueError("Inicie o diagnóstico antes de exportar")
            return self._live_diagnostics.export_json()

    def get_live_opponent(self):
        """Passive RAM reader with local, provisional ID logging.

        Auto-record only when THIS app launched the process for the
        same active ISO SHA. An external disc swap is not detectable,
        therefore stored IDs cannot promote drops or opponent mappings.
        """
        from dueltrace_live_opponent import probe_live_opponent
        fail={"ready":False,"status":"runtime_probe_unavailable",
              "runtimeOpponentId":None,
              "runtimeIdVerifiedForMod":False,"romIdentityVerified":False,
              "opponentNameVerified":False,
              "mayActivateDrops":False,"mayActivateRank":False,
              "autoLogged":False}
        with self._lock:
            active, entry, profile = self._active()
            sha=active.get("sha256") if isinstance(active,dict) else None
            if not profile:
                return {**fail,"status":"activate_mod"}
            launched=self._process is not None and self._process.poll() is None
            preferred=self._process.pid if launched else None
        try:
            sample=probe_live_opponent(preferred_pid=preferred)
        except (OSError,RuntimeError,ValueError,OverflowError):
            return fail
        if not (isinstance(sample,dict) and sample.get("ready") is True
                and type(sample.get("runtimeOpponentId")) is int
                and 0 <= sample["runtimeOpponentId"] <= 39):
            return {**fail,**sample,"autoLogged":False}
        # RAM field remains only a candidate until tested with this mod.
        outcome={**sample,"autoLogged":False,
                 "runtimeIdVerifiedForMod":False,
                 "romIdentityVerified":False,
                 "opponentNameVerified":False,
                 "mayActivateDrops":False,"mayActivateRank":False}
        if not (launched and preferred is not None
                and type(sha) is str and re.fullmatch(r"[a-f0-9]{64}",sha)):
            return outcome
        with self._lock:
            active_now,_entry,_profile=self._active()
            if (active_now.get("sha256") != sha
                    or self._launched_rom_sha != sha
                    or self._process is None
                    or self._process.poll() is not None
                    or self._process.pid != preferred):
                return outcome
            path=self.catalog.home/"runtime_opponent_observations"/(sha+".json")
            try:
                raw=load_json(path,{})
                if raw and (not isinstance(raw,dict)
                            or raw.get("rom_sha256") != sha):
                    return outcome
                events=raw.get("events",[]) if isinstance(raw,dict) else []
                if not isinstance(events,list) or len(events)>256:
                    return outcome
                if (events and isinstance(events[-1],dict)
                        and events[-1].get("opponentRuntimeId")
                            == sample["runtimeOpponentId"]):
                    return {**outcome,"localRuntimeIdEvents":len(events)}
                events=events[-255:]+[{
                    "opponentRuntimeId":sample["runtimeOpponentId"],
                    "observedAtUTC":datetime.now(timezone.utc).isoformat(),
                    "source":"epsxe_ram_candidate_not_game_verified",
                }]
                atomic_json(path,{
                    "schema":1,"rom_sha256":sha,"events":events,
                    "verifiedForGame":False,"mayActivateDrops":False,
                    "mayActivateRank":False,
                })
                return {**outcome,"autoLogged":True,
                        "localRuntimeIdEvents":len(events)}
            except (OSError,ValueError,TypeError):
                return outcome

    def get_candidate_matrix(self, sha, physical_block_index=-1,
                             matrix_group=1, query="", offset=0, limit=30):
        """Zero-manual-data candidate browser, based on local ISO bytes.

        -1 automatically selects a single physical-block hypothesis already
        derived from observations when available, otherwise explores block 0.
        Neither selection is an opponent ID or proof of a RANK group.
        """
        from dueltrace_candidate_matrix_browser import browse_candidate_matrices
        if type(sha) is not str or not re.fullmatch(r"[a-f0-9]{64}", sha):
            raise ValueError("SHA da ISO inválido")
        if type(physical_block_index) is not int or not -1 <= physical_block_index <= 127:
            raise ValueError("Bloco físico inválido")
        with self._lock:
            entry = next((e for e in self.catalog.list()
                          if e.get("sha256") == sha), None)
            profile = self.catalog.profile_for(entry) if entry else None
            if not profile or not profile.get("supported_features", {}).get("cards"):
                raise ValueError("Catálogo de cartas validado não disponível")
            if len(profile.get("cards", [])) != 722:
                raise ValueError("Catálogo de 722 cartas incompleto")
            selection = "explicit_physical_block_not_opponent"
            chosen = physical_block_index
            if chosen == -1:
                selection = "first_unmapped_block_unverified"
                chosen = 0
                path = self._window_observation_path(sha)
                if path.is_file() and path.stat().st_size <= 128 * 1024:
                    saved = load_json(path, {})
                    analysis = saved.get("last_analysis") if isinstance(saved, dict) and saved.get("rom_sha256") == sha else None
                    scan = analysis.get("unmappedPhysicalBlocks") if isinstance(analysis, dict) else None
                    slots = scan.get("slots") if isinstance(scan, dict) else None
                    if (isinstance(slots, list) and len(slots) == 1
                            and isinstance(slots[0], dict)
                            and slots[0].get("possiblePhysicalBlocks") == 1
                            and isinstance(slots[0].get("candidateSamples"), list)
                            and len(slots[0]["candidateSamples"]) == 1):
                        candidate = slots[0]["candidateSamples"][0]
                        if (isinstance(candidate, dict)
                                and candidate.get("clusterIndex") == 0
                                and type(candidate.get("physicalBlockIndex")) is int
                                and 0 <= candidate["physicalBlockIndex"] < 128):
                            chosen = candidate["physicalBlockIndex"]
                            selection = "single_hypothesis_from_saved_observation"
            blob, family = self._load_structural_family(sha, entry, profile)
            cards = self._cards(profile)
            result = browse_candidate_matrices(
                blob, family, cards,
                physical_block_index=chosen, matrix_group=matrix_group,
                query=query, offset=offset, limit=limit)
            return {**result,
                    "autoSelected": physical_block_index == -1,
                    "selectionReason": selection,
                    "opponentIdsVerified": False,
                    "rankGroupLabelsVerified": False,
                    "mayActivateDrops": False,
                    "mayActivateRank": False}

    def undo_last_window_observation(self, sha):
        """Undo the latest manually entered observation and recompute windows."""
        from dueltrace_window_observation import _parse_observation
        if type(sha) is not str or not re.fullmatch(r"[a-f0-9]{64}", sha):
            raise ValueError("SHA da ISO inválido")
        with self._lock:
            entry = next((e for e in self.catalog.list()
                          if e.get("sha256") == sha), None)
            profile = self.catalog.profile_for(entry) if entry else None
            if not profile:
                raise ValueError("Perfil do mod não localizado")
            path = self._window_observation_path(sha)
            if not path.is_file() or path.stat().st_size > 128 * 1024:
                raise ValueError("Não há registros locais para desfazer")
            previous = load_json(path, {})
            if (not isinstance(previous, dict)
                    or previous.get("rom_sha256") != sha
                    or not isinstance(previous.get("observations"), list)):
                raise ValueError("Registros inválidos ou de outra ISO")
            rows = previous["observations"]
            if (not rows or len(rows) > 200
                    or any(_parse_observation(r) is None for r in rows)):
                raise ValueError("Registro de duelo inválido; nada foi alterado")
            kept = rows[:-1]
            report = self._evaluate_window_records(sha, entry, profile, kept)
            atomic_json(path, {
                "schema": 1, "rom_sha256": sha,
                "observations": kept, "last_analysis": report,
            })
            return self._window_observation_summary(kept, report)

    def record_window_observation(self, sha, opponent_slot, observed_rank,
                                  reward_card_id, played_card_ids):
        """Record ONE independent observation; never promote IDs/RANK/drops.

        The position 1–39 is structural and is NOT a proved runtime game ID.
        The source ISO must have the same SHA as the registered mod.
        """
        from dueltrace_window_observation import _parse_observation
        row = {
            "source": "manual_game_observation",
            "opponent_slot": opponent_slot,
            "observed_rank": observed_rank,
            "reward_card_id": reward_card_id,
            "played_card_ids": played_card_ids,
        }
        if _parse_observation(row) is None:
            raise ValueError("Informe posição 1–39, RANK, carta 1–722 e até 24 cartas distintas")
        if type(sha) is not str or not re.fullmatch(r"[a-f0-9]{64}", sha):
            raise ValueError("SHA da ISO inválido")
        with self._lock:
            entry = next((e for e in self.catalog.list()
                          if e.get("sha256") == sha), None)
            profile = self.catalog.profile_for(entry) if entry else None
            if not profile:
                raise ValueError("Perfil do mod não localizado")
            choices = self._structural_opponent_choices(profile)
            if not choices or opponent_slot not in {c["slot"] for c in choices}:
                raise ValueError("Selecione um dos 39 nomes extraídos desta ISO")
            path = self._window_observation_path(sha)
            if path.is_file() and path.stat().st_size > 128 * 1024:
                raise ValueError("Registro anterior excede o limite")
            previous = load_json(path, {})
            if previous and (not isinstance(previous, dict)
                             or previous.get("rom_sha256") != sha):
                raise ValueError("Registro anterior pertence a outra ISO")
            records = previous.get("observations", []) if isinstance(previous, dict) else []
            if not isinstance(records, list):
                raise ValueError("Registro anterior inválido")
            records = [r for r in records[-199:] if _parse_observation(r) is not None]
            # Fresh ISO bytes are read from disk. The profile's speculative
            # data cannot substitute for this independent local read.
            report = self._evaluate_window_records(sha, entry, profile, records + [row])
            atomic_json(path, {
                "schema": 1, "rom_sha256": sha,
                "observations": records + [row],
                "last_analysis": report,
            })
            return self._window_observation_summary(records + [row], report)

    def _observations_path(self, sha):
        if type(sha) is not str or not re.fullmatch("[0-9a-f]{64}",sha):
            raise ValueError("SHA da ISO inválido")
        return self.catalog.home / "rank_observations" / (sha+".json")

    def get_duel_evidence(self):
        """Apenas dados locais da ISO ativa, sem arquivo de jogo ou RAM bruta."""
        with self._lock:
            active,entry,profile=self._active()
            sha=active.get("sha256")
            if profile is None or not isinstance(sha,str):
                return rank_drop_report(None,[])
            raw=load_json(self._observations_path(sha),{})
            observations=(raw.get("observations",[]) if isinstance(raw,dict) else [])
            return rank_drop_report(profile,observations)

    def get_rank_comparison(self):
        """Resumo local da divergência entre previsão capturada e duelo manual."""
        with self._lock:
            active,_entry,profile=self._active()
            sha=active.get("sha256")
            if not profile or not isinstance(sha,str):
                return {"available":False,"status":"no_active_mod","cases":[]}
            saved=load_json(self._observations_path(sha),{})
            records=saved.get("observations",[]) if isinstance(saved,dict) else []
            return {"available":True,**compare_rank_observations(sha,records)}

    def record_duel_result(self, opponent_id, observed_rank, card_id,
                           observed_points=None, victory_type="unknown",
                           capture_id=None):
        """Registra recompensa e nota VISTAS pelo jogador, jamais auto-verificadas.

        A projeção do snapshot anterior não se torna verdade de treinamento:
        fica explicitamente marcada como previsão para futura comparação.
        """
        if capture_id is not None and (type(capture_id) is not str or
                not re.fullmatch(r"[0-9a-f-]{36}",capture_id)):
            raise ValueError("Identificador de captura inválido.")
        if type(victory_type) is not str or victory_type not in ("lp","deckout","other","unknown"):
            raise ValueError("Resultado de vitória inválido.")
        if type(opponent_id) is not int or not 1<=opponent_id<=39:
            raise ValueError("Selecione um oponente válido (1–39).")
        if type(card_id) is not int or not 1<=card_id<=722:
            raise ValueError("Informe o ID da carta recebida (1–722).")
        if type(observed_rank) is not str or len(observed_rank)>32:
            raise ValueError("RANK observado inválido.")
        if observed_points is not None and (type(observed_points) is not int
                                             or not 0<=observed_points<=300):
            raise ValueError("Pontuação observada inválida.")
        with self._lock:
            active,entry,profile=self._active()
            sha=active.get("sha256")
            if observed_rank not in available_ranks(sha):
                raise ValueError("RANK observado incompatível com esta ISO.")
            if not profile or not profile.get("supported_features",{}).get("drops"):
                raise ValueError("Carregue uma ISO com drops validados.")
            # Validação estrutural de todos os pesos antes de salvar relatos.
            catalog=get_drop_catalog(profile,limit=1)
            if not catalog["available"]:
                raise ValueError("Tabelas de drops não validadas para esta ISO.")
            if opponent_id not in {o["id"] for o in catalog["opponents"]}:
                raise ValueError("Oponente não identificado na ISO.")
            path=self._observations_path(sha)
            raw=load_json(path,{})
            observations=list(raw.get("observations",[])) if isinstance(raw,dict) else []
            if len(observations)>=500:
                observations=observations[-499:]
            capture=self._rank_pending_capture
            estimate=None
            if capture_id is not None:
                if (not isinstance(capture,dict) or capture["id"]!=capture_id
                        or capture["rom_sha256"]!=sha
                        or monotonic()-capture["at"]>600):
                    self._rank_pending_capture=None
                    raise ValueError("Captura expirou ou pertence a outro duelo/mod. Capture novamente.")
                estimate={"projected_score":capture["score"],
                          "projected_rank":capture["category"],
                          "counters":dict(capture["counters"]),
                          "capture_id":capture["id"],
                          "capture_source":"user_confirmed_lp_prediction",
                          "comparison_status":"projection_not_final"}
            observation={
                "duel_id":str(uuid4()),"rom_sha256":sha,
                "opponent_id":opponent_id,"observed_rank":observed_rank,
                "card_id":card_id,"observed_points":observed_points,
                "victory_type":victory_type,
                "recorded_at":datetime.now(timezone.utc).isoformat(),
                "source":"manual_game_observation",
                "rank_snapshot":estimate,
            }
            observations.append(observation)
            atomic_json(path,{"schema":1,"rom_sha256":sha,
                              "observations":observations})
            if capture_id is not None:
                self._rank_pending_capture=None  # uso único após salvar
            return rank_drop_report(profile,observations)

    def activate_mod(self, sha, acknowledge=False):
        if not isinstance(sha,str) or len(sha)!=64:
            raise ValueError("Identificador de mod inválido")
        if type(acknowledge) is not bool:
            raise ValueError("Confirmação inválida")
        self.catalog.activate(sha,acknowledge_uncertainty=acknowledge)
        self._fusion_cache_key=None
        self._alpha_bundle_key=None
        self._alpha_bundle_cache={}
        self._hand_suggestions_key=None
        self._hand_suggestions=None
        self._rank_calibration=None
        self._rank_auto_probe=None
        self._rank_legacy_trial=None
        self._rank_gap_started=None
        self._rank_lp_session=None
        self._rank_last_turns=None
        self._rank_last_snapshot=None
        self._rank_pending_capture=None
        self._rank_experimental_sha=None
        return self.get_state()

    def audit_mod_iso(self, sha):
        """Explicit local-only forensic run; never changes a registered mod."""
        if type(sha) is not str or not re.fullmatch(r"[a-f0-9]{64}",sha):
            raise ValueError("SHA de ISO inválido.")
        with self._lock:
            entry=next((e for e in self.catalog.list()
                        if e.get("sha256")==sha),None)
            if entry is None:
                raise ValueError("ISO não cadastrada.")
            source=entry.get("source_path")
            if type(source) is not str or not source:
                raise ValueError("Caminho da ISO cadastrada indisponível.")
            path=Path(source).resolve(strict=True)
            if path.suffix.lower() not in (".iso",".bin"):
                raise ValueError("Somente imagens ISO/BIN cadastradas são permitidas.")
            expected_size=entry.get("size")
            expected_mtime=entry.get("mtime_ns")
            before=path.stat()
            if (type(expected_size) is int and expected_size!=before.st_size
                    or type(expected_mtime) is int
                    and expected_mtime!=before.st_mtime_ns):
                raise ValueError(
                    "Imagem alterada desde a importação. Atualize dados primeiro.")
        from dueltrace_iso_forensic_lab import inspect_iso
        report=inspect_iso(path,sha)
        # A deliberate local persist, separate from cards/profiles/drop tables.
        target=(self.catalog.home/"iso_forensics"/(sha+".json"))
        atomic_json(target,report)
        return report

    def upload_iso_forensic(self, sha):
        """A separate explicit user action, not an extension of Live Diagnostics."""
        if type(sha) is not str or not re.fullmatch(r"[a-f0-9]{64}",sha):
            raise ValueError("SHA de ISO inválido.")
        with self._lock:
            entry=next((e for e in self.catalog.list()
                        if e.get("sha256")==sha),None)
            if entry is None:
                raise ValueError("ISO não cadastrada.")
            path=Path(entry.get("source_path") or "").resolve(strict=True)
            if path.suffix.lower() not in (".iso",".bin"):
                raise ValueError("Fonte não é uma ISO/BIN cadastrada.")
            from scanner_multiiso import sha256 as actual_sha256
            if actual_sha256(path)!=sha:
                raise ValueError("Imagem alterada. Audite novamente antes do envio.")
            report_file=self.catalog.home/"iso_forensics"/(sha+".json")
            report=load_json(report_file,{})
            if (not isinstance(report,dict)
                    or report.get("romFingerprint")!=sha[:12]
                    or report.get("exactSha256Matched") is not True
                    or report.get("fileSizeBytes")!=path.stat().st_size):
                raise ValueError("Relatório forense ausente ou incompatível.")
        # Only the sanitized report goes to the explicitly selected private
        # GitHub destination. Never transmit ROM, paths, art or recipes.
        return self._private_evidence_sync.upload_forensic(report)

    def compare_mod_layouts(self, baseline_sha):
        """Compare already scanned ISOs, never reading ROM bytes or paths out."""
        from dueltrace_iso_differential import (
            compare_structures, _load, MAX_COMPARISONS)
        if (type(baseline_sha) is not str or
                not re.fullmatch(r"[a-f0-9]{64}", baseline_sha)):
            raise ValueError("SHA da ISO de referência inválido.")
        with self._lock:
            entries = self.catalog.list()
            baseline_entry = next(
                (entry for entry in entries
                 if entry.get("sha256") == baseline_sha), None)
            if baseline_entry is None:
                raise ValueError("ISO de referência não cadastrada.")
            root = (self.catalog.home / "analises").resolve()

            def local_report(entry):
                profile = self.catalog.profile_for(entry)
                if not isinstance(profile, dict):
                    raise ValueError("Perfil ausente")
                folder = profile.get("scan_result_dir")
                if type(folder) is not str or not folder:
                    raise ValueError("Relatório ausente")
                resolved = Path(folder).resolve()
                if not resolved.is_relative_to(root):
                    raise ValueError("Caminho de relatório não autorizado")
                report = _load(resolved / "relatorio.json")
                if report.get("sha256") != entry.get("sha256"):
                    raise ValueError("SHA do relatório não corresponde à ISO")
                # Fusion evidence comes from a separate local extraction
                # pipeline, not scanner_multiiso.process(). Export only
                # counts and source kind; never actual recipes/card names.
                recipes = profile.get("fusion_recipes")
                recipes = recipes if isinstance(recipes, list) else []
                rows = [r for r in recipes if isinstance(r, dict)]
                review = profile.get("fusion_review")
                review = review if isinstance(review, dict) else {}
                report["fusion_profile_evidence"] = {
                    "inspected": True,
                    "count": min(len(rows), 100000),
                    "sevenConsistentBanks": (
                        review.get("matching_banks") == 7
                        and review.get("divergent_banks") is False
                        and review.get("bank_conflicts") == 0),
                    "manuallyObserved": any(
                        r.get("validation") == "observada_manualmente_no_jogo"
                        for r in rows),
                }
                return report

            baseline = local_report(baseline_entry)
            others = []
            skipped = 0
            for entry in entries:
                if entry.get("sha256") == baseline_sha:
                    continue
                if len(others) >= MAX_COMPARISONS:
                    skipped += 1
                    continue
                try:
                    others.append(local_report(entry))
                except (OSError, ValueError, TypeError):
                    skipped += 1
            result = compare_structures(baseline, others)
            result["comparedProfiles"] = len(others)
            result["skippedProfiles"] = skipped
            return result

    def get_mod_scan_diagnostic(self, sha, with_ollama=False):
        """Diagnóstico legível de uma ISO sem transmitir arquivos completos.

        Ollama só analisa metadados quando solicitado. Nenhum candidato vira
        tabela verificada ou altera o mod automaticamente.
        """
        if (type(sha) is not str or not re.fullmatch(r"[a-f0-9]{64}",sha)
                or type(with_ollama) is not bool):
            raise ValueError("Identificador/solicitação de diagnóstico inválido.")
        with self._lock:
            entry=next((x for x in self.catalog.list()
                        if x.get("sha256")==sha),None)
            if not entry:
                raise ValueError("ISO não encontrada na Biblioteca de Mods.")
            profile=self.catalog.profile_for(entry)
            if not isinstance(profile,dict):
                raise ValueError("Perfil local indisponível.")
            scan_dir=profile.get("scan_result_dir")
            root=(self.catalog.home/"analises").resolve()
            if not isinstance(scan_dir,str) or not scan_dir:
                raise ValueError("Nenhuma análise local encontrada.")
            folder=Path(scan_dir).resolve()
            if not folder.is_relative_to(root):
                raise ValueError("Caminho de análise fora da pasta autorizada.")
            meta=load_json(folder/"relatorio.json",{})
            diagnosis=diagnose_layout(meta,profile)
            from dueltrace_forensic_ai import numeric_evidence
            from dueltrace_opponent_forensics import summarize_alternative_layouts
            diagnosis["opponentForensics"]=numeric_evidence(meta)
            diagnosis["opponentLayoutSearch"]=summarize_alternative_layouts(meta)
            diagnosis["romSha"]=sha
            diagnosis["ai"]={"state":"nao_solicitada","note":"Use o diagnóstico Ollama se desejar hipóteses."}
            diagnosis["forensic_ai"]={"state":"nao_solicitada",
                                     "note":"Revisão binária local opcional, sem promover dados."}
            if with_ollama:
                # Revisor numérico adicional: somente contagens, sem ISO,
                # nomes, hashes ou offsets enviados ao modelo.
                from dueltrace_forensic_ai import review_with_ollama
                forensic=review_with_ollama(meta,timeout=25)
                diagnosis["forensic_ai"]={
                    "state":forensic["status"],
                    "cause":forensic["cause"],
                    "actions":forensic["actions"],
                    "inGameVerified":False,
                    "mayActivate":False
                }
                source=Path(entry.get("source_path") or "").resolve(strict=True)
                if not source.is_file():
                    raise ValueError("ISO original não disponível para análise.")
                result=MultiModIntelligence(self.catalog).inspect(
                    source,use_ollama=True)
                diagnosis["ai"]={
                    "state":result.get("ai","nao_iniciada"),
                    "message":str(result.get("ai_message") or "")[:220],
                }
                ai_report=result.get("ai_report_path")
                if isinstance(ai_report,str):
                    file=Path(ai_report).resolve()
                    safe_dir=(self.catalog.home/"investigacoes").resolve()
                    if file.is_relative_to(safe_dir):
                        suggestion=load_json(file,{})
                        raw_summary=str(suggestion.get("resumo") or "")[:1200]
                        # O Ollama pode inventar que o jogo não contém cartas
                        # quando, na verdade, só falhou o extrator. Nunca
                        # mostrar uma conclusão factual do LLM para uma ISO
                        # cujo layout sequer foi reconhecido.
                        if diagnosis["state"]!="estrutura_reconhecida":
                            diagnosis["ai"]["resumo"]=(
                                "O scanner não conseguiu reconhecer as tabelas "
                                "desta ISO. Isso NÃO comprova ausência de cartas, "
                                "oponentes, fusões ou drops. O conteúdo do "
                                "executável e dos recursos permanece desconhecido.")
                            diagnosis["ai"]["summarySuppressed"]=bool(raw_summary)
                            diagnosis["ai"]["note"]=(
                                "Texto conclusivo de IA omitido por falta de "
                                "evidência binária; as sugestões abaixo são "
                                "hipóteses e não dados verificados.")
                        else:
                            diagnosis["ai"]["resumo"]=raw_summary
                        raw_priorities=suggestion.get("prioridades",[])
                        diagnosis["ai"]["prioridades"]=[
                            str(x)[:250] for x in raw_priorities[:6]
                            if isinstance(x,str)] if isinstance(raw_priorities,list) else []
                        diagnosis["ai"]["alertas"]=[
                            str(x)[:200] for x in suggestion.get("alertas",[])[:6]
                            if isinstance(x,str)]
            return diagnosis

    def scan_sources(self, sha):
        """Releia a ISO local e seus WA_MRG/SLUS; não envie dados à nuvem."""
        if type(sha) is not str or len(sha)!=64 or any(
                ch not in "0123456789abcdef" for ch in sha):
            raise ValueError("Identificador SHA-256 inválido")
        with self._lock:
            entry=next((e for e in self.catalog.list() if e.get("sha256")==sha),None)
            if not entry or not entry.get("source_path"):
                raise ValueError("Mod não cadastrado")
            source=Path(entry["source_path"]).resolve(strict=True)
            if not source.is_file() or source.suffix.lower() not in (".bin",".iso"):
                raise ValueError("Imagem original não encontrada")
            # Validar ANTES de reescrever registro ou perfil: uma ISO substituída
            # não pode destruir o cadastro antigo quando o SHA mudou.
            from scanner_multiiso import sha256 as hash_image
            if hash_image(source)!=sha:
                raise RuntimeError("ISO modificada desde o cadastro; o perfil original foi preservado")
            updated=self.catalog.analyse(source,with_art=True,force=True)
            if updated["sha256"]!=sha:
                raise RuntimeError("A imagem da ISO mudou desde o último cadastro")
            self._fusion_cache_key=None
            self._hand_suggestions_key=None
            self._hand_suggestions=None
            self._cross_mod_cards_cache_key=None
            self._cross_mod_cards_cache=None
            self._rank_calibration=None
            self._rank_legacy_trial=None
            self._rank_gap_started=None
            self._rank_lp_session=None
            # Se Ollama estiver instalado, consultar automaticamente
            # hipóteses locais a partir da análise; offline não impede scanner.
            analysis=MultiModIntelligence(self.catalog).inspect(source,use_ollama=True)
            profile=self.catalog.profile_for(updated)
            graphic=(profile or {}).get("graphic_assets",{})
            provenance=(profile or {}).get("descriptions_provenance",{})
            meta=load_json(Path(profile.get("scan_result_dir") or "")/
                           "relatorio.json",{}) if profile else {}
            diagnostic=diagnose_layout(meta,profile)
            return {
                "sha256":sha,
                "cardCount":len((profile or {}).get("cards",[]))
                    if (profile or {}).get("supported_features",{}).get("cards") else 0,
                "candidateCardCount":max(0,min(722,int((profile or {}).get("candidate_catalogue",{}).get("cards",0))))
                    if isinstance((profile or {}).get("candidate_catalogue"),dict) else 0,
                "artCount":graphic.get("art_count",0),
                "thumbnailCount":graphic.get("thumbnails",0),
                "framedCards":graphic.get("composed_cards",0),
                "opponentCount":len((profile or {}).get("opponents",[]))
                    if (profile or {}).get("supported_features",{}).get("opponents") else 0,
                "opponentCandidateCount":(
                    (profile or {}).get("opponent_layout_discovery",{})
                    .get("candidateOpponentCount",0)),
                "opponentDiagnosticReason":str(
                    (profile or {}).get("opponent_layout_discovery",{})
                    .get("reason",""))[:220],
                "dropEntries":len((profile or {}).get("drops",[]))
                    if (profile or {}).get("supported_features",{}).get("drops") else 0,
                "frameStyles":graphic.get("frames",0),
                "descriptionCount":provenance.get("descriptions_attached",0),
                "effectTexts":provenance.get("effect_descriptions_attached",0),
                "investigation":analysis.get("state","sem_relatorio"),
                "diagnostic":diagnostic,
                "aiState":analysis.get("ai","desativada"),
                "aiMessage":str(analysis.get("ai_message") or "")[:220],
                "status":("Dados reconhecidos por validações estruturais."
                          if diagnostic["automaticExtractionComplete"] else
                          "Layout não reconhecido integralmente; consulte o diagnóstico, "
                          "não interprete os zeros como ausência de conteúdo."),
            }

    def import_iso(self):
        if self._file_picker is None:
            raise RuntimeError("Seleção de arquivo disponível somente no aplicativo Windows.")
        files=self._file_picker("iso")
        if not files:
            return {"cancelled":True}
        image=Path(files[0]).expanduser().resolve(strict=True)
        if image.suffix.lower() not in (".iso",".bin"):
            raise ValueError("Selecione ISO ou BIN.")
        with self._lock:
            entry=self.catalog.analyse(image,with_art=True)
            intelligence=MultiModIntelligence(self.catalog)
            report=intelligence.inspect(image)
            return {"cancelled":False,"mod":self._mod(entry),
                    "investigation":report.get("state","não concluída")}

    def configure_epsxe(self):
        if self._file_picker is None:
            raise RuntimeError("Seletor disponível somente no Windows.")
        files=self._file_picker("epsxe")
        if not files:
            return {"cancelled":True}
        from epsxe_launcher import command_for_epsxe
        path=Path(files[0]).resolve(strict=True)
        if not path.is_file() or path.suffix.lower()!=".exe" or "epsxe" not in path.stem.casefold():
            raise ValueError("Selecione o executável ePSXe.exe.")
        from auto_mods import atomic_json
        with self._lock:
            settings=load_json(self.settings_path,{})
            settings["epsxe_executable"]=str(path)
            atomic_json(self.settings_path,settings)
        return {"cancelled":False,"configured":True}

    def start_game(self):
        with self._lock:
            active,entry,profile=self._active()
            if not profile:
                raise ValueError("Ative o perfil do mod antes de iniciar.")
            settings=load_json(self.settings_path,{})
            executable=settings.get("epsxe_executable")
            if not executable:
                raise ValueError("Configure o caminho do ePSXe.exe.")
            if self._process is not None and self._process.poll() is None:
                return {"started":False,"status":"ePSXe já iniciado por DUELTRACE"}
            self._process=launch_epsxe(self.catalog,executable,active["sha256"])
            self._launched_rom_sha=active["sha256"]
            return {"started":True,"status":"ePSXe iniciado com o mod selecionado"}
