"""Busca apenas diagnóstica de tabelas de 39 nomes de oponentes relocadas.

O scanner original usa o índice 0x328 como base. Mods podem mover esses
ponteiros, deixando as 722 cartas legíveis mas os oponentes inválidos.
Pesquisa uma vizinhança limitada da tabela de ponteiros, reaproveitando
somente a codificação que o parser original reconheceu. NÃO promove perfis.
"""
from __future__ import annotations

import struct
import unicodedata

MAX_SCAN_INDICES=1152
OPPONENT_COUNT=39


def find_opponent_pointer_candidates(
        sl: bytes, *, pointer_base: int, text_base: int, glyph_base: int,
        original_index: int=0x328, max_indices: int=MAX_SCAN_INDICES) -> dict:
    """Identifica faixas plausíveis; somente pistas, sem confirmação.

    Leitura inteira dentro do executável já extraído em memória. Nenhum
    arquivo novo, execução MIPS, chamada remota ou escrita no perfil.
    """
    max_indices=max(0,min(int(max_indices),MAX_SCAN_INDICES))
    if glyph_base+93*4>len(sl) or pointer_base+(max_indices+OPPONENT_COUNT)*2>len(sl):
        return {"state":"executavel_insuficiente","candidates":[],"validated":False}
    glyphs=[]
    try:
        for i in range(93):
            value=struct.unpack_from("<H",sl,glyph_base+i*4)[0]
            glyphs.append(value.to_bytes(2,"big").decode("shift_jis")
                          if value else "")
    except (UnicodeError,struct.error):
        return {"state":"glifos_nao_compativeis","candidates":[],"validated":False}
    decoded={}
    for index in range(723,max_indices+OPPONENT_COUNT):
        ptr=struct.unpack_from("<H",sl,pointer_base+index*2)[0]
        pos=text_base+ptr
        if not 0<=pos<len(sl):
            decoded[index]=None
            continue
        raw=sl[pos+3:pos+88] if sl[pos:pos+2]==b"\xf8\x0a" else sl[pos:pos+88]
        result=[]
        invalid=False
        terminated=False
        for ch in raw:
            if ch==255:
                terminated=True
                break
            if ch==0:
                result.append(" ")
            elif ch<len(glyphs) and glyphs[ch]:
                result.append(glyphs[ch])
            else:
                invalid=True
                break
        name=unicodedata.normalize("NFKC","".join(result)).strip()
        valid=(not invalid and terminated and 3<=len(name)<=52
               and sum(c.isalnum() for c in name)>=3
               and any(c.isalpha() for c in name))
        decoded[index]=name if valid else None

    possibilities=[]
    for start in range(723,max_indices):
        names=[decoded.get(i) for i in range(start,start+OPPONENT_COUNT)]
        good=[n for n in names if n]
        unique=len(set(good))
        if len(good)<34 or unique<32:
            continue
        score=len(good)*2+unique
        possibilities.append({
            "startIndex":start,
            "plausible":len(good),
            "distinct":unique,
            "score":score,
            "samples":[name[:52] for name in good[:5]],
            "nearKnown":abs(start-original_index)<=24,
            "validated":False,
        })
    possibilities.sort(key=lambda x:(-x["score"],
                                      abs(x["startIndex"]-original_index)))
    # Truncar janelas sobrepostas que leem quase os mesmos 39 nomes.
    distinct=[]
    for row in possibilities:
        if any(abs(row["startIndex"]-v["startIndex"])<OPPONENT_COUNT
               for v in distinct):
            continue
        distinct.append(row)
        if len(distinct)>=5:
            break
    return {
        "state":"hipoteses_de_ponteiros" if distinct else
                "nenhuma_tabela_plausivel_na_vizinhanca",
        "scannedStart":723,"scannedEnd":max_indices,
        "candidates":distinct,"validated":False,
        "note":"Somente possíveis grupos de nomes; 39 oponentes não validados.",
    }
