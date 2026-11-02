"""Detector automático e catálogo local de mods — não modifica a ROM.

Detecta imagens novas na pasta selecionada, gera perfis locais e diferencia
dados extraídos/validados de regras ainda desconhecidas.

Este módulo não usa um LLM. A 'inteligência' consiste em reconhecimento de
assinaturas, parsers de estrutura, verificações cruzadas e perfis revisáveis.
"""
from __future__ import annotations

import json
import os
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from importador_perfis import import_rom
from scanner_multiiso import X15_SHA

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
        resolved = str(path.resolve())
        return next((row for row in self.list() if row.get("source_path") == resolved), None)

    def profile_for(self, entry: dict) -> dict | None:
        path = Path(entry.get("profile_path", ""))
        if not path.is_file() or not path.resolve().is_relative_to(self.home.resolve()):
            return None
        profile = load_json(path, {})
        if profile.get("rom_sha256") != entry.get("sha256"):
            return None
        return profile

    def analyse(self, path: Path, with_art: bool = False) -> dict:
        path = Path(path).resolve(strict=True)
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            raise ValueError("Selecione uma imagem .bin ou .iso")
        before = path.stat()
        if before.st_size < 100_000:
            raise ValueError("Arquivo pequeno demais para uma imagem de jogo")
        old = self.lookup(path)
        if old and old.get("size") == before.st_size and old.get("mtime_ns") == before.st_mtime_ns:
            if not with_art or (self.profile_for(old) or {}).get("supported_features", {}).get("art"):
                return dict(old)

        profile, profile_path = import_rom(path, self.home, art=with_art)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError("Arquivo alterado durante a leitura; análise descartada")

        entry = {
            "source_path": str(path),
            "file_name": path.name,
            "size": after.st_size,
            "mtime_ns": after.st_mtime_ns,
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
                entry = self.catalog.analyse(path)
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
