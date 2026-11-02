"""Monitor temporal experimental de RAM do ePSXe (somente leitura).

Registra amostras pequenas e limitadas no tempo a partir de FusionMemoryProbe.
O estado do campo de duelo NÃO está mapeado: não inferir cartas na mesa por
endereços não validados. Nenhum log representa confirmação de fusões.
"""
from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from fusion_ram_probe import FusionMemoryProbe, WINDOWS, differences

MAX_SECONDS = 90
MIN_INTERVAL_MS = 200
MAX_INTERVAL_MS = 1000
MAX_SAMPLES = 452   # inclui primeira amostra (90 s em 200 ms, com margem)
ALLOWED_MARKERS = {
    "fusao": "Fusão realizada (informada pelo usuário)",
    "invocacao": "Invocação sem fusão (informada pelo usuário)",
    "ataque": "Ataque sem fusão (informado pelo usuário)",
    "cancelamento": "Seleção/cancelamento (informado pelo usuário)",
    "controle": "Controle sem ação (informado pelo usuário)",
}


class TemporalRamRecorder:
    """Amostras disparadas por Tk.after; sem thread e sem escrita no emulador."""

    def __init__(self, probe: FusionMemoryProbe, *, monotonic=time.monotonic):
        self.probe = probe
        self.monotonic = monotonic
        self.active = False
        self.profile_sha = None
        self.pid = None
        self.started_monotonic = None
        self.interval_ms = None
        self.duration_seconds = None
        self.samples = []
        self.markers = []
        self.status = "inativo"
        self.last_paths = None

    def start(self, sha: str, *, interval_ms: int = 250,
              duration_seconds: int = 45) -> dict:
        if self.active:
            raise RuntimeError("Monitor temporal já está gravando")
        if type(interval_ms) is not int or not MIN_INTERVAL_MS <= interval_ms <= MAX_INTERVAL_MS:
            raise ValueError(f"Intervalo deve ser de {MIN_INTERVAL_MS} a {MAX_INTERVAL_MS} ms")
        if type(duration_seconds) is not int or not 1 <= duration_seconds <= MAX_SECONDS:
            raise ValueError(f"Duração deve estar entre 1 e {MAX_SECONDS} segundos")
        initial = self.probe.snapshot(sha)
        if initial["hand_ids"] is None:
            raise RuntimeError("Inicie durante um duelo com cinco cartas válidas na mão")
        self.profile_sha = sha.lower()
        self.pid = initial["pid"]
        self.started_monotonic = self.monotonic()
        self.interval_ms = interval_ms
        self.duration_seconds = duration_seconds
        self.samples = [{"elapsed_ms": 0, "snapshot": initial, "changes": None}]
        self.markers = []
        self.status = "gravando"
        self.last_paths = None
        self.active = True
        return initial

    def sample(self) -> dict:
        if not self.active:
            raise RuntimeError("Monitor temporal não está gravando")
        if len(self.samples) >= MAX_SAMPLES:
            raise RuntimeError("Limite de amostras atingido; finalize a gravação")
        current = self.probe.snapshot(self.profile_sha)
        if current["pid"] != self.pid:
            raise RuntimeError("PID do ePSXe mudou durante a gravação")
        prev = self.samples[-1]["snapshot"]
        delta = differences(prev, current)
        changed = [name for name, detail in delta.items() if detail["changed_bytes"]]
        elapsed = round((self.monotonic() - self.started_monotonic) * 1000)
        self.samples.append({
            "elapsed_ms": max(0, elapsed), "snapshot": current,
            "changes": delta,
        })
        return {
            "samples": len(self.samples),
            "elapsed_ms": max(0, elapsed),
            "changed_windows": changed,
            "finished_by_duration": elapsed >= self.duration_seconds * 1000,
            "finished_by_limit": len(self.samples) >= MAX_SAMPLES,
        }

    def mark(self, label: str):
        if not self.active:
            raise RuntimeError("Monitor temporal não está gravando")
        if label not in ALLOWED_MARKERS:
            raise ValueError("Tipo de marcador desconhecido")
        marker = {
            "label": label,
            "caption": ALLOWED_MARKERS[label],
            "elapsed_ms": max(0, round((self.monotonic() - self.started_monotonic) * 1000)),
            "sample_count_at_click": len(self.samples),
            "annotation_only": True,
        }
        self.markers.append(marker)
        return marker

    def stop(self, *, reason="manual") -> tuple[dict, Path, Path]:
        if not self.active:
            raise RuntimeError("Nenhuma gravação em andamento")
        if reason not in ("manual", "duracao", "limite", "erro", "fechar_janela"):
            raise ValueError("Motivo de encerramento inválido")
        self.active = False
        self.status = "encerrado"
        self.last_paths = None
        changed = sum(
            1 for row in self.samples[1:]
            if any((d.get("changed_bytes") or 0) > 0
                   for d in (row["changes"] or {}).values()))
        report = {
            "schema": 1,
            "type": "DIAGNOSTICO_TEMPORAL_RAM",
            "status": "EXPERIMENTAL — NÃO CONFIRMA FUSÃO NEM CARTAS NO CAMPO",
            "rom_sha256_selected_manually": self.profile_sha,
            "emulator_iso_verified": False,
            "pid": self.pid,
            "interval_ms_requested": self.interval_ms,
            "max_duration_seconds": self.duration_seconds,
            "end_reason": reason,
            "sample_count": len(self.samples),
            "transitions_with_changed_bytes": changed,
            "windows": {k: {"address": hex(v[0]), "size": v[1],
                            "meaning": "mão validada" if k == "mao_conhecida"
                            else "exploratória — não validada"}
                        for k, v in WINDOWS.items()},
            "markers": self.markers,
            "samples": self.samples,
            "duel_field_card_ids": None,
            "duel_field_ram_verified": False,
            "fusion_event_verified": False,
            "fusion_catalog_changed": False,
        }
        folder = self.probe.home / "diagnosticos_temporais" / self.profile_sha
        folder.mkdir(parents=True, exist_ok=True)
        name = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + str(time.time_ns())
        json_file = folder / (name + ".json")
        csv_file = folder / (name + ".csv")
        tmp_json = json_file.with_name(json_file.name + ".tmp")
        tmp_csv = csv_file.with_name(csv_file.name + ".tmp")
        try:
            tmp_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
            with tmp_csv.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["sample", "elapsed_ms", "timestamp_utc", "pid",
                                 "hand_ids", "hand_valid"] +
                                [name + "_changed_bytes" for name in WINDOWS])
                for idx, row in enumerate(self.samples):
                    snap = row["snapshot"]
                    diffs = row["changes"] or {}
                    writer.writerow([
                        idx, row["elapsed_ms"], snap["captured_at"], snap["pid"],
                        " ".join(str(c) for c in (snap["hand_ids"] or [])),
                        snap["hand_ids"] is not None,
                    ] + [diffs.get(key, {}).get("changed_bytes", "")
                         for key in WINDOWS])
            tmp_json.replace(json_file)
            tmp_csv.replace(csv_file)
        except Exception:
            tmp_json.unlink(missing_ok=True)
            tmp_csv.unlink(missing_ok=True)
            raise
        self.last_paths = (json_file, csv_file)
        return report, json_file, csv_file
