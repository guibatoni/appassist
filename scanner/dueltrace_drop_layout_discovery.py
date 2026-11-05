"""Busca determinística e limitada por tabelas de drops WA realocadas.

Prova apenas 39*3 matrizes de 722 pesos com soma 2048 cada, mesmo
layout e contêiner. Não confirma nomes das três classes de RANK,
identidade dos duelistas nem execução do jogo; sem catálogo validado
não se publicam associações de cartas.
"""
from __future__ import annotations

import struct

WEIGHTS=722
OPPONENTS=39
RANK_GROUPS=3
WEIGHT_TOTAL=2048
MAX_WA_BYTES=96*1024*1024
MAX_SHIFT_BYTES=128*1024
MAX_LAYOUTS=4
MAX_OFFSETS=25000
# Famílias de blocos de sector observáveis em mods PS1; adaptadores
# adicionais podem fornecer strides sem mudar o parser de cartas.
OPPONENT_STEPS=(0x1800,0x1C00,0x2000,0x1400)
RANK_STRIDES=(0x5B4,0x5C0,0x600)


def _table_weights(blob:bytes,offset:int)->bool:
    if offset<0 or offset+WEIGHTS*2>len(blob):
        return False
    words=struct.unpack_from("<722H",blob,offset)
    if max(words)<=WEIGHT_TOTAL:
        return sum(words)==WEIGHT_TOTAL
    if min(words)<2512 or max(words)>18896:
        return False
    return (all((x-2512)%8<=6 for x in words)
            and sum((x-2512)//8 for x in words)==WEIGHT_TOTAL)


def discover_relocated_drops(wa:bytes, *, known_base:int,
                             decode_at_layout,
                             max_shift:int=MAX_SHIFT_BYTES)->dict:
    """Procura contêiner FM compatível, sem atribuir nomes aos RANKs.

    `decode_at_layout(base, opponent_step, rank_stride)` deve validar
    todas as 117 matrizes por conteúdo. Uma hipótese ambígua fica
    indisponível, e mesmo uma única prova é só estrutural.
    """
    result={"schema":1,"state":"nao_encontrado","validated":False,
            "inGameVerified":False,"rankLabelsVerified":False,
            "candidates":[],"selected":None,"offsetsExamined":0,
            "scanRadius":0,"strategy":"bounded_content_and_117_tables"}
    if (not isinstance(wa,bytes) or len(wa)>MAX_WA_BYTES
            or type(known_base) is not int or known_base<0
            or not callable(decode_at_layout)):
        result["state"]="entrada_invalida"
        return result
    radius=(max(0,min(MAX_SHIFT_BYTES,max_shift))
            if type(max_shift) is int else 0)
    result["scanRadius"]=radius
    if len(wa)<WEIGHTS*2*RANK_GROUPS*OPPONENTS:
        result["state"]="recurso_pequeno_ou_incompativel"
        return result
    lo=max(0,known_base-radius)
    hi=min(len(wa)-WEIGHTS*2*RANK_GROUPS,known_base+radius)
    if hi<lo:
        return result
    # Priorizar blocos alinhados a 2048, comuns nos contêineres PS1,
    # depois alinhamento de 16 bytes e só então 4 bytes em raio pequeno.
    offsets=[]
    used=set()
    for step,r in ((2048,radius),(16,radius),(4,min(radius,8192))):
        a=max(lo,known_base-r)
        z=min(hi,known_base+r)
        a+=(-a)%step
        for base in range(a,z+1,step):
            if base not in used:
                used.add(base)
                offsets.append(base)
            if len(offsets)>=MAX_OFFSETS:
                break
        if len(offsets)>=MAX_OFFSETS:
            break
    # O offset convencional também é um candidato quando a etapa de
    # drops anterior falhou; nesse caso a geometria pode ter outro stride.
    if lo<=known_base<=hi and known_base not in used:
        offsets.insert(0,known_base)
    candidates=[]
    for base in offsets:
        result["offsetsExamined"]+=1
        for rank_stride in RANK_STRIDES:
            if not _table_weights(wa,base+rank_stride):
                continue
            if not (_table_weights(wa,base+2*rank_stride)
                    and _table_weights(wa,base+3*rank_stride)):
                continue
            for opp_step in OPPONENT_STEPS:
                if opp_step<3*rank_stride+WEIGHTS*2:
                    continue
                if base+(OPPONENTS-1)*opp_step+3*rank_stride+WEIGHTS*2>len(wa):
                    continue
                if not all(_table_weights(wa,base+i*opp_step+ri*rank_stride)
                           for i in (1,19,38) for ri in (1,2,3)):
                    continue
                try:
                    decoded,status=decode_at_layout(base,opp_step,rank_stride)
                except (ValueError,OverflowError,struct.error):
                    continue
                if not (isinstance(decoded,dict)
                        and len(decoded.get("verificacao",[]))==117
                        and len(decoded.get("drops",[]))>0):
                    continue
                candidates.append({
                    "opponentBase":base,
                    "opponentStep":opp_step,
                    "rankStride":rank_stride,
                    "matrixCount":117,
                    "status":"estrutural_nao_validado_no_jogo",
                    "validated":False,
                    "rankLabelsVerified":False,
                })
                if len(candidates)>=MAX_LAYOUTS:
                    break
            if len(candidates)>=MAX_LAYOUTS:
                break
        if len(candidates)>=MAX_LAYOUTS:
            break
    result["candidates"]=candidates
    if len(candidates)==1:
        result["state"]="layout_candidato_unico"
        result["selected"]=dict(candidates[0])
    elif candidates:
        result["state"]="layouts_ambiguos"
    return result
