"""Diagnóstico experimental de eventos de fusão na RAM do ePSXe (somente leitura).

Objetivo: observar duas capturas feitas pelo usuário ANTES e DEPOIS de uma
fusão reproduzida no jogo. Registra diferenças brutas em poucas regiões já
investigadas, mas não deduz resultado nem confirma automaticamente receitas.

A leitura da mão em 0xBFF484 (140 bytes) é comprovada pelo CompactPanel.tick().
As demais regiões são EXPLORATÓRIAS: alterações nelas não comprovam fusão.
"""
from __future__ import annotations

import json
import re
import struct
import time
from datetime import datetime, timezone
from pathlib import Path

# Uma única amostragem limitada. Não varre nem despeja memória indiscriminadamente.
WINDOWS = {
    "mao_conhecida": (0xBFF484, 140),
    "exploratoria_a": (0xB483A2, 32),
    "exploratoria_b": (0xB5B21E, 32),
    "exploratoria_c": (0xB41891, 32),
}
MAX_DIFFS_PER_WINDOW = 96
SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def decode_hand(data: bytes | None) -> list[int] | None:
    """Replica exatamente a validação do CompactPanel.tick()."""
    if not isinstance(data, bytes) or len(data) != 140:
        return None
    cards = []
    for slot in range(5):
        row = data[slot * 28:(slot + 1) * 28]
        cid = struct.unpack_from("<H", row)[0]
        index = struct.unpack_from("<I", row, 12)[0]
        if not 1 <= cid <= 722 or index != slot:
            return None
        cards.append(cid)
    return cards


def differences(before: dict, after: dict) -> dict:
    """Comparação bruta: diffs NÃO têm significado sem prova no emulador."""
    changes = {}
    for name in WINDOWS:
        a = before.get("windows", {}).get(name, {})
        b = after.get("windows", {}).get(name, {})
        if not (a.get("ok") and b.get("ok")):
            changes[name] = {"status": "indisponivel", "changed_bytes": None}
            continue
        ab = bytes.fromhex(a["hex"])
        bb = bytes.fromhex(b["hex"])
        if len(ab) != len(bb):
            changes[name] = {"status": "comprimento_divergente", "changed_bytes": None}
            continue
        changed = [i for i, (left, right) in enumerate(zip(ab, bb)) if left != right]
        changes[name] = {
            "status": "comparado",
            "changed_bytes": len(changed),
            "sample": [{"offset": i, "before": f"{ab[i]:02x}", "after": f"{bb[i]:02x}"}
                       for i in changed[:MAX_DIFFS_PER_WINDOW]],
            "sample_truncated": len(changed) > MAX_DIFFS_PER_WINDOW,
        }
    return changes


class FusionMemoryProbe:
    """Capturas síncronas na thread Tk; rd.read() é a mesma API do painel."""

    def __init__(self, reader_provider, home: Path):
        self.reader_provider = reader_provider
        self.home = Path(home)
        self.before: dict | None = None

    @staticmethod
    def _check_sha(sha: str):
        if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            raise ValueError("Identificador da ISO inválido")

    def snapshot(self, sha: str) -> dict:
        self._check_sha(sha)
        reader = self.reader_provider()
        if reader is None:
            raise RuntimeError("ePSXe não conectado ao Assistente")
        pid = getattr(reader, "pid", None)
        if type(pid) is not int or pid <= 0:
            raise RuntimeError("PID do ePSXe indisponível")
        windows = {}
        for name, (address, size) in WINDOWS.items():
            try:
                raw = reader.read(address, size)
                if not isinstance(raw, bytes) or len(raw) != size:
                    raise ValueError("leitura incompleta")
                windows[name] = {"address": f"0x{address:X}", "size": size,
                                 "ok": True, "hex": raw.hex()}
            except Exception as exc:
                windows[name] = {"address": f"0x{address:X}", "size": size,
                                 "ok": False, "error": f"{type(exc).__name__}: {exc}"[:160]}
        hand = bytes.fromhex(windows["mao_conhecida"]["hex"]) if windows["mao_conhecida"]["ok"] else None
        return {
            "rom_sha256_selected_manually": sha.lower(),
            "pid": pid, "captured_at": datetime.now(timezone.utc).isoformat(),
            "hand_ids": decode_hand(hand),
            "windows": windows,
        }

    def capture_before(self, sha: str) -> dict:
        snap = self.snapshot(sha)
        if snap.get("hand_ids") is None:
            raise RuntimeError("Mão de cinco cartas não validada; tente durante o duelo")
        self.before = snap
        return snap

    def capture_after(self, sha: str, *, observed_result_id: int | None = None) -> tuple[dict, Path]:
        self._check_sha(sha)
        before = self.before
        if before is None:
            raise RuntimeError("Use 'Capturar antes' primeiro")
        if before["rom_sha256_selected_manually"] != sha.lower():
            raise RuntimeError("Outro perfil de ISO foi selecionado; diagnóstico cancelado")
        if observed_result_id is not None:
            if type(observed_result_id) is not int or not 1 <= observed_result_id <= 722:
                raise ValueError("ID do resultado observado deve estar entre 1 e 722")
        after = self.snapshot(sha)
        if before["pid"] != after["pid"]:
            raise RuntimeError("O processo do ePSXe mudou; descarte a captura anterior")
        report = {
            "schema": 1,
            "status": "DIAGNOSTICO — NAO CONFIRMA FUSAO",
            "rom_sha256_selected_manually": sha.lower(),
            "emulator_iso_verified": False,
            "pid": after["pid"],
            "before": before, "after": after,
            "diff": differences(before, after),
            "user_observed_result_id": observed_result_id,
            "fusion_event_verified": False,
            "fusion_catalog_changed": False,
            "notes": [
                "Janelas exploratórias não identificam, isoladamente, um evento de fusão.",
                "O resultado observado foi informado pelo usuário; não foi lido automaticamente.",
                "Não contém nem modifica ISO, Memory Card ou saves.",
            ],
        }
        destination = self.home / "diagnosticos_fusao" / sha.lower()
        destination.mkdir(parents=True, exist_ok=True)
        file = destination / (datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                              + "_" + str(time.time_ns()) + ".json")
        temp = file.with_name(file.name + ".tmp")
        temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(file)
        self.before = None
        return report, file
