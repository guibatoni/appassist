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
from field_occupancy_probe import analyze_occupancy
from field_cancel_probe import (
    FOCUS_CHUNK, focus_watch_values, focus_slot_u16_values,
    focus_phase_differences, cancelled_preparation_analysis,
)

HAND_ADDR = 0xBFF484
HAND_SIZE = 140
CHUNK_SIZE = 4096
SEARCH_START = (HAND_ADDR & ~(CHUNK_SIZE - 1)) - 8 * CHUNK_SIZE
SEARCH_SIZE = 24 * CHUNK_SIZE  # 96 KiB máximo; não é varredura de processo completo.
MAX_CANDIDATES = 150
# HIPÓTESE, NÃO estrutura validada: em testes de slot 1, o ID ficou em BFF510;
# no teste do slot 2, houve alteração em BFF52C (+28 bytes).
# Lemos exclusivamente uint16 LE nesses cinco endereços candidatos.
HYPOTHESIS_FIRST_SLOT_ID_ADDR = 0xBFF510
HYPOTHESIS_SLOT_STRIDE = 28
HYPOTHESIS_SLOT_COUNT = 5
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


def hypothetical_slot_u16_values(chunks: dict[int, bytes]) -> list[dict]:
    """Cinco valores uint16 dos offsets candidatos, nunca cartas identificadas.

    A presença de um valor 1..722 não significa carta na mesa, nem determina
    lado, ocupação, Guardian Star, status faceup/facedown ou fusões.
    """
    records = []
    for i in range(HYPOTHESIS_SLOT_COUNT):
        addr = HYPOTHESIS_FIRST_SLOT_ID_ADDR + HYPOTHESIS_SLOT_STRIDE * i
        chunk_addr = addr & ~(CHUNK_SIZE - 1)
        buffer = chunks.get(chunk_addr)
        local_offset = addr - chunk_addr
        readable = (isinstance(buffer, bytes) and
                    len(buffer) == CHUNK_SIZE and
                    local_offset + 2 <= len(buffer))
        number = int.from_bytes(buffer[local_offset:local_offset + 2], "little") if readable else None
        records.append({
            "hypothetical_slot": i + 1,
            "address": f"0x{addr:08X}",
            "u16_le": number,
            "plausible_card_id": (1 <= number <= 722) if number is not None else None,
            "field_slot_verified": False,
        })
    return records


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

    def __init__(self, reader_provider, home: Path, *, expanded: bool = False,
                 focused: bool = False):
        self.reader_provider=reader_provider
        self.home=Path(home)
        if type(expanded) is not bool:
            raise ValueError("expanded deve ser booleano")
        if type(focused) is not bool:
            raise ValueError("focused deve ser booleano")
        self.expanded=expanded
        self.focused=focused
        self.search_start=EXPANDED_START if expanded else SEARCH_START
        self.search_size=EXPANDED_SIZE if expanded else SEARCH_SIZE
        self.before=None
        self.prepared=None
        self.after=None
        self.refreshed=None
        self.occupied_control=None
        self.removed_sample=None
        self.vacant_control=None
        self.cancelled=False
        self.no_action_done=False
        self.cancel_file=None
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
        addresses=list(range(self.search_start,self.search_start+self.search_size,CHUNK_SIZE))
        if (self.focused and FOCUS_CHUNK not in addresses):
            # Leitura complementar de 4 KiB; nao e varredura de outro processo.
            addresses.append(FOCUS_CHUNK)
        for addr in addresses:
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

    def capture_before(self, sha: str, target_id: int, *,
                       user_slot: int | None = None) -> dict:
        if user_slot is not None and (type(user_slot) is not int or
                                      not 1<=user_slot<=5):
            raise ValueError("Slot observado deve estar entre 1 e 5")
        if type(target_id) is not int or not 1<=target_id<=722:
            raise ValueError("Informe o ID da carta a invocar entre 1 e 722")
        sample=self._capture(sha)
        if target_id not in sample["hand_ids"]:
            raise ValueError("Carta escolhida não consta da mão; captura ANTES rejeitada")
        self.before={"snapshot":sample,"target_id":target_id,
                     "user_slot":user_slot}
        self.prepared=None
        self.after=None
        self.refreshed=None
        self.occupied_control=None
        self.removed_sample=None
        self.vacant_control=None
        self.cancelled=False
        self.no_action_done=False
        self.cancel_file=None
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
        if self.no_action_done:
            raise RuntimeError("Controle SEM AÇÃO encerrado; clique novamente em ANTES")
        if self.cancelled:
            raise RuntimeError("Jogada cancelada; inicie outro diagnóstico pelo botão ANTES")
        if face_state not in (None,"faceup","facedown"):
            raise ValueError("Posição da face inválida")
        sample=self._capture_same_session(sha)
        initial=self.before["snapshot"]
        self.prepared={"snapshot":sample,"face_state":face_state}
        return {
            **self._public(sample),
            "hypothetical_slot_values": hypothetical_slot_u16_values(sample["chunks"]),
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
        if self.no_action_done:
            raise RuntimeError("Controle SEM AÇÃO encerrado; clique novamente em ANTES")
        if self.cancelled:
            raise RuntimeError("Invocação cancelada: inicie outro diagnóstico pelo botão ANTES")
        if (self.before["user_slot"] is not None and user_slot is not None
            and self.before["user_slot"] != user_slot):
            raise ValueError("O slot mudou entre ANTES e NA MESA; reinicie o diagnóstico")
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
        self.occupied_control=None
        self.removed_sample=None
        self.vacant_control=None
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
            "after_occupied_control":None,
            "after_vacant_control":None,
            "targeted_ram_monitor":(
                {
                    "status":"ENDERECOS_HIPOTETICOS_NAO_VALIDOS_COMO_CAMPO",
                    "focus_chunk":f"0x{FOCUS_CHUNK:08X}",
                    "before":self._focused_public(initial),
                    "prepared":self._focused_public(self.prepared["snapshot"])
                        if self.prepared else None,
                    "set":self._focused_public(sample),
                    "occupied_control":None,
                    "removed":None,
                    "vacant_control":None,
                    "hand_refreshed":None,
                    "field_slot_verified":False,
                } if self.focused else None),
            "occupancy_analysis":{
                "status":"AGUARDANDO_REMOCAO",
                "field_slot_verified":False,
                "occupancy_verified":False,
                "candidates":[],
            },
            "hypothetical_slot_probe":{
                "status":"PADRAO DE 28 BYTES NAO VALIDADO COMO CAMPO",
                "hypothesis":"0xBFF510 + (slot - 1) * 28",
                "before":hypothetical_slot_u16_values(initial["chunks"]),
                "prepared":(hypothetical_slot_u16_values(self.prepared["snapshot"]["chunks"])
                            if self.prepared else None),
                "set":hypothetical_slot_u16_values(sample["chunks"]),
                "hand_refreshed":None,
                "removed":None,
                "field_slot_verified":False,
                "does_not_confirm_occupancy":True,
            },
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
                    "focused_extra_chunk":(
                        f"0x{FOCUS_CHUNK:08X}" if self.focused and not self.expanded
                        else None),
                    "focused_enabled":self.focused,
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
                "Os valores em BFF510 + n*28 são leituras uint16 experimentais "
                "e NAO provam que existam cinco slots nesse endereço.",
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
        if self.focused:
            monitor=dict(report["targeted_ram_monitor"])
            monitor["hand_refreshed"]=self._focused_public(sample)
            report["targeted_ram_monitor"]=monitor
        probe=dict(report["hypothetical_slot_probe"])
        probe["hand_refreshed"]=hypothetical_slot_u16_values(sample["chunks"])
        report["hypothetical_slot_probe"]=probe
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

    def _occupancy_analysis(self) -> dict:
        """Cruza snapshots para gerar HIPÓTESES, nunca autoriza leitura do campo."""
        if self.before is None or self.after is None or self.report is None:
            raise RuntimeError("Capture ANTES e NA MESA antes de analisar ocupação")
        observed_slot=self.report["observed_by_user"]["slot_position_1_to_5"]
        if observed_slot is None:
            # API antiga permitia capturar sem slot; não inventar posição.
            return {
                "status":"SEM_SLOT_DECLARADO",
                "field_slot_verified":False,
                "occupancy_verified":False,
                "candidates":[],
            }
        return analyze_occupancy(
            self.before["snapshot"]["chunks"],
            self.after["chunks"],
            self.removed_sample["chunks"] if self.removed_sample else None,
            observed_slot=observed_slot,
            prepared=self.prepared["snapshot"]["chunks"] if self.prepared else None,
            occupied_control=(
                self.occupied_control["chunks"] if self.occupied_control else None),
            vacant_control=(
                self.vacant_control["chunks"] if self.vacant_control else None),
        )

    def capture_occupied_control(self, sha: str) -> tuple[dict, Path]:
        """Captura controle em que o MESMO monstro segue presente na mesa."""
        if self.after is None or self.report is None:
            raise RuntimeError("Capture NA MESA antes do controle OCUPADA")
        if self.removed_sample is not None:
            raise RuntimeError("A fase REMOVIDA já foi registrada; inicie novo teste")
        sample=self._capture_same_session(sha)
        self.occupied_control=sample
        report=dict(self.report)
        report["after_occupied_control"]=self._public(sample)
        if self.focused:
            monitor=dict(report["targeted_ram_monitor"])
            monitor["occupied_control"]=self._focused_public(sample)
            report["targeted_ram_monitor"]=monitor
        report["occupancy_analysis"]=self._occupancy_analysis()
        self._save(self.file,report)
        self.report=report
        return report,self.file

    def capture_vacant_control(self, sha: str) -> tuple[dict, Path]:
        """Captura controle após REMOVIDA, com o mesmo slot ainda vazio."""
        if self.removed_sample is None or self.report is None:
            raise RuntimeError("Capture REMOVIDA antes de confirmar VAZIA ESTÁVEL")
        sample=self._capture_same_session(sha)
        self.vacant_control=sample
        report=dict(self.report)
        report["after_vacant_control"]=self._public(sample)
        if self.focused:
            monitor=dict(report["targeted_ram_monitor"])
            monitor["vacant_control"]=self._focused_public(sample)
            report["targeted_ram_monitor"]=monitor
        report["occupancy_analysis"]=self._occupancy_analysis()
        self._save(self.file,report)
        self.report=report
        return report,self.file

    @staticmethod
    def _focused_public(snapshot: dict) -> dict:
        """Exporta somente valores pontuais; NAO copia blocos de RAM."""
        return {
            "timestamp_utc": snapshot["timestamp_utc"],
            "watch_values":focus_watch_values(snapshot["chunks"]),
            "hypothetical_slot_u16":focus_slot_u16_values(snapshot["chunks"]),
            "field_slot_verified":False,
            "occupancy_verified":False,
        }

    def capture_no_action(self, sha: str, *, user_slot: int | None = None
                          ) -> tuple[dict, Path]:
        """Controle negativo realista: duas leituras SEM qualquer jogada.

        O usuario garante que nao houve selecao, FaceUp/Down, turno, movimento
        ou invocacao e que o slot permaneceu vazio. Os dados nao o verificam.
        """
        if self.before is None:
            raise RuntimeError("Capture 1. ANTES antes de 2X. SEM AÇÃO")
        if self.prepared is not None or self.after is not None or self.report is not None:
            raise RuntimeError("Controle SEM AÇÃO exige ANTES sem PREPARADA/NA MESA")
        if self.no_action_done or self.cancelled:
            raise RuntimeError("Controle já encerrado; clique novamente em ANTES")
        selected=self.before["user_slot"]
        if selected is not None and user_slot is not None and selected!=user_slot:
            raise ValueError("O slot mudou desde ANTES; reinicie a captura")
        user_slot=selected if selected is not None else user_slot
        if type(user_slot) is not int or not 1<=user_slot<=5:
            raise ValueError("Informe o slot visual de 1 a 5")
        sample=self._capture_same_session(sha)
        initial=self.before["snapshot"]
        target=self.before["target_id"]
        a,b=initial["chunks"],sample["chunks"]
        watch_start={item["address"]:item["u8"] for item in focus_watch_values(a)}
        watch_finish={item["address"]:item["u8"] for item in focus_watch_values(b)}
        changes=[
            {
                "address":key,"u8_before":value,
                "u8_after":watch_finish[key],
                "field_slot_verified":False,
            }
            for key,value in watch_start.items()
            if value is not None and watch_finish[key] is not None
            and value!=watch_finish[key]
        ]
        report={
            "schema":1,
            "type":"CONTROLE_SEM_ACAO_CAMPO_RAM",
            "status":"CONTROLE NEGATIVO — SEM JOGADA, DECLARADO PELO USUARIO",
            "rom_sha256_selected_manually":sample["sha"],
            "emulator_iso_verified":False,
            "pid":sample["pid"],
            "reference_card_id":target,
            "before":self._public(initial),
            "after_no_action":self._public(sample),
            "after_preparation":None,
            "after_summon":None,
            "observed_by_user":{
                "slot_position_1_to_5":user_slot,
                "slot_stayed_empty":True,
                "no_game_actions_between_samples":True,
                "card_placed_on_board":False,
                "interpretation":"DECLARADO PELO USUARIO, NAO DETECTADO PELA RAM",
            },
            "hand_analysis":{
                "target_count_before":initial["hand_ids"].count(target),
                "target_count_after":sample["hand_ids"].count(target),
                "hand_ids_unchanged":initial["hand_ids"]==sample["hand_ids"],
                "proves_no_summon":False,
            },
            "scan":{
                "address_start":f"0x{self.search_start:08X}",
                "size_bytes":self.search_size,
                "chunk_size":CHUNK_SIZE,
                "mode":"AMPLIADA_1MIB" if self.expanded else "RESTRITA_96KIB",
                "focused_enabled":self.focused,
                "focused_extra_chunk":(
                    f"0x{FOCUS_CHUNK:08X}" if self.focused and not self.expanded else None),
                "purpose":"controle sem acao; faixa experimental limitada do mesmo ePSXe",
            },
            "no_action_analysis":{
                "before_to_no_action":summarize_phase_changes(a,b),
                "focus_before_to_no_action":focus_phase_differences(a,b),
                "watched_changed_values":changes,
                "field_slot_verified":False,
                "occupancy_verified":False,
                "note":"Comparacao de volatilidade; nao demonstra ocupacao nem cancelamento.",
            },
            "hypothetical_slot_probe":{
                "before":hypothetical_slot_u16_values(a),
                "no_action":hypothetical_slot_u16_values(b),
                "field_slot_verified":False,
                "does_not_confirm_occupancy":True,
            },
            "targeted_ram_monitor":(
                {
                    "before":self._focused_public(initial),
                    "no_action":self._focused_public(sample),
                    "field_slot_verified":False,
                } if self.focused else None),
            "duel_field_card_ids":None,
            "duel_field_ram_verified":False,
            "fusion_catalog_changed":False,
            "notes":[
                "Controle realizado sem invocacao, selecao ou cancelamento no jogo.",
                "Este controle nao e equivalente a cancelar apos FaceUp/FaceDown.",
                "A ausencia de jogadas depende da confirmacao visual do usuario.",
                "Sem escrita RAM/ISO/ROM/saves, sem dump bruto, sem validar slots.",
            ],
        }
        folder=self.home/"diagnosticos_campo"/sample["sha"]
        folder.mkdir(parents=True,exist_ok=True)
        path=folder/(
            datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")+
            "_SEM_ACAO_"+str(time.time_ns())+".json")
        self._save(path,report)
        self.no_action_done=True
        return report,path

    def capture_cancelled(self, sha: str, *, user_slot: int | None = None
                          ) -> tuple[dict, Path]:
        """Controle NEGATIVO: preparar e cancelar SEM colocar no campo.

        A captura depende do usuario informar que cancelou. Se usada, encerra
        a sessao: nao e permitido registrar NA MESA depois dela.
        """
        if self.before is None or self.prepared is None:
            raise RuntimeError("Capture ANTES e PREPARADA antes de CANCELADA")
        if self.after is not None or self.report is not None:
            raise RuntimeError("NA MESA ja registrada: cancelamento nao permitido")
        if self.cancelled or self.no_action_done:
            raise RuntimeError("Controle ja concluido. Inicie novo teste com ANTES")
        frozen_slot=self.before["user_slot"]
        if frozen_slot is not None:
            if user_slot is not None and user_slot != frozen_slot:
                raise ValueError("O slot mudou desde ANTES; reinicie o diagnostico")
            user_slot=frozen_slot
        if type(user_slot) is not int or not 1<=user_slot<=5:
            raise ValueError("Informe o slot visual escolhido (1 a 5)")
        sample=self._capture_same_session(sha)
        initial=self.before["snapshot"]
        prepared=self.prepared["snapshot"]
        target=self.before["target_id"]
        report={
            "schema":1,
            "type":"CONTROLE_CANCELAMENTO_CAMPO_RAM",
            "status":"CONTROLE_NEGATIVO — NENHUMA INVOCACAO CONFIRMADA",
            "rom_sha256_selected_manually":sample["sha"],
            "emulator_iso_verified":False,
            "pid":sample["pid"],
            "reference_card_id":target,
            "before":self._public(initial),
            "after_preparation":self._public(prepared),
            "after_cancellation":self._public(sample),
            "observed_by_user":{
                "slot_position_1_to_5":user_slot,
                "face_state":self.prepared["face_state"],
                "cancellation_confirmed_visually":True,
                "card_placed_on_board":False,
                "interpretation":"DECLARADO PELO USUARIO, NAO DETECTADO PELA RAM",
            },
            "hand_analysis":{
                "target_count_before":initial["hand_ids"].count(target),
                "target_count_prepared":prepared["hand_ids"].count(target),
                "target_count_cancelled":sample["hand_ids"].count(target),
                "hand_unchanged_after_cancel":initial["hand_ids"]==sample["hand_ids"],
                "proves_no_summon":False,
            },
            "scan":{
                "address_start":f"0x{self.search_start:08X}",
                "size_bytes":self.search_size,
                "chunk_size":CHUNK_SIZE,
                "mode":"AMPLIADA_1MIB" if self.expanded else "RESTRITA_96KIB",
                "focused_enabled":self.focused,
                "focused_extra_chunk":(
                    f"0x{FOCUS_CHUNK:08X}" if self.focused and not self.expanded else None),
                "purpose":"controle negativo; area experimental do mesmo ePSXe",
            },
            "negative_control_analysis":cancelled_preparation_analysis(
                initial["chunks"],prepared["chunks"],sample["chunks"]),
            "hypothetical_slot_probe":{
                "before":hypothetical_slot_u16_values(initial["chunks"]),
                "prepared":hypothetical_slot_u16_values(prepared["chunks"]),
                "cancelled":hypothetical_slot_u16_values(sample["chunks"]),
                "field_slot_verified":False,
                "does_not_confirm_occupancy":True,
            },
            "targeted_ram_monitor":(
                {
                    "status":"HIPOTESES_DE_SELECAO_NAO_VALIDADAS_COMO_CAMPO",
                    "before":self._focused_public(initial),
                    "prepared":self._focused_public(prepared),
                    "cancelled":self._focused_public(sample),
                    "field_slot_verified":False,
                } if self.focused else None),
            "after_summon":None,
            "duel_field_card_ids":None,
            "duel_field_ram_verified":False,
            "fusion_catalog_changed":False,
            "notes":[
                "Esta sessao NAO pode ser usada como prova de invocacao no campo.",
                "Cancelar deve ocorrer antes da carta ser fisicamente posicionada.",
                "Nao ha escrita na RAM, nem modificacao de ISO, saves ou fusoes.",
                "Os enderecos sao candidatos, nao um mapa validado dos slots.",
            ],
        }
        folder=self.home/"diagnosticos_campo"/sample["sha"]
        folder.mkdir(parents=True,exist_ok=True)
        path=folder/(
            datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")+
            "_CANCELADA_"+str(time.time_ns())+".json")
        self._save(path,report)
        self.cancelled=True
        self.cancel_file=path
        return report,path

    @staticmethod
    def _save(path,report):
        tmp=path.with_name(path.name+".tmp")
        tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        tmp.replace(path)

    def capture_removed(self, sha: str) -> tuple[dict,Path]:
        if self.before is None or self.after is None or self.report is None:
            raise RuntimeError("Capture ANTES e NA MESA antes de registrar a remoção")
        if self.removed_sample is not None:
            raise RuntimeError("REMOVIDA já registrada; use VAZIA ESTÁVEL ou inicie novo teste")
        sample=self._capture_same_session(sha)
        self.removed_sample=sample
        initial=self.before["snapshot"]
        target=self.before["target_id"]
        # O usuário confirmou visualmente a remoção; os bytes são evidência
        # experimental e não atestam que houve realmente a remoção.
        report=dict(self.report)
        report["after_removal"]=self._public(sample)
        if self.focused:
            monitor=dict(report["targeted_ram_monitor"])
            monitor["removed"]=self._focused_public(sample)
            monitor["focus_set_to_removed"]=focus_phase_differences(
                self.after["chunks"],sample["chunks"])
            report["targeted_ram_monitor"]=monitor
        probe=dict(report["hypothetical_slot_probe"])
        probe["removed"]=hypothetical_slot_u16_values(sample["chunks"])
        report["hypothetical_slot_probe"]=probe
        reference=self.prepared["snapshot"] if self.prepared else initial
        report["analysis"]=find_new_id_candidates(
            reference["chunks"],self.after["chunks"],target,
            after_removed=sample["chunks"])
        phases=dict(report["phase_differences"])
        phases["set_to_removed"]=summarize_phase_changes(
            self.after["chunks"],sample["chunks"])
        report["phase_differences"]=phases
        report["occupancy_analysis"]=self._occupancy_analysis()
        report["notes"]=report["notes"]+[
            "A remoção foi informada visualmente pelo usuário; "
            "o desaparecimento do padrão em RAM ainda não valida o slot."
        ]
        self._save(self.file,report)
        self.report=report
        return report,self.file
