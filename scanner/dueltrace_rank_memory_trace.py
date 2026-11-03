"""Evidência dinâmica de LEITURA da tabela de RANK por instruções MIPS.

Formato opcional de depurador instrumentado:
 PC=0x80012040 PHASE=RANK OP=LHU ADDR=0x80030000 VALUE=0x0005
 PC=0x80012044 PHASE=RANK OP=LH  ADDR=0x80030002 VALUE=0x000C

Para reconhecer um par, o valor de LHU (limiar) e o de LH
(pontos assinados) devem corresponder ao mesmo par extraído da
tabela WA da ISO ativa e vir de endereços adjacentes. Não depende de
offset ROM fixo. Dados de logs externos NÃO são autenticados; nenhuma
inferência aqui confirma causalidade MIPS ou a fórmula completa.
"""
from __future__ import annotations

import re
from collections import defaultdict

MAX_TRACE_BYTES=8*1024*1024
MAX_TRACE_LINES=250_000
MAX_EVENTS=50_000
MIN_PAIRS=4
WINDOW_BYTES=56*4
LINE_PATTERN=re.compile(
    r"^.*?\bPC=(0x[0-9A-Fa-f]{8})\s+PHASE=RANK\s+"
    r"OP=(LHU|LH)\s+ADDR=(0x[0-9A-Fa-f]{8})\s+"
    r"VALUE=(0x[0-9A-Fa-f]{1,8})(?:\s|$)"
)


def _empty(status: str):
    return {
        "status":status,"available":False,"tableReadsObserved":False,
        "rankRoutineConfirmed":False,"scoringCausalityConfirmed":False,
        "matchedPairs":0,"uniqueValues":0,"candidateWindows":[],
        "memoryEvents":0,"reason":"Somente pares de leituras WA observados não provam a rotina final de RANK.",
    }


def inspect_rank_memory_trace(trace: bytes, rank_points: dict | None,
                              rank_evidence: dict | None) -> dict:
    if not isinstance(trace,bytes) or not 0<len(trace)<=MAX_TRACE_BYTES:
        return _empty("invalid_trace")
    if (not isinstance(rank_points,dict) or
            rank_points.get("available") is not True or
            not isinstance(rank_points.get("rules"),dict)):
        return _empty("rank_table_not_extracted")
    if (not isinstance(rank_evidence,dict) or
            rank_evidence.get("available") is not True):
        return _empty("mips_candidates_missing")
    rows=rank_points["rules"]
    known_pairs=set()
    pair_positions=defaultdict(list)
    for bands in rows.values():
        if not isinstance(bands,list):
            return _empty("invalid_rank_table")
        for pair in bands:
            if not isinstance(pair,dict):
                return _empty("invalid_rank_table")
            limit,score=pair.get("below"),pair.get("points")
            if type(limit) is not int or type(score) is not int:
                return _empty("invalid_rank_table")
            if not 0<=limit<=32767 or not -32768<=score<=32767:
                return _empty("invalid_rank_table")
            known_pairs.add((limit,score))
    # Ordem dos pares no perfil é a mesma dos 10 critérios × 5 faixas
    # extraídos pelo decoder. Cada par ocupa exatamente 4 bytes.
    index=0
    table_length=sum(len(b) for b in rows.values())*4
    for bands in rows.values():
        for pair in bands:
            pair_positions[(pair["below"],pair["points"])].append(index)
            index+=1
    if len(known_pairs)<MIN_PAIRS:
        return _empty("insufficient_unique_rule_pairs")
    windows=[]
    for item in rank_evidence.get("candidates",[])[:20]:
        if not isinstance(item,dict) or not isinstance(item.get("pc"),str):
            continue
        try:
            pc=int(item["pc"],16)
        except ValueError:
            continue
        if 0x80000000<=pc<=0x801fffff:
            windows.append((pc,pc+WINDOW_BYTES))
    if not windows:
        return _empty("mips_windows_missing")
    # Para cada janela, manter pares endereço -> valores observados. A leitura
    # é unicamente local e o log original não fica salvo no perfil.
    seen=defaultdict(lambda: {"limit":defaultdict(set),"score":defaultdict(set)})
    events=0
    for idx,line in enumerate(trace.splitlines()):
        if idx>=MAX_TRACE_LINES:
            return _empty("trace_line_limit_exceeded")
        match=LINE_PATTERN.match(line.decode("ascii","ignore")[:320])
        if match is None:
            continue
        pc=int(match.group(1),16)
        op=match.group(2)
        address=int(match.group(3),16)
        value=int(match.group(4),16)&0xffff
        if not (0x80000000<=address<=0x801fffff and address%2==0):
            continue
        events+=1
        if events>MAX_EVENTS:
            return _empty("trace_event_limit_exceeded")
        if op=="LH" and value&0x8000:
            value-=0x10000
        for start,end in windows:
            if start<=pc<end:
                column="limit" if op=="LHU" else "score"
                seen[start][column][address].add(value)
    found=[]
    for start,fields in seen.items():
        # O mesmo deslocamento RAM-base deve explicar todos os pares.
        # Correspondências isoladas por valor são insuficientes.
        possible_bases=defaultdict(lambda:{"indices":set(),"pairs":set(),
                                           "addresses":set()})
        for addr,limits in fields["limit"].items():
            scores=fields["score"].get(addr+2,set())
            valid={(limit,score) for limit in limits for score in scores
                   if (limit,score) in known_pairs}
            for pair in valid:
                for index in pair_positions[pair]:
                    base=addr-4*index
                    if (base<0x80000000 or
                            base+table_length>0x80200000):
                        continue
                    sample=possible_bases[base]
                    sample["indices"].add(index)
                    sample["addresses"].add(addr)
                    sample["pairs"].add(pair)
        for base,sample in possible_bases.items():
            if (len(sample["indices"])<MIN_PAIRS or
                    len(sample["addresses"])<MIN_PAIRS or
                    len(sample["pairs"])<MIN_PAIRS):
                continue
            found.append({
                "candidatePC":f"0x{start:08X}",
                "matchedPairs":len(sample["pairs"]),
                "distinctTableAddresses":len(sample["addresses"]),
                "valuePairs":[{"threshold":limit,"points":score}
                              for limit,score in sorted(sample["pairs"])[:12]],
                "memoryBaseCandidate":f"0x{base:08X}",
                "status":"table_value_reads_corroborated",
            })
    found.sort(key=lambda row:(-row["matchedPairs"],row["candidatePC"]))
    return {
        **_empty("table_reads_corroborated" if found else
                 "no_sufficient_table_reads"),
        "available":True,"tableReadsObserved":bool(found),
        "matchedPairs":max((x["matchedPairs"] for x in found),default=0),
        "uniqueValues":len(known_pairs),
        "candidateWindows":found[:6],
        "memoryEvents":events,
        "reason":("Foram vistos múltiplos pares limiar/pontos da tabela WA em "
                  "acessos LHU/LH a endereços adjacentes, próximos a código "
                  "MIPS candidato. Confirmação causal do cálculo final "
                  "continua pendente."),
    }
