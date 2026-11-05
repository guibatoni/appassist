"""Descoberta limitada de tabelas de ponteiros realocadas no executável PS1.

Esta etapa procura uma tabela *compartilhada* de nomes das 722 cartas e dos
39 oponentes com ponteiros de 16 bits e glifos no layout já conhecido.
Uma correspondência é evidência estrutural, não prova da identidade do ID,
portanto não autoriza ativar cartas, fusões ou drops automaticamente.

Outros formatos de strings, tabelas MIPS e glifos deslocados exigem adaptador
diferente; nunca reinterpretar bytes arbitrários como nomes verificados.
"""
from __future__ import annotations

import struct
import unicodedata

from dueltrace_name_boundaries import read_glyphs, read_name_table

CARD_COUNT=722
OPPONENT_COUNT=39
OPPONENT_FIRST_INDEX=0x329
MAX_SHIFT_BYTES=32768
MAX_EXE_BYTES=8*1024*1024
MAX_CANDIDATES=4
MAX_READ_CHARS=64

# Primeiro e último ID evitam que um deslocamento de 1 posição atribua
# nomes de cartas ou inimigos aos IDs vizinhos.
_CARD_SAMPLES=(1,2,3,10,25,50,100,200,350,500,650,722)
_OPP_SAMPLES=(OPPONENT_FIRST_INDEX,OPPONENT_FIRST_INDEX+1,0x330,0x340,0x34F)
_SAMPLES=_CARD_SAMPLES+_OPP_SAMPLES
_MANDATORY=(1,722,OPPONENT_FIRST_INDEX,0x34F)


def _plausible_name(value: str) -> bool:
    return (2<=len(value)<=52 and
            sum(c.isalnum() for c in value)>=2 and
            any(c.isalpha() for c in value) and
            all(c.isprintable() and c!='\ufffd' for c in value))


def _read_sample(sl:bytes, *, pointer_address:int, text_base:int,
                 glyphs:tuple[str,...], index:int) -> str | None:
    addr=pointer_address+index*2
    if addr<0 or addr+2>len(sl):
        return None
    offset=struct.unpack_from('<H',sl,addr)[0]
    pos=text_base+offset
    if not 0<=pos<len(sl):
        return None
    if sl[pos:pos+2]==b"\xf8\x0a":
        pos+=3
    raw=sl[pos:pos+MAX_READ_CHARS]
    chars=[]
    for code in raw:
        if code==255:
            value=unicodedata.normalize("NFKC","".join(chars)).strip()
            return value if _plausible_name(value) else None
        if code==0:
            chars.append(" ")
        elif code<len(glyphs) and glyphs[code]:
            chars.append(glyphs[code])
        else:
            return None
    return None


def discover_relocated_name_table(sl:bytes, *, pointer_base:int,
                                  text_base:int,glyph_base:int,
                                  max_shift:int=MAX_SHIFT_BYTES) -> dict:
    """Busca em uma vizinhança limitada e devolve somente evidências.

    Não usa a extensão do executável, SHA de outra ISO, nomes canônicos de
    cartas nem dados externos. Um FF encontrado depois de outro nome não
    valida o registro: a verificação final usa limites físicos por ponteiro.
    """
    result={
        "schema":1,"state":"nao_encontrado","validated":False,
        "candidates":[],"scannedPositions":0,
        "scanRadiusBytes":0,"glyphLayout":"known_offsets_only",
        "note":"Ponteiros realocados são candidatos; IDs e nomes não foram confirmados no jogo.",
    }
    if (not isinstance(sl,bytes) or len(sl)>MAX_EXE_BYTES or
            min(pointer_base,text_base,glyph_base)<0 or
            glyph_base+93*4>len(sl)):
        result["state"]="executavel_ou_glifos_incompativeis"
        return result
    max_shift=max(0,min(int(max_shift),MAX_SHIFT_BYTES))
    result["scanRadiusBytes"]=max_shift
    try:
        glyphs=read_glyphs(sl,glyph_base)
    except (ValueError,UnicodeError,struct.error):
        result["state"]="glifos_invalidos"
        return result
    if sum(bool(g and len(g)==1 and g.isprintable()) for g in glyphs)<24:
        result["state"]="glifos_insuficientes"
        return result

    card_indices=tuple(range(1,CARD_COUNT+1))
    opponent_indices=tuple(range(OPPONENT_FIRST_INDEX,
                                 OPPONENT_FIRST_INDEX+OPPONENT_COUNT))
    indices=card_indices+opponent_indices
    count=0
    strong=[]
    for shift in range(-max_shift,max_shift+1,2):
        if shift==0:
            continue  # layout original já passou pelo decoder tradicional
        base=pointer_base+shift
        if base<0 or base+(max(indices)+1)*2>len(sl):
            continue
        count+=1
        anchors={i:_read_sample(sl,pointer_address=base,text_base=text_base,
                                glyphs=glyphs,index=i) for i in _MANDATORY}
        if not all(anchors.values()):
            continue
        good={}
        for index in _SAMPLES:
            if index in anchors:
                good[index]=anchors[index]
            else:
                good[index]=_read_sample(sl,pointer_address=base,text_base=text_base,
                                         glyphs=glyphs,index=index)
        valid=[name for name in good.values() if name]
        card_ok=sum(bool(good.get(i)) for i in _CARD_SAMPLES)
        opp_ok=sum(bool(good.get(i)) for i in _OPP_SAMPLES)
        if (len(valid)<16 or len(set(valid))<14 or
                card_ok<11 or opp_ok<4):
            continue
        # Só nesta fase cara interpretar os 761 registros e seus limites.
        try:
            records=read_name_table(sl,pointer_base=base,
                text_base=text_base,glyph_base=glyph_base,indices=indices,
                max_bytes=100)
        except (ValueError,UnicodeError,struct.error):
            continue
        cards=[records[i] for i in card_indices]
        opponents=[records[i] for i in opponent_indices]
        def valid_record(row):
            return (row["recordStatus"]=="ff_encontrado"
                    and _plausible_name(row["readablePrefix"]))
        n_cards=sum(valid_record(row) for row in cards)
        n_opponents=sum(valid_record(row) for row in opponents)
        if n_cards<720 or n_opponents<38:
            continue
        card_names=[r["readablePrefix"] for r in cards if valid_record(r)]
        opponent_names=[r["readablePrefix"] for r in opponents if valid_record(r)]
        # Nomes duplicados em massa, como regiões zeradas, não representam
        # um catálogo. Esta prova ainda não identifica cada ID no jogo.
        if len(set(card_names))<700 or len(set(opponent_names))<37:
            continue
        strong.append({
            "pointerBase":base,
            "relativeShift":shift,
            "cardNamesTerminated":n_cards,
            "opponentNamesTerminated":n_opponents,
            "distinctCardNames":len(set(card_names)),
            "distinctOpponentNames":len(set(opponent_names)),
            "cardSamples":[{"id":i,"text":records[i]["readablePrefix"][:52]}
                           for i in (1,100,500,722)],
            "opponentSamples":[{"id":i,"text":records[0x328+i]["readablePrefix"][:52]}
                               for i in (1,20,39)],
            "validated":False,
        })
        # Vários alinhamentos fortes não são automaticamente resolvidos.
        if len(strong)>=MAX_CANDIDATES:
            break
    result["scannedPositions"]=count
    result["candidates"]=strong
    result["state"]=("hipoteses_ambiguas" if len(strong)>1 else
                     "tabela_candidata_localizada" if strong else "nao_encontrado")
    return result
