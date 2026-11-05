"""Investiga atributos de cartas em tabelas PS1 movidas, sem publicar dados.

O layout observado em FM usa 722 palavras LE de 32 bits:
  ATK(9) | DEF(9) | estrela1(4) | estrela2(4) | tipo(5)
e 722 bytes separados: nível(4) | atributo(4).

Heurísticas só apontam candidatos. Nem o encaixe estatístico nem as
referências MIPS comprovam a semântica, os IDs ou a execução em jogo.
"""
from __future__ import annotations

import hashlib
import struct

from dueltrace_name_boundaries import read_name_table
from dueltrace_card_opponent_discovery import _plausible_name

CARD_COUNT=722
MAX_EXE_BYTES=8*1024*1024
MAX_SHIFT_BYTES=16384
MAX_NAME_LAYOUTS=6
MAX_TABLE_CANDIDATES=6
MAX_LINKS=12

# IDs distribuídos pelo catálogo; os extremos têm proteção extra.
SAMPLES=(1,2,3,7,19,33,51,74,100,125,151,178,205,237,270,
         303,335,366,398,431,463,495,526,559,591,625,658,690,
         717,720,721,722)
NAME_INDICES=tuple(range(1,723))+tuple(range(0x329,0x350))


def _packed_word(word:int)->tuple[int,int,int,int,int]:
    return (word&511,(word>>9)&511,(word>>26)&31,
            (word>>18)&15,(word>>22)&15)


def _packed_sample(exe:bytes,offset:int,ids= SAMPLES)->float|None:
    if offset<0 or offset+CARD_COUNT*4>len(exe):
        return None
    # Um deslocamento de uma carta dentro da mesma tabela também pode
    # parecer plausível. Exigir extremos não vazios e observar a fronteira.
    if (exe[offset:offset+4]==b"\0"*4 or
            exe[offset+(CARD_COUNT-1)*4:offset+CARD_COUNT*4]==b"\0"*4):
        return None
    rows=[_packed_word(struct.unpack_from("<I",exe,offset+(i-1)*4)[0])
          for i in ids]
    stats=sum(atk%5==0 and defense%5==0 for atk,defense,*_ in rows)
    types=sum(type_id<=23 for _,_,type_id,_,_ in rows)
    nonzero=sum(bool(atk or defense) for atk,defense,*_ in rows)
    distinct=len({(atk,defense) for atk,defense,*_ in rows})
    kind=len({r[2] for r in rows})
    n=len(rows)
    if (stats*100<75*n or types*100<88*n or
            nonzero*100<65*n or distinct<22 or kind<5):
        return None
    boundary=(int(offset>=4 and exe[offset-4:offset]==b"\0"*4)
              +int(offset+CARD_COUNT*4+4<=len(exe) and
                   exe[offset+CARD_COUNT*4:offset+CARD_COUNT*4+4]==b"\0"*4))
    return (stats/n*55+types/n*15+nonzero/n*10+
            min(1,distinct/28)*10+min(1,kind/9)*10+boundary*12)


def _full_packed(exe:bytes,offset:int)->dict|None:
    if offset<0 or offset+CARD_COUNT*4>len(exe):
        return None
    atks=set()
    pairs=set()
    types=set()
    reasonable=nonzero=within=0
    for (word,) in struct.iter_unpack(
        "<I",exe[offset:offset+CARD_COUNT*4]
    ):
        attack,defense,kind,_,_=_packed_word(word)
        atks.add(attack)
        pairs.add((attack,defense))
        types.add(kind)
        reasonable+=attack%5==0 and defense%5==0
        nonzero+=bool(attack or defense)
        within+=kind<=23
    if (reasonable<540 or nonzero<470 or within<640 or
            len(pairs)<110 or len(types)<7 or len(atks)<35):
        return None
    return {"statsMultiple50":reasonable,
            "nonzeroStats":nonzero,
            "typesInExpectedRange":within,
            "distinctPairs":len(pairs),
            "distinctTypes":len(types)}


def _detail_sample(exe:bytes,base:int,ids=SAMPLES)->float|None:
    if base<0 or base+CARD_COUNT>len(exe):
        return None
    if exe[base]==0 or exe[base+CARD_COUNT-1]==0:
        return None
    data=[exe[base+i-1] for i in ids]
    level=[x&15 for x in data]
    attr=[x>>4 for x in data]
    reasonable=sum(a<=8 and l<=12 for a,l in zip(attr,level))
    if (reasonable*100<90*len(data) or
            len(set(level))<5 or len(set(attr))<4
            or sum(bool(x) for x in data)<23):
        return None
    boundary=(int(base>0 and exe[base-1]==0)
              +int(base+CARD_COUNT<len(exe) and
                   exe[base+CARD_COUNT]==0))
    return (reasonable/len(data)*70+
            min(1,len(set(level))/9)*15+
            min(1,len(set(attr))/7)*15+boundary*12)


def _full_details(exe:bytes,offset:int)->dict|None:
    if offset<0 or offset+CARD_COUNT>len(exe):
        return None
    raw=exe[offset:offset+CARD_COUNT]
    levels={x&15 for x in raw}
    attrs={x>>4 for x in raw}
    plausible=sum((x&15)<=12 and (x>>4)<=8 for x in raw)
    if plausible<650 or len(levels)<7 or len(attrs)<5:
        return None
    return {"plausibleCodes":plausible,"distinctLevels":len(levels),
            "distinctAttributes":len(attrs)}


def _scan_packed(exe:bytes,base:int,radius:int)->tuple[list[dict],int]:
    candidates=[]
    tested=0
    start=max(0,base-radius)
    end=min(len(exe)-CARD_COUNT*4,base+radius)
    start+=(base-start)%4
    for offset in range(start,end+1,4):
        tested+=1
        score=_packed_sample(exe,offset)
        if score is None:
            continue
        metrics=_full_packed(exe,offset)
        if metrics is not None:
            candidates.append({"offset":offset,"shift":offset-base,
                               "score":round(score,3),**metrics})
    candidates.sort(key=lambda v:(-v["score"],abs(v["shift"]),v["offset"]))
    return candidates[:MAX_TABLE_CANDIDATES],tested


def _scan_details(exe:bytes,base:int,radius:int)->tuple[list[dict],int]:
    candidates=[]
    tested=0
    start=max(0,base-radius)
    end=min(len(exe)-CARD_COUNT,base+radius)
    for offset in range(start,end+1):
        tested+=1
        score=_detail_sample(exe,offset)
        if score is None:
            continue
        metrics=_full_details(exe,offset)
        if metrics is not None:
            candidates.append({"offset":offset,"shift":offset-base,
                               "score":round(score,3),**metrics})
    candidates.sort(key=lambda v:(-v["score"],abs(v["shift"]),v["offset"]))
    return candidates[:MAX_TABLE_CANDIDATES],tested


def _names_in_same_executable(exe:bytes,name_layouts:list[dict])->list[dict]:
    viable=[]
    for candidate in name_layouts[:MAX_NAME_LAYOUTS]:
        if not isinstance(candidate,dict):
            continue
        p,t,g=(candidate.get(k) for k in ("pointerBase","textBase","glyphBase"))
        if not all(type(x) is int and 0<=x<len(exe) for x in (p,t,g)):
            continue
        try:
            rows=read_name_table(exe,pointer_base=p,text_base=t,
                                 glyph_base=g,indices=NAME_INDICES,max_bytes=100)
        except (ValueError,UnicodeError,struct.error):
            continue
        def recognized(i):
            row=rows[i]
            return row["recordStatus"]=="ff_encontrado" and _plausible_name(
                row["readablePrefix"])
        if not all(recognized(i) for i in (1,100,722,0x329,0x34F)):
            continue
        cards=sum(recognized(i) for i in range(1,723))
        opponents=sum(recognized(i) for i in range(0x329,0x350))
        if cards<720 or opponents<38:
            continue
        viable.append({"pointerBase":p,"textBase":t,"glyphBase":g,
                       "names":rows,"cardCount":cards,"opponentCount":opponents})
    return viable


def discover_card_attribute_layout(
    exe:bytes, *, name_layouts:list[dict],
    packed_base:int,detail_base:int,max_shift:int=MAX_SHIFT_BYTES
)->dict:
    """Cruza nomes e duas estruturas de atributos só nesta mesma imagem.

    Retorna amostras de IDs e métricas limitadas. Nenhuma saída possui
    verified=true; ativação de cartas e drops continua independente.
    """
    report={"schema":1,"state":"sem_evidencia","validated":False,
            "inGameVerified":False,"exeSha256":None,"links":[],
            "packedCandidates":[],"detailCandidates":[],
            "packedPositionsExamined":0,"detailPositionsExamined":0,
            "nameLayoutsExamined":0}
    if (not isinstance(exe,bytes) or len(exe)>MAX_EXE_BYTES or
            type(packed_base) is not int or type(detail_base) is not int or
            packed_base<0 or detail_base<0 or
            not isinstance(name_layouts,list)):
        report["state"]="entrada_invalida"
        return report
    report["exeSha256"]=hashlib.sha256(exe).hexdigest()
    radius=(max(0,min(max_shift,MAX_SHIFT_BYTES))
            if type(max_shift) is int else 0)
    report["radiusBytes"]=radius
    layouts=_names_in_same_executable(exe,name_layouts)
    report["nameLayoutsExamined"]=min(len(name_layouts),MAX_NAME_LAYOUTS)
    if not layouts:
        report["state"]="nomes_nao_identificados"
        return report
    packed,pc=_scan_packed(exe,packed_base,radius)
    details,dc=_scan_details(exe,detail_base,radius)
    report["packedCandidates"]=packed
    report["detailCandidates"]=details
    report["packedPositionsExamined"]=pc
    report["detailPositionsExamined"]=dc
    if not packed or not details:
        report["state"]="atributos_nao_identificados"
        return report
    # A leitura dentro da tabela compactada pode, acidentalmente, parecer
    # uma tabela de bytes de detalhes. As duas tabelas FM são separadas.
    # Filtramos candidatos fracos comparados à melhor fronteira observada,
    # mas preservamos múltiplas hipóteses fortes sem escolher um vencedor.
    strongest_packed=packed[0]["score"]
    strongest_detail=details[0]["score"]
    packed=[x for x in packed if x["score"]>=strongest_packed-14]
    details=[x for x in details if x["score"]>=strongest_detail-14]
    report["packedCandidates"]=packed
    report["detailCandidates"]=details
    # Bases das duas tabelas podem mudar independentemente. Preferir
    # deslocamentos iguais apenas para ORDENAR hipóteses, nunca para validar.
    combinations=sorted(
        ((a,b) for a in packed for b in details
         if (a["offset"]+CARD_COUNT*4<=b["offset"] or
             b["offset"]+CARD_COUNT<=a["offset"])),
        key=lambda pair:(pair[0]["shift"]!=pair[1]["shift"],
                         -(pair[0]["score"]+pair[1]["score"]),
                         abs(pair[0]["shift"]-pair[1]["shift"]))
    )
    for names in layouts:
        for a,b in combinations:
            previews=[]
            for i in (1,100,350,500,722):
                packed_word=struct.unpack_from("<I",exe,
                                            a["offset"]+(i-1)*4)[0]
                atk,defense,kind,star1,star2=_packed_word(packed_word)
                detail=exe[b["offset"]+i-1]
                previews.append({
                    "id":i,"name":names["names"][i]["readablePrefix"][:52],
                    "atk":atk*10,"def":defense*10,"typeCode":kind,
                    "levelCode":detail&15,"attributeCode":detail>>4,
                    "star1Code":star1,"star2Code":star2})
            report["links"].append({
                "namePointerBase":names["pointerBase"],
                "nameTextBase":names["textBase"],
                "nameGlyphBase":names["glyphBase"],
                "packedBase":a["offset"],"detailBase":b["offset"],
                "packedShift":a["shift"],"detailShift":b["shift"],
                "sharedShift":a["shift"]==b["shift"],
                "nameCounts":{"cards":names["cardCount"],
                              "opponents":names["opponentCount"]},
                "samples":previews,"validated":False,
                "inGameVerified":False,
            })
            if len(report["links"])>=MAX_LINKS:
                break
        if len(report["links"])>=MAX_LINKS:
            break
    report["state"]=("candidatos_vinculados" if len(report["links"])==1
                     else "hipoteses_ambiguas" if report["links"]
                     else "atributos_nao_identificados")
    return report
