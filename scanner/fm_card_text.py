"""Textos de cartas extraídos diretamente da tabela de ponteiros do SLUS.

SLUS_014.11 retail/mod comum:
  banco de texto em 0x1B0800,
  ponteiros u16 de descrição em 0x1B0A02 + (id-1)*2,
  glifos em 0x1C9800.
As offsets são hipóteses do layout SLUS-01411, confirmadas em fontes
independentes; módulos incompatíveis não recebem descrições inventadas.
Este parser lê texto, NÃO garante execução do efeito durante duelo.
"""
from __future__ import annotations
import hashlib
import re
import struct
import unicodedata

CARD_COUNT=722
DESCRIPTION_POINTERS=0x1B0A02
DESCRIPTION_BANK=0x1B0800
DESCRIPTION_BANK_END=0x1C0800
GLYPHS_OFFSET=0x1C9800
GLYPHS_COUNT=93
MAX_RAW_BYTES=384
MAX_TEXT_CHARS=550
VALID_THRESHOLD=400  # Remaster X15 real tem 497 textos e 225 entradas vazias
EFFECT_MARKER=re.compile(r"(?:<|\\[|《|〈|【)\\s*(?:effect|efeito)\\s*(?:>|\\]|》|〉|】)",re.I)


def _glyphs(sl:bytes)->list[str]:
    if len(sl)<GLYPHS_OFFSET+GLYPHS_COUNT*4:
        raise ValueError("Fonte de glifos do SLUS incompleta")
    converted=[]
    for index in range(GLYPHS_COUNT):
        value=struct.unpack_from("<H",sl,GLYPHS_OFFSET+4*index)[0]
        if not value:
            converted.append("")
            continue
        pair=value.to_bytes(2,"big")
        try:
            # Descarta preenchimento NUL, não o conteúdo real.
            converted.append(pair.lstrip(b"\x00").decode("shift_jis"))
        except UnicodeError:
            converted.append("\uFFFD")
    return converted


def _decode(sl:bytes, offset:int, glyphs:list[str])->str|None:
    if offset<DESCRIPTION_BANK or offset>=min(DESCRIPTION_BANK_END,len(sl)):
        return None
    end=min(offset+MAX_RAW_BYTES,len(sl),DESCRIPTION_BANK_END)
    rendered=[]
    terminated=False
    i=offset
    while i<end:
        byte=sl[i]
        i+=1
        if byte==255:
            terminated=True
            break
        if byte==254:
            rendered.append("\n")
            continue
        if byte==0:
            rendered.append(" ")
            continue
        if byte==0xF8 and i+1<end and sl[i] in (0x0A,0x0B):
            key=sl[i];arg=sl[i+1];i+=2
            # O marcador original é preservado para auditoria da descrição.
            if key==0x0B:
                rendered.append("[Ícone %02X]"%arg)
            continue
        if byte>=len(glyphs) or not glyphs[byte]:
            return None
        rendered.append(glyphs[byte])
    if not terminated:
        return None
    content=unicodedata.normalize("NFKC","".join(rendered))
    content=re.sub(r"[ \t]{2,}"," ",content).strip()
    if not 4<=len(content)<=MAX_TEXT_CHARS:
        return None
    if "\x00" in content or "\uFFFD" in content:
        return None
    if sum(ch.isalpha() or ch.isdigit() for ch in content)<3:
        return None
    return content


def extract_descriptions(sl:bytes,*,exe_name="SLUS_014.11")->tuple[dict[int,dict],dict]:
    if len(sl)<max(GLYPHS_OFFSET+GLYPHS_COUNT*4,
                  DESCRIPTION_POINTERS+CARD_COUNT*2):
        return {},{"status":"executavel_curto","count":0,"valid":False}
    try:
        glyphs=_glyphs(sl)
    except (ValueError,struct.error) as exc:
        return {},{"status":"glifos_invalidos","count":0,"valid":False,"reason":str(exc)}
    found={}
    unique=set()
    for cid in range(1,CARD_COUNT+1):
        pointer=struct.unpack_from("<H",sl,DESCRIPTION_POINTERS+(cid-1)*2)[0]
        addr=DESCRIPTION_BANK+pointer
        txt=_decode(sl,addr,glyphs)
        if txt is None:
            continue
        unique.add(pointer)
        found[cid]={
            "text":txt,
            "source":f"{exe_name}:descricao:id={cid}:slus_offset=0x{addr:X}",
            "exe_offset":addr,
        }
    # Não trate bytes aleatórios em código MIPS como texto de carta.
    valid=len(found)>=VALID_THRESHOLD and len(unique)>=VALID_THRESHOLD//2
    if not valid:
        return {},{"status":"tabela_incompativel","count":len(found),
                   "unique_pointers":len(unique),"valid":False}
    return found,{"status":"texto_estrutural_extraido","count":len(found),
                  "unique_pointers":len(unique),"valid":True,
                  "layout":"SLUS-01411-0x1B0A02","exe_sha256":hashlib.sha256(sl).hexdigest(),
                  "effects_executed_in_game_verified":False}


def attach_descriptions(cards:list[dict],extracted:dict[int,dict])->tuple[list[dict],dict]:
    """Anexa apenas descrições associadas por ponteiros e ID; não inventa efeitos."""
    out=[]
    descriptions=effects=0
    for card in cards:
        row=dict(card)
        data=extracted.get(row.get("id"))
        if data:
            row["description_text"]=data["text"]
            row["description_source"]=data["source"]
            descriptions+=1
            category=row.get("category")
            # Textos declarados de Magia/Armadilha/Ritual/Equip,
            # ou um monstro com marcador explícito de efeito.
            if (not row.get("effect_text") and
                (category in ("Mágicas","Armadilhas","Rituais","Equipamentos")
                 or EFFECT_MARKER.search(data["text"]))):
                row["effect_text"]=data["text"]
                row["effect_source"]=data["source"]
                row["effect_status"]="texto_do_jogo_sem_confirmacao_de_mecanica"
                effects+=1
        out.append(row)
    return out,{"descriptions_attached":descriptions,
                "effect_descriptions_attached":effects,
                "effects_executed_in_game_verified":False}
