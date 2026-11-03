"""Confirmação de EXECUÇÃO de PCs candidatos usando trace de emulador.

Exige log de instruções executadas exportado pelo depurador durante duelo.
Não interpreta desassembly estático como execução e não confirma que um PC
seja especificamente responsável pelo RANK sem análise de fluxo de dados.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter

MAX_TRACE_BYTES=8*1024*1024
MAX_TRACE_LINES=250_000
MAX_CANDIDATES=20
PC_PATTERN=re.compile(
    r"(?:^|[\s,;])(?:PC|pc|Pc)\s*[:=]\s*(?:0x)?([0-9A-Fa-f]{8})(?![0-9A-Fa-f])"
)


def inspect_duel_mips_trace(trace: bytes,
                            rank_evidence: dict | None) -> dict:
    empty={
        "available":False,"status":"trace_unavailable",
        "source":"log_de_execucao_fornecido_pelo_usuario",
        "executedCandidates":[],"instructionSamples":0,
        "distinctPCs":0,"executionEvidence":False,
        "rankRoutineConfirmed":False,
        "note":"Execução de PCs candidatos não prova cálculo de RANK.",
    }
    if (not isinstance(trace,bytes) or not 0<len(trace)<=MAX_TRACE_BYTES
            or not isinstance(rank_evidence,dict)):
        return empty
    if (rank_evidence.get("available") is not True
            or not isinstance(rank_evidence.get("candidates"),list)):
        return {**empty,"status":"missing_static_mips_candidates"}
    targets={}
    for item in rank_evidence["candidates"][:MAX_CANDIDATES]:
        if not isinstance(item,dict) or not isinstance(item.get("pc"),str):
            continue
        try:
            pc=int(item["pc"],16)
        except ValueError:
            continue
        if 0x80000000<=pc<0x80200000:
            targets[pc]=item["pc"].upper().replace("0X","0x")
    if not targets:
        return {**empty,"status":"no_candidate_pcs"}
    counts=Counter()
    unique=set()
    samples=0
    lines=0
    for line in trace.splitlines():
        lines+=1
        if lines>MAX_TRACE_LINES:
            return {**empty,"status":"trace_too_many_lines"}
        # Logs devem registrar explicitamente o PC; evitar comparar
        # offsets citados em relatórios de disassembly estático.
        text=line.decode("ascii","ignore")[:400]
        match=PC_PATTERN.search(text)
        if match is None:
            continue
        pc=int(match.group(1),16)
        if not 0x80000000<=pc<0x80200000:
            continue
        samples+=1
        if len(unique)<5000:
            unique.add(pc)
        if pc in targets:
            counts[pc]+=1
    # Um único endereço escrito em arquivo texto não é um trace sério.
    quality=samples>=30 and len(unique)>=8
    found=[
        {"pc":targets[pc],"hits":n}
        for pc,n in sorted(counts.items(),key=lambda v:-v[1])
    ]
    return {
        **empty,
        "available":True,
        "status":("candidate_pc_executed" if found and quality else
                  "insufficient_execution_trace" if not quality else
                  "candidate_pc_not_observed"),
        "instructionSamples":samples,"distinctPCs":len(unique),
        "executedCandidates":found if quality else [],
        "executionEvidence":bool(found and quality),
        "traceSha256":hashlib.sha256(trace).hexdigest(),
        "note":("PCs de candidatos MIPS foram observados no trace "
                "exportado do emulador. Não é possível concluir apenas "
                "disso que calculam o RANK; é necessário correlacionar "
                "leituras de tabela, pontos e fim do duelo."),
    }
