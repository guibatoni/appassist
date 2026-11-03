"""Bridge local do design v0 para o motor Python do DUELTRACE.

Não envia ISO, cartas, RAM nem chaves para a nuvem. Objetos JSON contêm
somente dados do perfil validado e deixam explícita a origem dos efeitos.
O JavaScript da interface acessa os métodos via pywebview.api, não por uma
API HTTP aberta para comandos. As imagens são lidas localmente.
"""
from __future__ import annotations

import threading
from pathlib import Path

from auto_mods import ModCatalog, load_json
from mod_autopilot import ModAutopilot, profile_summary
from dueltrace_intelligence import MultiModIntelligence
from dueltrace_live_hand import (read_hand_from_epsxe, build_fusion_index,
                                 suggest_hand_pairs)
from dueltrace_fusion_planner import plan_fusion_chains
from epsxe_launcher import launch_epsxe


class DueltraceWebBridge:
    def __init__(self, catalog: ModCatalog | None = None, *,
                 file_picker=None, ram_reader=None):
        self.catalog = catalog or ModCatalog()
        self._file_picker = file_picker
        self._ram_reader = ram_reader or read_hand_from_epsxe
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
            "requiresReview":summary.get("requires_review",True),
            "verified":summary.get("validated",{}),
        }

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
            chains=plan_fusion_chains(ids,index,cards,limit=16)
            return {"ready":True,"status":sample.get("status","Mão identificada"),
                    "hand":enriched,"pairs":pairs,
                    "chains":chains["routes"],
                    "chainsComplete":chains["complete"]}

    def get_fusions(self, query="", offset=0, limit=100):
        if type(query) is not str or len(query)>100:
            raise ValueError("Consulta inválida")
        if type(offset) is not int or offset<0 or offset>1000000:
            raise ValueError("Página inválida")
        if type(limit) is not int or not 1<=limit<=150:
            raise ValueError("Limite inválido")
        with self._lock:
            active,entry,profile=self._active()
            if not profile or not profile.get("supported_features",{}).get("fusions"):
                return {"total":0,"offset":0,"rows":[]}
            cards={c["id"]:c for c in self._cards(profile)}
            q=query.strip().casefold()
            rows=[]
            total=0
            for item in profile.get("fusion_recipes",[]):
                try:
                    a,b,result=(int(item[k]) for k in ("a","b","result"))
                except (KeyError,ValueError,TypeError):
                    continue
                if not all(1<=v<=722 for v in (a,b,result)):
                    continue
                names=[cards.get(cid,{}).get("name") or f"Carta #{cid}"
                       for cid in (a,b,result)]
                if q and not any(q in text.casefold() or q==str(cid)
                                 for text,cid in zip(names,(a,b,result))):
                    continue
                if total>=offset and len(rows)<limit:
                    rows.append({"a":a,"b":b,"result":result,
                                 "nameA":names[0],"nameB":names[1],
                                 "nameResult":names[2],
                                 "atk":cards.get(result,{}).get("atk"),
                                 "source":str(item.get("validation") or "Não informada")})
                total+=1
            return {"total":total,"offset":offset,"rows":rows}

    def activate_mod(self, sha, acknowledge=False):
        if not isinstance(sha,str) or len(sha)!=64:
            raise ValueError("Identificador de mod inválido")
        if type(acknowledge) is not bool:
            raise ValueError("Confirmação inválida")
        self.catalog.activate(sha,acknowledge_uncertainty=acknowledge)
        self._fusion_cache_key=None
        return self.get_state()

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
