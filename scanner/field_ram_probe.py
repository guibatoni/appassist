"""Investigação restrita dos slots de monstros no campo do ePSXe (somente leitura).

A única estrutura validada até aqui é a mão em 0xBFF484. A região pesquisada
é uma HIPÓTESE de proximidade com a mão, não um endereço comprovado de campo.
Amostras de regiões pequenas ao redor da mão, sem dump completo de processo.
Relatórios guardam APENAS endereços candidatos e IDs, nunca os blocos brutos.
"""
from __future__ import annotations

import json
import struct
import time
from datetime import datetime, timezone
from pathlib import Path

from fusion_ram_probe import decode_hand, FusionMemoryProbe

HAND_ADDR = 0xBFF484
HAND_SIZE = 140
CHUNK_SIZE = 4096
SEARCH_START = (HAND_ADDR & ~(CHUNK_SIZE - 1)) - 8 * CHUNK_SIZE
SEARCH_SIZE = 24 * CHUNK_SIZE  # 96 KiB máximo; não é varredura de processo completo.
MAX_CANDIDATES = 150
# Investigação AMPLIADA manual: 1 MiB do MESMO processo ePSXe, sem dump.
# Inclui endereços de interesse B483A2, B5B21E, BFF484 e C02D00.
# Não corresponde a um mapa confirmado do campo.
EXPANDED_START = 0xB40000
EXPANDED_SIZE = 0x100000  # 1 MiB, 256 chunks de 4096 bytes
assert EXPANDED_SIZE == 256 * CHUNK_SIZE
assert EXPANDED_START <= SEARCH_START
assert SEARCH_START + SEARCH_SIZE <= EXPANDED_START + EXPANDED_SIZE


def find_new_id_candidates(before: dict[int, bytes], after: dict[int, bytes],
                           target: int, *, after_removed: dict[int, bytes] | None = None) -> dict:
    """Procura o ID uint16 LE que APARECEU depois fora do bloco validado da mão.

    Um ID em RAM é apenas padrão de bytes; não confirma uma carta no campo.
    A etapa opcional de remoção reduz falsos positivos, mas não valida um slot.
    """
    if type(target) is not int or not 1 <= target <= 722:
        raise ValueError("ID deve estar entre 1 e 722")
    pattern = struct.pack("<H", target)
    offsets = []
    compared = 0
    changed = 0
    unmatched = 0
    for addr in sorted(set(before)|set(after)):
        first,second = before.get(addr),after.get(addr)
        if first is None or second is None or len(first)!=CHUNK_SIZE or len(second)!=CHUNK_SIZE:
            unmatched+=1
            continue
        compared+=1
        changed+=sum(x!=y for x,y in zip(first,second))
        # Para evitar um falso positivo entre dois blocos, só contar padrões
        # que cabem no mesmo chunk. Isso pode perder candidatos na borda.
        start = 0
        while True:
            idx = second.find(pattern,start)
            if idx < 0:break
            offset=addr+idx
            start=idx+1
            if HAND_ADDR <= offset < HAND_ADDR + HAND_SIZE:
                continue
            if first[idx:idx+2] == pattern:
                continue
            removed=None
            if after_removed is not None and addr in after_removed:
                last=after_removed[addr]
                if len(last)==CHUNK_SIZE:
                    removed=last[idx:idx+2] != pattern
            offsets.append({
                "address":f"0x{offset:08X}",
                "before_u16":int.from_bytes(first[idx:idx+2],"little"),
                "after_u16":target,
                "disappeared_after_removal":removed,
                "confidence":"HIPOTESE_NAO_VALIDADA",
            })
    total=len(offsets)
    return {
        "search_target_id":target,
        "candidate_count_total":total,
        "candidate_list_truncated":total>MAX_CANDIDATES,
        "candidates":offsets[:MAX_CANDIDATES],
        "chunks_compared":compared,
        "chunks_not_comparable":unmatched,
        "changed_bytes_in_compared_chunks":changed,
        "hand_region_excluded":True,
        "field_address_verified":False,
    }


def summarize_phase_changes(before: dict[int, bytes], after: dict[int, bytes]) -> dict:
    """Diferenças por offset (sem bytes brutos), nunca prova de carta no campo."""
    changed_total = 0
    comparable = 0
    changes_by_chunk = []
    address_samples = []
    for addr in sorted(set(before) | set(after)):
        a, b = before.get(addr), after.get(addr)
        if a is None or b is None or len(a) != CHUNK_SIZE or len(b) != CHUNK_SIZE:
            continue
        comparable += 1
        changed = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        if changed:
            changed_total += len(changed)
            changes_by_chunk.append({
                "chunk_start": f"0x{addr:08X}",
                "changed_bytes": len(changed),
            })
            for off in changed[:max(0, 96 - len(address_samples))]:
                address_samples.append(f"0x{addr + off:08X}")
    return {
        "comparable_chunks": comparable,
        "changed_bytes": changed_total,
        "hotspot_chunks": sorted(changes_by_chunk,
                                 key=lambda c: (-c["changed_bytes"], c["chunk_start"]))[:12],
        "changed_chunks": changes_by_chunk,
        "changed_offsets_sample": address_samples,
        "sample_truncated": changed_total > len(address_samples),
        "proves_duel_field": False,
    }


class FieldMemoryProbe:
    """Bancada por fases; a mão pode atualizar somente após virar o turno.

    ANTES -> PREPARADA (opcional) -> NA MESA -> MÃO ATUALIZADA (opcional)
    -> REMOVIDA (opcional). As fases são observadas pelo usuário no jogo.
    """

    def __init__(self, reader_provider, home: Path, *, expanded: bool = False):
        self.reader_provider=reader_provider
        self.home=Path(home)
        if type(expanded) is not bool:
            raise ValueError("expanded deve ser booleano")
        self.expanded=expanded
        self.search_start=EXPANDED_START if expanded else SEARCH_START
        self.search_size=EXPANDED_SIZE if expanded else SEARCH_SIZE
        self.before=None
        self.prepared=None
        self.after=None
        self.refreshed=None
        self.report=None
        self.file=None

    def _capture(self, sha: str) -> dict:
        FusionMemoryProbe._check_sha(sha)
        reader=self.reader_provider()
        if reader is None:
            raise RuntimeError("ePSXe desconectado")
        pid=getattr(reader,"pid",None)
        if type(pid) is not int or pid<=0:
            raise RuntimeError("PID do ePSXe inválido")
        # O layout da mão precisa estar íntegro em todas as fases.
        hand=reader.read(HAND_ADDR,HAND_SIZE)
        ids=decode_hand(hand)
        if ids is None:
            raise RuntimeError("Mão de cinco cartas inválida; capture durante um duelo")
        chunks={}
        errors=[]
        for addr in range(self.search_start,self.search_start+self.search_size,CHUNK_SIZE):
            try:
                block=reader.read(addr,CHUNK_SIZE)
                if not isinstance(block,bytes) or len(block)!=CHUNK_SIZE:
                    raise ValueError("bloco incompleto")
                chunks[addr]=block
            except Exception as exc:
                errors.append({"address":f"0x{addr:08X}","error":type(exc).__name__})
        if not chunks:
            raise RuntimeError("Nenhum bloco acessível na área experimental próxima à mão")
        return {
            "sha":sha.lower(),"pid":pid,
            "timestamp_utc":datetime.now(timezone.utc).isoformat(),
            "hand_ids":ids, "chunks":chunks, "unreadable_chunks":errors,
        }

    @staticmethod
    def _public(snapshot: dict) -> dict:
        return {key:snapshot[key] for key in
                ("sha","pid","timestamp_utc","hand_ids","unreadable_chunks")} | {
                    "readable_chunks":len(snapshot["chunks"])}

    def capture_before(self, sha: str, target_id: int) -> dict:
        if type(target_id) is not int or not 1<=target_id<=722:
            raise ValueError("Informe o ID da carta a invocar entre 1 e 722")
        sample=self._capture(sha)
        if target_id not in sample["hand_ids"]:
            raise ValueError("Carta escolhida não consta da mão; captura ANTES rejeitada")
        self.before={"snapshot":sample,"target_id":target_id}
        self.prepared=None
        self.after=None
        self.refreshed=None
        self.report=None
        self.file=None
        return self._public(sample)

    def _capture_same_session(self, sha: str) -> dict:
        if self.before is None:
            raise RuntimeError("Capture ANTES primeiro")
        sample=self._capture(sha)
        initial=self.before["snapshot"]
        if sample["sha"]!=initial["sha"] or sample["pid"]!=initial["pid"]:
            raise RuntimeError("ISO ou PID do ePSXe mudou; inicie outro diagnóstico")
        return sample

    def capture_prepared(self, sha: str, *, face_state: str | None = None) -> dict:
        """Opcional: carta selecionada, orientação e Guardian Star já escolhidas;
        ainda não colocada na mesa. Não confirma semanticamente essa fase.
        """
        if self.after is not None:
            raise RuntimeError("A carta já foi registrada na mesa; reinicie o diagnóstico")
        if face_state not in (None,"faceup","facedown"):
            raise ValueError("Posição da face inválida")
        sample=self._capture_same_session(sha)
        initial=self.before["snapshot"]
        self.prepared={"snapshot":sample,"face_state":face_state}
        return {
            **self._public(sample),
            "phase":"PREPARADA_INFORMADA_PELO_USUARIO",
            "changes_since_before":summarize_phase_changes(
                initial["chunks"],sample["chunks"]),
        }

    def capture_after(self, sha: str, *,
                      face_state: str | None = None,
                      user_slot: int | None = None) -> tuple[dict,Path]:
        """Captura IMEDIATAMENTE após posicionar a carta no campo.

        Não exige que o ID suma da mão. O usuário comprovou que no ePSXe a
        mão pode manter o ID até passar o turno e o controle voltar.
        """
        if self.before is None:
            raise RuntimeError("Primeiro capture o estado ANTES da invocação")
        if face_state not in (None,"faceup","facedown"):
            raise ValueError("FaceUp ou FaceDown inválido")
        if user_slot is not None and (
                type(user_slot) is not int or not 1<=user_slot<=5):
            raise ValueError("Slot observado deve estar entre 1 e 5")
        sample=self._capture_same_session(sha)
        initial=self.before["snapshot"]
        target=self.before["target_id"]
        self.after=sample
        self.refreshed=None
        reference=self.prepared["snapshot"] if self.prepared else initial
        candidates=find_new_id_candidates(reference["chunks"],sample["chunks"],target)
        target_remaining=sample["hand_ids"].count(target)
        target_initial=initial["hand_ids"].count(target)
        report={
            "schema":2,"type":"DIAGNOSTICO_CAMPO_RAM",
            "status":"HIPOTESES — NENHUM SLOT DO CAMPO VALIDADO",
            "rom_sha256_selected_manually":sample["sha"],
            "emulator_iso_verified":False,"pid":sample["pid"],
            "reference_card_id":target,
            "before":self._public(initial),
            "after_preparation":(self._public(self.prepared["snapshot"])
                                 if self.prepared else None),
            "after_summon":self._public(sample),
            "after_hand_refresh":None,
            "after_removal":None,
            "observed_by_user":{
                "face_state":face_state or (self.prepared or {}).get("face_state"),
                "slot_position_1_to_5":user_slot,
                "summon_set_visible":True,
                "guardian_star_selected":True,
                "interpretation":"DECLARADO PELO USUARIO, NAO DETECTADO PELA RAM",
            },
            "hand_state_at_set":{
                "target_count_before":target_initial,
                "target_count_when_set":target_remaining,
                "target_still_visible_in_hand_ram":target_remaining>0,
                "hand_ids_identical_to_before":sample["hand_ids"]==initial["hand_ids"],
                "hand_refresh_not_required":True,
                "does_not_prove_field":True,
            },
            "scan":{"address_start":f"0x{self.search_start:08X}",
                    "size_bytes":self.search_size,"chunk_size":CHUNK_SIZE,
                    "mode":"AMPLIADA_1MIB" if self.expanded else "RESTRITA_96KIB",
                    "purpose":"faixa experimental no processo ePSXe; NAO e mapa de campo"},
            "analysis":candidates,
            "phase_differences":{
                "before_to_preparation":(
                    summarize_phase_changes(initial["chunks"],self.prepared["snapshot"]["chunks"])
                    if self.prepared else None),
                "reference_to_set":summarize_phase_changes(reference["chunks"],sample["chunks"]),
                "before_to_set":summarize_phase_changes(initial["chunks"],sample["chunks"]),
                "set_to_hand_refresh":None,
                "set_to_removed":None,
            },
            "duel_field_card_ids":None,
            "duel_field_ram_verified":False,
            "fusion_catalog_changed":False,
            "notes":[
                "A carta pode estar visível na mesa e simultaneamente permanecer no bloco RAM da mão até outro turno.",
                "Captura NA MESA feita após FaceUp/FaceDown, Guardian Star e colocação no slot.",
                "A presença do ID uint16 em memória não comprova a ocupação do campo.",
                "Endereço 0xBFF510 pode ser buffer adjacente à mão, não slot da mesa.",
                "Nenhum dump bruto da memória é incluído neste relatório.",
                "A faixa ampliada de 1 MiB não equivale a uma varredura integral "
                "da RAM do ePSXe nem garante cobrir o campo.",
                "Contagens de bytes podem mudar por efeitos, animação e outras "
                "ações do jogo e não comprovam o campo.",
                "Todas as fases são anotações visuais do usuário, não verificações automáticas.",
            ],
        }
        folder=self.home/"diagnosticos_campo"/sample["sha"]
        folder.mkdir(parents=True,exist_ok=True)
        name=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")+"_"+str(time.time_ns())+".json"
        file=folder/name
        self._save(file,report)
        self.report=report
        self.file=file
        return report,file

    def capture_hand_refresh(self, sha: str) -> tuple[dict,Path]:
        """Opcional: após encerrar o turno e reabrir o controle da mão."""
        if self.after is None or self.report is None:
            raise RuntimeError("Capture NA MESA antes de atualizar a mão")
        sample=self._capture_same_session(sha)
        target=self.before["target_id"]
        before_count=self.before["snapshot"]["hand_ids"].count(target)
        refreshed_count=sample["hand_ids"].count(target)
        self.refreshed=sample
        report=dict(self.report)
        report["after_hand_refresh"]=self._public(sample)
        report["hand_refresh_analysis"]={
            "target_count_before":before_count,
            "target_count_after_refresh":refreshed_count,
            "target_count_decreased":refreshed_count<before_count,
            "is_field_presence_evidence":False,
        }
        phases=dict(report["phase_differences"])
        phases["set_to_hand_refresh"]=summarize_phase_changes(
            self.after["chunks"],sample["chunks"])
        report["phase_differences"]=phases
        self._save(self.file,report)
        self.report=report
        return report,self.file

    @staticmethod
    def _save(path,report):
        tmp=path.with_name(path.name+".tmp")
        tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        tmp.replace(path)

    def capture_removed(self, sha: str) -> tuple[dict,Path]:
        if self.before is None or self.after is None or self.report is None:
            raise RuntimeError("Capture ANTES e DEPOIS da invocação antes de registrar a remoção")
        sample=self._capture_same_session(sha)
        initial=self.before["snapshot"]
        target=self.before["target_id"]
        # O usuário confirmou visualmente a remoção; os bytes são evidência
        # experimental e não atestam que houve realmente a remoção.
        report=dict(self.report)
        report["after_removal"]=self._public(sample)
        reference=self.prepared["snapshot"] if self.prepared else initial
        report["analysis"]=find_new_id_candidates(
            reference["chunks"],self.after["chunks"],target,
            after_removed=sample["chunks"])
        phases=dict(report["phase_differences"])
        phases["set_to_removed"]=summarize_phase_changes(
            self.after["chunks"],sample["chunks"])
        report["phase_differences"]=phases
        report["notes"]=report["notes"]+[
            "A remoção foi informada visualmente pelo usuário; "
            "o desaparecimento do padrão em RAM ainda não valida o slot."
        ]
        self._save(self.file,report)
        self.report=report
        return report,self.file
