"""Quarentena de catálogos reconstruídos de ISOs sem layout confirmado.

Produz 722 registros de carta + 39 de oponentes com offsets e SHA do
executável, somente quando nome e atributos têm UMA combinação estrutural.
Nunca preenche profiles/cards nem marca efeitos, drops ou IDs verificados
em execução. A saída serve exclusivamente à revisão de engenharia reversa.
"""
from __future__ import annotations

import hashlib
import re
import struct

from dueltrace_name_boundaries import read_name_table
from dueltrace_card_opponent_discovery import _plausible_name
from dueltrace_catalog_validation import validate_identity_catalogs

CARD_COUNT=722
OPPONENT_COUNT=39
MAX_EXE_BYTES=8*1024*1024
INDICES=tuple(range(1,CARD_COUNT+1))+tuple(range(0x329,0x350))


def build_quarantined_catalog(exe:bytes,rom_sha256:str,probe:dict)->dict:
    output={"schema":1,"status":"indisponivel","romSha256":None,
            "exeSha256":None,"cards":[],"opponents":[],
            "cardsCount":0,"opponentsCount":0,"validated":False,
            "inGameVerified":False,"mayActivate":False}
    if (not isinstance(exe,bytes) or not 0<len(exe)<=MAX_EXE_BYTES
            or type(rom_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}",rom_sha256)
            or not isinstance(probe,dict)):
        output["status"]="entrada_invalida"
        return output
    digest=hashlib.sha256(exe).hexdigest()
    output["romSha256"]=rom_sha256
    output["exeSha256"]=digest
    if probe.get("exeSha256")!=digest:
        output["status"]="assinatura_executavel_divergente"
        return output
    links=probe.get("links")
    if (probe.get("state")!="candidatos_vinculados"
            or not isinstance(links,list) or len(links)!=1):
        output["status"]="layout_nao_unico"
        return output
    link=links[0]
    if not isinstance(link,dict):
        output["status"]="layout_invalido"
        return output
    fields=("namePointerBase","nameTextBase","nameGlyphBase",
            "packedBase","detailBase")
    if not all(type(link.get(k)) is int and 0<=link[k]<len(exe)
               for k in fields):
        output["status"]="offset_invalido"
        return output
    packed,detail=link["packedBase"],link["detailBase"]
    if (packed+CARD_COUNT*4>len(exe)
            or detail+CARD_COUNT>len(exe)):
        output["status"]="tabelas_incompletas"
        return output
    try:
        names=read_name_table(
            exe,pointer_base=link["namePointerBase"],
            text_base=link["nameTextBase"],
            glyph_base=link["nameGlyphBase"],
            indices=INDICES,max_bytes=100)
    except (ValueError,UnicodeError,struct.error):
        output["status"]="nomes_incompativeis"
        return output
    if not all(row["recordStatus"]=="ff_encontrado"
               and _plausible_name(row["readablePrefix"])
               for row in names.values()):
        output["status"]="nomes_incompletos"
        return output
    cards=[]
    for i in range(1,CARD_COUNT+1):
        word=struct.unpack_from("<I",exe,packed+(i-1)*4)[0]
        byte=exe[detail+i-1]
        cards.append({
            "id":i,"nome":names[i]["readablePrefix"],
            "atk":(word&511)*10,
            "def":((word>>9)&511)*10,
            "tipo":(word>>26)&31,
            "nivel":byte&15,
            "atributo":(byte>>4)&15,
            "estrela_1":(word>>18)&15,
            "estrela_2":(word>>22)&15,
        })
    opponents=[{"id":i,"nome":names[0x328+i]["readablePrefix"]}
               for i in range(1,OPPONENT_COUNT+1)]
    validation=validate_identity_catalogs(cards,opponents)
    if not (validation["cards_valid"] and validation["opponents_valid"]):
        output["status"]="estruturas_incoerentes"
        return output
    output.update(status="catalogo_candidato_reconstruido",
                  cards=cards,opponents=opponents,
                  cardsCount=CARD_COUNT,opponentsCount=OPPONENT_COUNT,
                  offsets={k:link[k] for k in fields},
                  fieldEncoding="fm_packed_722_v1",
                  origin="somente_executavel_desta_iso",
                  validated=False,inGameVerified=False,mayActivate=False)
    return output
