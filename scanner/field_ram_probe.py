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


class FieldMemoryProbe:
    """Ferramenta de bancada: 3 estados de um monstro conhecido.

    A) monstro ainda na mão, ausente da mesa (confirmado visualmente);
    B) monstro invocado na mesa;
    C) monstro removido da mesa (opcional).
    """

    def __init__(self, reader_provider, home: Path):
        self.reader_provider=reader_provider
        self.home=Path(home)
        self.before=None
        self.after=None
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
        for addr in range(SEARCH_START,SEARCH_START+SEARCH_SIZE,CHUNK_SIZE):
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
        self.after=None
        self.report=None
        self.file=None
        return self._public(sample)

    def capture_after(self, sha: str) -> tuple[dict,Path]:
        if self.before is None:
            raise RuntimeError("Primeiro capture o estado ANTES da invocação")
        sample=self._capture(sha)
        initial=self.before["snapshot"]
        target=self.before["target_id"]
        if sample["sha"]!=initial["sha"] or sample["pid"]!=initial["pid"]:
            raise RuntimeError("ISO ou PID do ePSXe mudou; inicie outro diagnóstico")
        if sample["hand_ids"].count(target)>=initial["hand_ids"].count(target):
            raise RuntimeError("O ID escolhido não saiu da mão; confira a invocação antes de capturar")
        self.after=sample
        candidates=find_new_id_candidates(initial["chunks"],sample["chunks"],target)
        report={
            "schema":1,"type":"DIAGNOSTICO_CAMPO_RAM",
            "status":"HIPOTESES — NENHUM SLOT DO CAMPO VALIDADO",
            "rom_sha256_selected_manually":sample["sha"],
            "emulator_iso_verified":False,"pid":sample["pid"],
            "reference_card_id":target,
            "before":self._public(initial),
            "after_summon":self._public(sample),
            "after_removal":None,
            "scan":{"address_start":f"0x{SEARCH_START:08X}",
                    "size_bytes":SEARCH_SIZE,"chunk_size":CHUNK_SIZE,
                    "purpose":"janela exploratoria em torno da mao conhecida"},
            "analysis":candidates,
            "duel_field_card_ids":None,
            "duel_field_ram_verified":False,
            "fusion_catalog_changed":False,
            "notes":[
                "A carta que saiu da mão não comprova que entrou no campo; evento informado pelo usuário.",
                "Um ID de dois bytes pode ocorrer em estruturas não relacionadas a cartas.",
                "Somente uma área de 96 KiB próxima à mão foi pesquisada; "
                "sem candidatos não significa que o campo não possa ser mapeado.",
                "Nenhum dump bruto da memória é incluído neste relatório.",
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

    @staticmethod
    def _save(path,report):
        tmp=path.with_name(path.name+".tmp")
        tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        tmp.replace(path)

    def capture_removed(self, sha: str) -> tuple[dict,Path]:
        if self.before is None or self.after is None or self.report is None:
            raise RuntimeError("Capture ANTES e DEPOIS da invocação antes de registrar a remoção")
        sample=self._capture(sha)
        initial=self.before["snapshot"]
        if sample["sha"]!=initial["sha"] or sample["pid"]!=initial["pid"]:
            raise RuntimeError("ISO ou processo ePSXe mudou; não é possível comparar")
        target=self.before["target_id"]
        # O usuário confirmou visualmente a remoção; os bytes são evidência
        # experimental e não atestam que houve realmente a remoção.
        report=dict(self.report)
        report["after_removal"]=self._public(sample)
        report["analysis"]=find_new_id_candidates(
            initial["chunks"],self.after["chunks"],target,
            after_removed=sample["chunks"])
        report["notes"]=report["notes"]+[
            "A remoção foi informada visualmente pelo usuário; "
            "o desaparecimento do padrão em RAM ainda não valida o slot."
        ]
        self._save(self.file,report)
        self.report=report
        return report,self.file
