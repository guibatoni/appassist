"""Bridge local do design v0 para o motor Python do DUELTRACE.

Não envia ISO, cartas, RAM nem chaves para a nuvem. Objetos JSON contêm
somente dados do perfil validado e deixam explícita a origem dos efeitos.
O JavaScript da interface acessa os métodos via pywebview.api, não por uma
API HTTP aberta para comandos. As imagens são lidas localmente.
"""
from __future__ import annotations

import threading
import json
import re
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

from auto_mods import ModCatalog, load_json, atomic_json
from mod_autopilot import ModAutopilot, profile_summary
from dueltrace_intelligence import MultiModIntelligence
from dueltrace_live_hand import (read_hand_from_epsxe, build_fusion_index,
                                 suggest_hand_pairs)
from dueltrace_fusion_planner import plan_fusion_chains
from dueltrace_rank_live import (model_available, read_rank_candidate,
                                 read_rank_from_verified_binding, project_lp_win_rank)
from dueltrace_rank_profile_live import (
    validate_live_rank_binding, project_rank_for_mod, x15_compatible_runtime
)
from epsxe_launcher import launch_epsxe
from dueltrace_drops import get_drop_catalog
from dueltrace_drop_rank_evidence import rank_drop_report
from dueltrace_rank_system import available_ranks,rank_system,rank_label_for_existing_score
from dueltrace_mips_duel_trace import inspect_duel_mips_trace, MAX_TRACE_BYTES
from dueltrace_rank_memory_trace import inspect_rank_memory_trace
from dueltrace_rank_export import build_rank_evidence_report
from dueltrace_rank_duel_verification import compare_rank_observations
from dueltrace_library_sort import validate_sort,matches_type,sort_key
from dueltrace_update_checker import (
    check_for_updates, open_official_releases, fetch_stable_release, CURRENT_VERSION
)
from dueltrace_signed_install import (
    trusted_installer_ready, select_signed_installer, install_new_release
)


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
        self._rank_last_turns = None
        self._rank_last_snapshot = None
        self._rank_pending_capture = None
        self._process = None
        self._lock = threading.RLock()
        self._fusion_cache_key = None
        self._fusion_cache = {}
        self.settings_path = self.catalog.home / "dueltrace_desktop_settings.json"

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

    def _mod(self, entry):
        profile = self.catalog.profile_for(entry)
        summary = profile_summary(entry, profile)
        return {
            "sha256":entry.get("sha256",""),
            "name":entry.get("file_name") or summary.get("name") or "Mod local",
            "level":entry.get("level","desconhecido"),
            "cards":summary.get("cards_total",0),
            "fusions":summary.get("fusion_count",0),
            "effects":summary.get("effect_count",0),
            "descriptions":len([c for c in (profile or {}).get("cards",[])
                                if c.get("description_text") and c.get("description_source")]),
            "framedCards":(profile or {}).get("graphic_assets",{}).get("composed_cards",0),
            "frameStyles":(profile or {}).get("graphic_assets",{}).get("frames",0),
            "opponents":len((profile or {}).get("opponents",[]))
                if (profile or {}).get("supported_features",{}).get("opponents") else 0,
            "dropEntries":len((profile or {}).get("drops",[]))
                if (profile or {}).get("supported_features",{}).get("drops") else 0,
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
        """Detecta Preview e release estável; instalador somente com confiança."""
        status=check_for_updates()
        if status.get("status")!="update_available":
            status["automaticInstallReason"]=(
                "Não há release estável mais recente. As builds Preview "
                "continuam sem instalação automática por segurança.")
        elif not trusted_installer_ready():
            status["automaticInstallReason"]=(
                "Esta instalação não possui assinatura Authenticode "
                "verificada. A atualização automática exige uma versão "
                "estável assinada previamente instalada.")
        else:
            try:
                release=fetch_stable_release()
                candidate=select_signed_installer(release,CURRENT_VERSION)
                if candidate is not None:
                    status["automaticInstallReady"]=True
                    status["automaticInstallReason"]=(
                        "Instalador oficial com hash publicado; a assinatura "
                        "será comparada antes de executar.")
            except (OSError,ValueError,TypeError):
                status["automaticInstallReason"]=(
                    "A release mais recente ainda não possui instalador "
                    "com metadados de integridade verificáveis.")
        return status

    def install_signed_update(self):
        """Somente após autorização explícita do usuário na WebUI."""
        return install_new_release(data_home=self.catalog.home)

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
                "activeName":entry.get("file_name") if entry and profile else None,
                "mods":mods,
                "cards":self._cards(profile),
                "fusionCount":len(profile.get("fusion_recipes",[]))
                    if profile and profile.get("supported_features",{}).get("fusions")
                    else 0,
                "epsxeConfigured":bool(settings.get("epsxe_executable")),
                "warning":"O DUELTRACE não confirma automaticamente qual ISO o ePSXe abriu.",
            }

    def _fusion_index(self, sha, profile):
        profile_path=Path(self.catalog.home)/"profiles"/sha[:16]/"profile.json"
        try:
            stamp=profile_path.stat().st_mtime_ns
        except OSError:
            stamp=0
        key=(sha,stamp)
        if self._fusion_cache_key != key:
            recipes=(profile or {}).get("fusion_recipes",[])
            allowed=bool((profile or {}).get("supported_features",{}).get("fusions"))
            self._fusion_cache=build_fusion_index(recipes if allowed else [])
            self._fusion_cache_key=key
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
            pairs=suggest_hand_pairs(ids,index,cards,limit=24)
            chains=plan_fusion_chains(ids,index,cards,min_cards=2,max_cards=5,limit=16)
            return {"ready":True,"status":sample.get("status","Mão identificada"),
                    "hand":enriched,"pairs":pairs,
                    "chains":chains["routes"],
                    "chainsComplete":chains["complete"]}

    def _rank_sample(self):
        active,entry,profile=self._active()
        sha=active.get("sha256") if profile else None
        binding=validate_live_rank_binding(profile)
        if binding is None and not model_available(sha) and not x15_compatible_runtime(profile):
            self._rank_calibration=None
            self._rank_pending_capture=None
            return None,sha,{"state":"unsupported","ready":False,
                "status":"Tabela e/ou rotina de RANK ainda não calibradas para esta ISO. "
                         "A leitura MIPS estática não autoriza inferir endereços RAM.",
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
            self._rank_calibration=None
            self._rank_last_turns=None
            # Captura explícita sobrevive à tela de resultado/transição,
            # mesmo que o registro RAM desapareça. Ainda expira em 10 min.
            if self._rank_pending_capture is not None:
                self._rank_pending_capture["ram_gap"]=True
            return None,sha,{"state":"unavailable","ready":False,
                "status":sample.get("status","Leitura indisponível"),
                "score":None,"category":None,"counters":None}
        return sample,sha,None

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
                if (self._rank_last_turns[0]==(sha,pid)
                        and self._rank_pending_capture is not None):
                    self._rank_pending_capture["returned_to_menu"]=True
                self._rank_calibration=None  # novo duelo ou contador reiniciado
                self._rank_last_snapshot=None
            self._rank_last_turns=((sha,pid),turns)
            calibrated=(self._rank_calibration is not None and
                self._rank_calibration["sha"]==sha and
                self._rank_calibration["pid"]==pid and
                monotonic()-self._rank_calibration["at"]<7200)
            if not calibrated:
                self._rank_calibration=None
                return {"ready":False,"state":"needs_lp_confirmation",
                    "status":"Confirme os LP exibidos pelo jogo neste duelo para habilitar a projeção.",
                    "candidateLp":counters[binding["life_points_criterion"]] if binding else counters["remaining_lp"],"score":None,
                    "category":None,"counters":None}
            result=(project_rank_for_mod(profile,counters)
                    if binding else project_lp_win_rank(counters))
            # Sem modificar soma, tabelas de pontos, contadores ou bônus.
            display_category=rank_label_for_existing_score(sha,result["score"])
            visible_counters=dict(counters)
            if binding:
                visible_counters["turns"]=counters[binding["turns_criterion"]]
                visible_counters["remaining_lp"]=counters[binding["life_points_criterion"]]
            compatible=(binding is None and not model_available(sha) and
                        x15_compatible_runtime(profile))
            status=("Projeção usando SLUS e tabela RANK idênticos ao X15; "
                    "LP confirmado nesta sessão, mas o resultado do duelo "
                    "ainda exige comparação."
                    if compatible else
                    "Projeção se vencer por LP; resultado e mapeamento RAM "
                    "não verificados no jogo.")
            self._rank_last_snapshot={
                "rom_sha256":sha,"pid":pid,"monotonic_at":monotonic(),
                "score":result["score"],"category":display_category,
                "counters":visible_counters.copy(),
            }
            return {"ready":True,"state":"provisional",
                    "status":status,
                    "candidateLp":counters[binding["life_points_criterion"]] if binding else counters["remaining_lp"],
                    "score":result["score"],"category":display_category,
                    "counters":visible_counters,"breakdown":result["breakdown"],
                    "model":result["model"],"rankSystem":rank_system(sha),
                    "final":False}


    def capture_rank_prediction(self):
        """Congela uma previsão de vitória LP com clique explícito no duelo.

        Não confirma o resultado do jogo, nem reconhece qual ISO o ePSXe abriu.
        Só compara com o resultado manual informado posteriormente.
        """
        with self._lock:
            current=self.get_rank()
            snap=self._rank_last_snapshot
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
                self._rank_last_snapshot=None
                self._rank_pending_capture=None
                return {"ready":False,"state":"lp_mismatch",
                    "status":"LP do jogo divergentes do candidato RAM. Contador não habilitado.",
                    "candidateLp":sample["counters"][lp_key],
                    "score":None,"category":None,"counters":None}
            self._rank_calibration={"sha":sha,"pid":sample["pid"],"at":monotonic()}
            self._rank_last_turns=((sha,sample["pid"]),sample["counters"][turns_key])
            return self.get_rank()

    def get_fusions(self, query="", offset=0, limit=100,
                    sort="id", card_type=""):
        """Filtro aplicado ao RESULTADO da fusão e antes da paginação."""
        if type(query) is not str or len(query)>100:
            raise ValueError("Consulta inválida")
        if type(offset) is not int or offset<0 or offset>1000000:
            raise ValueError("Página inválida")
        if type(limit) is not int or not 1<=limit<=150:
            raise ValueError("Limite inválido")
        validate_sort(sort,card_type)
        with self._lock:
            active,entry,profile=self._active()
            if not profile or not profile.get("supported_features",{}).get("fusions"):
                return {"total":0,"offset":offset,"rows":[]}
            cards={c["id"]:c for c in self._cards(profile)}
            q=query.strip().casefold()
            rows=[]
            for item in profile.get("fusion_recipes",[]):
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
                if q and not any(q in text.casefold() or q==str(cid)
                                 for text,cid in zip(names,(a,b,result))):
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
            return {"total":total,"offset":offset,"rows":rows[offset:offset+limit]}

    def get_drops(self, opponent_id=0, group="", query="", offset=0, limit=36,
                  sort="id", card_type="", rank=""):
        """Consulta exclusivamente tabelas validadas do perfil ISO ativo."""
        with self._lock:
            _active, _entry, profile = self._active()
            return get_drop_catalog(
                profile, opponent_id=opponent_id, group=group,
                query=query, offset=offset, limit=limit,
                sort=sort,card_type=card_type,rank=rank)

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
            if not report["available"]:
                return {"cancelled":False,**report}
            result={
                "record_id":str(uuid4()),
                "duel_id":duel_id,
                "created_at":datetime.now(timezone.utc).isoformat(),
                "source":"trace_exportado_do_emulador",
                "status":report["status"],
                "executionEvidence":report["executionEvidence"],
                "executedCandidates":report["executedCandidates"],
                "instructionSamples":report["instructionSamples"],
                "distinctPCs":report["distinctPCs"],
                "rankRoutineConfirmed":False,
                "traceSha256":report["traceSha256"],
                "rankTableEvidence":table_evidence,
                "note":report["note"],
            }
            dest=self._trace_results_path(sha)
            prior=load_json(dest,{})
            records=list(prior.get("records",[])) if isinstance(prior,dict) else []
            records.append(result)
            atomic_json(dest,{"schema":1,"rom_sha256":sha,"records":records[-50:]})
            return {"cancelled":False,**result}

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
        self._rank_calibration=None
        self._rank_last_turns=None
        self._rank_last_snapshot=None
        self._rank_pending_capture=None
        return self.get_state()

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
            self._rank_calibration=None
            analysis=MultiModIntelligence(self.catalog).inspect(source,use_ollama=False)
            profile=self.catalog.profile_for(updated)
            graphic=(profile or {}).get("graphic_assets",{})
            provenance=(profile or {}).get("descriptions_provenance",{})
            return {
                "sha256":sha,
                "artCount":graphic.get("art_count",0),
                "thumbnailCount":graphic.get("thumbnails",0),
                "framedCards":graphic.get("composed_cards",0),
                "opponentCount":len((profile or {}).get("opponents",[]))
                    if (profile or {}).get("supported_features",{}).get("opponents") else 0,
                "dropEntries":len((profile or {}).get("drops",[]))
                    if (profile or {}).get("supported_features",{}).get("drops") else 0,
                "frameStyles":graphic.get("frames",0),
                "descriptionCount":provenance.get("descriptions_attached",0),
                "effectTexts":provenance.get("effect_descriptions_attached",0),
                "investigation":analysis.get("state","sem_relatorio"),
                "status":"Análise local de WA_MRG.MRG e SLUS_014.11 concluída.",
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
            return {"started":True,"status":"ePSXe iniciado com o mod selecionado"}
