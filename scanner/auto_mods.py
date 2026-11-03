"""Detector automático e catálogo local de mods — não modifica a ROM.

Detecta imagens novas na pasta selecionada, gera perfis locais e diferencia
dados extraídos/validados de regras ainda desconhecidas.

Este módulo não usa um LLM. A 'inteligência' consiste em reconhecimento de
assinaturas, parsers de estrutura, verificações cruzadas e perfis revisáveis.
"""
from __future__ import annotations

import json
import hashlib
import os
import queue
import threading
import time
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from importador_perfis import import_rom
from scanner_multiiso import X15_SHA, ART_PARSER_REVISION
from card_catalog import effect_sidecar_path

EXTENSIONS = frozenset({".iso", ".bin"})
REGISTRY_FILE = "registro_mods.json"
ACTIVE_FILE = "perfil_ativo.json"


def data_home() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return root / "ForbiddenMemoriesMultiMod"


def atomic_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return fallback


def report_level(profile: dict) -> str:
    """Classificação conservadora: apenas o hash exato libera recursos X15."""
    verified = profile.get("verified", {})
    if profile.get("rom_sha256", "").lower() == X15_SHA.lower():
        if (verified.get("cartas") == "verificado"
                and verified.get("oponentes") == "verificado"
                and verified.get("tabelas_drops") == "verificado"):
            return "conhecido_validado"
    if (verified.get("cartas") == "verificado"
            or verified.get("oponentes") == "verificado"
            or verified.get("tabelas_drops") == "verificado"):
        return "parcial_revisar"
    return "desconhecido"


def supported_for_runtime(profile: dict) -> dict:
    """Nunca inventa ranking/fusões nem aproveita dados X15 por semelhança."""
    flags = profile.get("supported_features", {})
    known = profile.get("rom_sha256", "").lower() == X15_SHA.lower()
    return {
        "ids_e_lp": True,  # condicionado à validação da leitura RAM pelo aplicativo
        "nomes_cartas": bool(flags.get("cards")),
        "artes": bool(flags.get("art")),
        "oponentes": bool(flags.get("opponents")),
        "drops_brutos": bool(flags.get("drops")),
        "rank": known and bool(flags.get("ranks")),
        "pontuacao": known and bool(flags.get("scoring")),
        "fusoes": bool(flags.get("fusions")),
        "categorias": bool(flags.get("cards") and flags.get("categories")),
        "efeitos": bool(flags.get("cards") and flags.get("effects")),
    }


class ModCatalog:
    """Operações locais de persistência. Nenhuma chamada à rede."""
    def __init__(self, home: Path | None = None):
        self.home = Path(home) if home else data_home()
        self.home.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.home / REGISTRY_FILE
        self.active_file = self.home / ACTIVE_FILE
        self._lock = threading.RLock()

    def list(self) -> list[dict]:
        with self._lock:
            payload = load_json(self.registry_file, {"entries": []})
            return list(payload.get("entries", []))

    def lookup(self, path: Path) -> dict | None:
        # Resolve também aliases Windows 8.3 (RUNNER~1) e diferenças de caixa,
        # evitando descartar revisões manuais ao reescanear a mesma imagem.
        target=os.path.normcase(str(Path(path).expanduser().resolve()))
        return next((row for row in self.list()
                     if row.get("source_path")
                     and os.path.normcase(str(Path(row["source_path"]).resolve())) == target),None)

    def profile_for(self, entry: dict) -> dict | None:
        path = Path(entry.get("profile_path", ""))
        if not path.is_file() or not path.resolve().is_relative_to(self.home.resolve()):
            return None
        profile = load_json(path, {})
        if profile.get("rom_sha256") != entry.get("sha256"):
            return None
        return profile

    def analyse(self, path: Path, with_art: bool = False, progress=None,
                *, force: bool = False) -> dict:
        path = Path(path).resolve(strict=True)
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            raise ValueError("Selecione uma imagem .bin ou .iso")
        before = path.stat()
        if before.st_size < 100_000:
            raise ValueError("Arquivo pequeno demais para uma imagem de jogo")
        effect_file = effect_sidecar_path(path)
        try:
            sidecar_stat = effect_file.stat()
            effect_signature = (sidecar_stat.st_size, sidecar_stat.st_mtime_ns)
        except OSError:
            effect_signature = (0, 0)
        old = self.lookup(path)
        previous_profile=self.profile_for(old) if old else None
        if (not force and old and old.get("size") == before.st_size
                and old.get("mtime_ns") == before.st_mtime_ns
                and tuple(old.get("effects_manifest_signature", ())) == effect_signature):
            profile=self.profile_for(old) or {}
            if not with_art or profile.get("supported_features", {}).get("art"):
                return dict(old)
            scan_dir=profile.get("scan_result_dir")
            meta=load_json(Path(scan_dir) / "relatorio.json", {}) if scan_dir else {}
            # Não reescanear toda a ISO a cada abertura após uma tentativa
            # sem sucesso. Nova revisão ou 'Reanalisar' invalida este cache.
            if (meta.get("art_requested") is True
                    and meta.get("art_parser_revision") == ART_PARSER_REVISION):
                return dict(old)

        profile, profile_path = import_rom(path, self.home, art=with_art, progress=progress)
        # Reanálises não podem apagar confirmações individuais feitas em duelo.
        # O catálogo estrutural é recalculado pela etapa de investigação.
        if (previous_profile and previous_profile.get("rom_sha256")==profile.get("rom_sha256")
                and profile.get("verified",{}).get("cartas")=="verificado"):
            manual=[dict(row) for row in previous_profile.get("fusion_recipes",[])
                    if isinstance(row,dict)
                    and row.get("validation")=="observada_manualmente_no_jogo"]
            if manual:
                profile["fusion_recipes"]=manual
                profile["supported_features"]["fusions"]=True
                profile["verified"]["fusoes"]=f"parcial_usuario_{len(manual)}"
                profile["fusion_review"]={
                    "status":"confirmacoes_manuais_preservadas_aguardando_reanalise",
                    "rom_sha256":profile["rom_sha256"],
                    "in_game_individually_verified":len(manual),
                }
                atomic_json(profile_path,profile)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError("Arquivo alterado durante a leitura; análise descartada")

        entry = {
            "source_path": str(path),
            "file_name": path.name,
            "size": after.st_size,
            "mtime_ns": after.st_mtime_ns,
            "effects_manifest_signature": list(effect_signature),
            "sha256": profile["rom_sha256"],
            "profile_path": str(profile_path.resolve()),
            "level": report_level(profile),
            "verified": profile.get("verified", {}),
            "features": supported_for_runtime(profile),
            "analysed_at": datetime.now(timezone.utc).isoformat(),
            "approved": False,
        }
        with self._lock:
            old_entries = load_json(self.registry_file, {"entries": []}).get("entries", [])
            same_rom = [e for e in old_entries if e.get("sha256") == entry["sha256"]]
            # Usuário aprovou a assinatura; não cancelar aprovação ao mover arquivo.
            if same_rom:
                entry["approved"] = bool(same_rom[0].get("approved", False))
            new_entries = [e for e in old_entries
                           if e.get("source_path") != str(path) and e.get("sha256") != entry["sha256"]]
            new_entries.append(entry)
            atomic_json(self.registry_file, {"schema": 1, "entries": new_entries})
        return entry

    def activate(self, sha256: str, *, acknowledge_uncertainty: bool = False) -> dict:
        with self._lock:
            entries = self.list()
            entry = next((e for e in entries if e["sha256"] == sha256), None)
            if entry is None or self.profile_for(entry) is None:
                raise ValueError("Perfil inexistente ou incompatível")
            if entry["level"] != "conhecido_validado" and not acknowledge_uncertainty:
                raise PermissionError("Confirme que o mod desconhecido foi revisado antes de ativar")
            if entry["level"] == "desconhecido":
                raise PermissionError("Estrutura não identificada: usar somente IDs/LP, sem catálogo")
            entry["approved"] = True
            atomic_json(self.registry_file, {"schema": 1, "entries": entries})
            active = {
                "sha256": entry["sha256"],
                "profile_path": entry["profile_path"],
                "features": entry["features"],
                "level": entry["level"],
                "activated_at": datetime.now(timezone.utc).isoformat(),
            }
            atomic_json(self.active_file, active)
            return active

    def confirm_fusion(self, rom_sha256: str, a: int, b: int, result: int) -> int:
        """Confirma UMA receita observada no jogo, nunca o banco inteiro.

        A seleção de uma hipótese não constitui validação. A interface deve
        pedir ao usuário o ID do resultado que ele observou em duelo real.
        """
        a,b,result=(int(a),int(b),int(result))
        if not all(1<=v<=722 for v in (a,b,result)):
            raise ValueError("ID fora do catálogo 1..722")
        with self._lock:
            entries=self.list()
            entry=next((e for e in entries if e.get("sha256")==rom_sha256),None)
            if not entry:
                raise ValueError("ISO não cadastrada")
            profile=self.profile_for(entry)
            if not profile:
                raise ValueError("Perfil inexistente ou inválido")
            path=Path(entry["profile_path"])
            if not path.is_file():
                raise ValueError("Perfil indisponível")
            verified=profile.get("verified",{})
            catalog=profile.get("cards",[])
            if verified.get("cartas")!="verificado" or len(catalog)!=722:
                raise ValueError("Cartas ainda não validadas para este mod")
            pending=self.home/"investigacoes"/(rom_sha256+".fusoes.json")
            report=load_json(pending,{})
            if (report.get("rom_sha256")!=rom_sha256
                    or not report.get("candidate_fingerprint")):
                raise ValueError("Relatório de fusões ausente, antigo ou incompatível com a ROM")
            proposed={tuple(int(c[k]) for k in ("a","b","result"))
                      for c in report.get("candidates",[])}
            if (a,b,result) not in proposed:
                raise ValueError("Receita não consta da análise da ISO selecionada")
            already=profile.setdefault("fusion_recipes",[])
            key=(min(a,b),max(a,b))
            for r in already:
                if (min(int(r["a"]),int(r["b"])),max(int(r["a"]),int(r["b"])))==key:
                    if int(r["result"])!=result:
                        raise ValueError("Fusão incompatível com outra já confirmada")
                    if r.get("validation")!="observada_manualmente_no_jogo":
                        # Uma revisão em lote pode depois receber confirmação
                        # mais forte ao observar esta receita no próprio jogo.
                        r["validation"]="observada_manualmente_no_jogo"
                        review=profile.get("fusion_review")
                        if isinstance(review,dict):
                            review["in_game_individually_verified"]=sum(
                                item.get("validation")=="observada_manualmente_no_jogo"
                                for item in already
                            )
                        atomic_json(path,profile)
                        active=load_json(self.active_file,{})
                        if active.get("sha256")==rom_sha256:
                            active["fusion_revision"]=int(active.get("fusion_revision",0))+1
                            atomic_json(self.active_file,active)
                    return len(already)
            already.append({"a":a,"b":b,"result":result,
                            "validation":"observada_manualmente_no_jogo",
                            "fusion_candidate_fingerprint":report["candidate_fingerprint"]})
            profile["supported_features"]["fusions"]=True
            profile["verified"]["fusoes"]=f"parcial_usuario_{len(already)}"
            profile.setdefault("notes",[]).append(
                "Fusões são confirmadas individualmente pelo usuário durante o duelo."
            )
            atomic_json(path,profile)
            entry["verified"]=profile["verified"]
            entry["features"]=supported_for_runtime(profile)
            atomic_json(self.registry_file,{"schema":1,"entries":entries})
            active=load_json(self.active_file,{})
            if active.get("sha256")==rom_sha256:
                active["features"]=entry["features"]
                active["fusion_revision"]=len(already)
                atomic_json(self.active_file,active)
            return len(already)

    def review_fusion_batch(self, rom_sha256: str, *,
                            expected_fingerprint: str,
                            acknowledgement: str) -> dict:
        """Importa receitas revisadas explicitamente, vinculadas ao SHA da ISO.

        Revisão visual do usuário != fusões verificadas no ePSXe.
        Nenhuma aprovação é automática, nem é suficiente o Ollama concordar.
        """
        if acknowledgement != "CATALOGO REVISADO":
            raise PermissionError("É necessária confirmação explícita do usuário")
        with self._lock:
            entries=self.list()
            entry=next((e for e in entries if e.get("sha256")==rom_sha256),None)
            if not entry or not entry.get("approved"):
                raise ValueError("Ative primeiro o perfil correto na Biblioteca")
            profile=self.profile_for(entry)
            if not profile:
                raise ValueError("Perfil de mod ausente ou inconsistente")
            if (profile.get("verified",{}).get("cartas")!="verificado"
                    or len(profile.get("cards",[]))!=722):
                raise ValueError("Catálogo de 722 cartas ainda não validado")

            source=Path(entry.get("source_path",""))
            if not source.is_file():
                raise ValueError("ISO original não encontrada para revalidar a assinatura do arquivo")
            stat=source.stat()
            if (stat.st_size!=entry.get("size")
                    or stat.st_mtime_ns!=entry.get("mtime_ns")):
                raise ValueError("Arquivo ISO alterado desde a importação; refaça a análise")
            report=load_json(self.home/"investigacoes"/(rom_sha256+".fusoes.json"),{})
            if report.get("rom_sha256")!=rom_sha256:
                raise ValueError("Relatório de fusões pertence a outra ISO")
            candidates=report.get("candidates")
            if not isinstance(candidates,list) or not candidates:
                raise ValueError("Relatório não contém receitas candidatas")
            banks=report.get("banks")
            if (not isinstance(banks,list) or len(banks)!=7
                    or report.get("valid_banks")!=7
                    or report.get("matching_banks")!=7
                    or report.get("divergent_banks") is not False
                    or report.get("bank_conflicts")!=0):
                raise ValueError("Bancos de fusões divergentes ou incompletos; aprovação em lote bloqueada")
            fingerprints={x.get("recipelist_sha256") for x in banks
                          if x.get("status")=="decodificado"
                          and x.get("conflict_count")==0}
            fingerprint=report.get("candidate_fingerprint")
            if (len(fingerprints)!=1 or fingerprint not in fingerprints
                    or not isinstance(fingerprint,str)
                    or fingerprint!=expected_fingerprint):
                raise ValueError("Assinatura do conjunto de fusões mudou; revise novamente")
            recipes=set()
            symmetric={}
            for row in candidates:
                try:
                    a,b,c=(int(row[k]) for k in ("a","b","result"))
                except (KeyError,ValueError,TypeError) as exc:
                    raise ValueError("Receita inválida no relatório") from exc
                if not all(1<=v<=722 for v in (a,b,c)):
                    raise ValueError("ID de fusão fora de 1..722")
                key=(min(a,b),max(a,b))
                if key in symmetric and symmetric[key]!=c:
                    raise ValueError("Fusão conflitante para os mesmos materiais")
                symmetric[key]=c
                recipes.add((a,b,c))
            canonical=sorted(recipes)
            actual_hash=hashlib.sha256(json.dumps(canonical,separators=(",",":")).encode("ascii")).hexdigest()
            if (actual_hash!=fingerprint or len(recipes)!=report.get("candidate_count")
                    or any(b.get("unique_recipe_count")!=len(recipes) for b in banks)):
                raise ValueError("Receitas não correspondem à assinatura dos sete bancos")

            existing=profile.get("fusion_recipes",[])
            verified_manually={}
            for row in existing:
                a,b,c=(int(row[k]) for k in ("a","b","result"))
                key=(min(a,b),max(a,b))
                if symmetric.get(key)!=c:
                    raise ValueError("Receita já registrada diverge do conjunto; revisão individual necessária")
                if row.get("validation")=="observada_manualmente_no_jogo":
                    verified_manually[(key,c)]=dict(row)
            previous_review=profile.get("fusion_review",{})
            if (previous_review.get("candidate_fingerprint")==fingerprint
                    and len(existing)==len(recipes)):
                return {"count":len(recipes),"already_reviewed":True,
                        "fingerprint":fingerprint}

            reviewed=[]
            for a,b,c in canonical:
                observation=verified_manually.get(((min(a,b),max(a,b)),c))
                record={"a":a,"b":b,"result":c,
                        "validation":("observada_manualmente_no_jogo" if observation
                                      else "revisada_usuario_em_lote"),
                        "fusion_candidate_fingerprint":fingerprint}
                reviewed.append(record)
            updated=dict(profile)
            # Manter a lista EXATAMENTE igual ao banco assinado, incluindo
            # direções distintas, para preservar a assinatura e idempotência.
            updated["fusion_recipes"]=reviewed
            updated["supported_features"]=dict(profile.get("supported_features",{}),
                                               fusions=True)
            updated["verified"]=dict(profile.get("verified",{}),
                                     fusoes="revisadas_usuario_lote")
            updated["fusion_review"]={
                "status":"revisado_usuario_nao_testado_individualmente",
                "rom_sha256":rom_sha256,
                "candidate_fingerprint":fingerprint,
                "recipe_count":len(reviewed),
                "in_game_individually_verified":len(verified_manually),
                "reviewed_at":datetime.now(timezone.utc).isoformat(),
            }
            updated["notes"]=list(profile.get("notes",[]))+[
                "Catálogo revisado visualmente pelo usuário; não equivale a teste de todas as fusões no jogo."
            ]
            path=Path(entry["profile_path"])
            # Backup antes da primeira aprovação; não incluir ISO/saves.
            backup=path.with_name(path.name+".bak.before_fusion_batch")
            if not backup.exists():
                shutil.copy2(path,backup)
            atomic_json(path,updated)
            entry["verified"]=updated["verified"]
            entry["features"]=supported_for_runtime(updated)
            atomic_json(self.registry_file,{"schema":1,"entries":entries})
            active=load_json(self.active_file,{})
            if active.get("sha256")==rom_sha256:
                active["features"]=entry["features"]
                active["fusion_revision"]=len(reviewed)
                active["fusion_review_fingerprint"]=fingerprint
                atomic_json(self.active_file,active)
            return {"count":len(reviewed),"already_reviewed":False,
                    "fingerprint":fingerprint,
                    "in_game_verified":len(verified_manually),
                    "backup":str(backup)}

    def current(self) -> dict | None:
        active = load_json(self.active_file, {})
        row = next((e for e in self.list() if e.get("sha256") == active.get("sha256")), None)
        return active if row and self.profile_for(row) else None


class DirectoryMonitor:
    """Vigia uma pasta local. A análise ocorre em thread de trabalho.

    callback recebe dicts de eventos; NÃO deve modificar widgets Tkinter
    diretamente (use fila + root.after no thread da interface).
    """
    def __init__(self, folder: Path, catalog: ModCatalog,
                 callback: Callable[[dict], None] | None = None,
                 interval: float = 5.0, quiet_seconds: float = 4.0):
        self.folder = Path(folder)
        self.catalog = catalog
        self.callback = callback or (lambda _event: None)
        self.interval = max(1.0, interval)
        self.quiet_seconds = max(1.0, quiet_seconds)
        self._stop = threading.Event()
        self._thread = None
        self._observations: dict[str, tuple[int, int, float]] = {}
        self._processed: set[tuple[str, int, int]] = set()
        self._work: queue.Queue[Path | None] = queue.Queue()
        self._pending: set[str] = set()
        self._worker = None

    def _emit(self, kind: str, **fields):
        try:
            self.callback({"event": kind, **fields})
        except Exception:
            pass

    def _scan(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        while not self._stop.is_set():
            now = time.monotonic()
            for path in self.folder.iterdir():
                if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                resolved = str(path.resolve())
                signature = (resolved, stat.st_size, stat.st_mtime_ns)
                seen = self._observations.get(resolved)
                if seen is None or seen[:2] != signature[1:]:
                    self._observations[resolved] = (stat.st_size, stat.st_mtime_ns, now)
                    continue
                if (signature not in self._processed
                        and now - seen[2] >= self.quiet_seconds
                        and resolved not in self._pending):
                    cached = self.catalog.lookup(path)
                    if cached and cached["size"] == stat.st_size and cached["mtime_ns"] == stat.st_mtime_ns:
                        self._processed.add(signature)
                        continue
                    self._pending.add(resolved)
                    self._processed.add(signature)
                    self._work.put(path)
                    self._emit("encontrado", file=path.name)
            self._stop.wait(self.interval)

    def _analyse(self):
        while not self._stop.is_set():
            try:
                path = self._work.get(timeout=0.5)
            except queue.Empty:
                continue
            if path is None:
                return
            try:
                self._emit("analisando", file=path.name)
                def on_progress(stage, done, total):
                    percent=round(done*100/total) if total else None
                    self._emit("progresso", file=path.name, stage=stage, done=done,
                               total=total, percent=percent)
                entry = self.catalog.analyse(path, progress=on_progress)
                self._emit("concluido", file=path.name, level=entry["level"], sha256=entry["sha256"])
            except Exception as exc:
                self._emit("erro", file=path.name, message=str(exc))
                # Permitir nova tentativa caso o arquivo tenha mudado.
                for sig in list(self._processed):
                    if sig[0] == str(path.resolve()):
                        self._processed.remove(sig)
            finally:
                self._pending.discard(str(path.resolve()))
                self._work.task_done()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._analyse, daemon=True, name="mod-analyser")
        self._thread = threading.Thread(target=self._scan, daemon=True, name="rom-folder-monitor")
        self._worker.start()
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._work.put(None)
        if self._thread:
            self._thread.join(timeout=2)

    def scan_file(self, path: Path):
        """Adiciona manualmente um arquivo à fila, sem bloquear a janela."""
        path = Path(path)
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            raise ValueError("Selecione .bin ou .iso")
        if not self._thread or not self._thread.is_alive():
            self.start()
        resolved = str(path.resolve())
        if resolved not in self._pending:
            self._pending.add(resolved)
            self._work.put(path)
