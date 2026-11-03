"""Extratores declarativos de metadados dos arquivos PS1 do usuário.

NÃO é um leitor universal de formatos MRG. Offset e tamanho exigem
validação contra a versão real da ISO; dados não reconhecidos não são
inventados. Nenhuma modificação é feita nos arquivos de origem.
"""
from __future__ import annotations

import json
import re
import struct
import unicodedata
from pathlib import Path

CARD_COUNT = 722
DESC_POINTERS = 0x1B0A00
DESC_DATA = 0x1B0800
DESC_BANK_END = 0x1C0000
FONT_GLYPHS = 0x1C9800
MAX_DESCRIPTION_BYTES = 280

# Loader do campo Normal, pacote WA setor 0x16C6. O bloco no offset
# +0x20000 armazena 16 linhas de CLUT, cada uma com 256 cores 16-bit.
WA_TERRAIN_NORMAL = 0x16C6 * 2048
WA_FRAME_CLUT_BASE = WA_TERRAIN_NORMAL + 0x20000
FRAME_VARIANTS = {
    "normal": 248, "magia": 249, "armadilha": 250,
    "ritual": 251, "fusao": 252, "efeito": 253,
}
PALETTE_ROWS = 256
PALETTE_BYTES = PALETTE_ROWS * 2


def _chars(exe: bytes):
    if len(exe) < FONT_GLYPHS + 93*4:
        raise ValueError("SLUS sem tabela conhecida de glifos.")
    return [struct.unpack_from("<H",exe,FONT_GLYPHS+i*4)[0]
            for i in range(93)]


def _decode_psx_text(buf: bytes, glyphs: list[int]) -> str | None:
    """Fonte FM: 0 espaço, 0xFE nova linha, 0xFF fim, F8 0A/0B códigos.

    Não converte códigos binários desconhecidos em caracteres imprimíveis.
    """
    result=[]
    at=0
    ended=False
    while at<len(buf):
        v=buf[at]
        at+=1
        if v==0xFF:
            ended=True
            break
        if v==0xFE:
            result.append("\n")
            continue
        if v==0xF8:
            if at+2>len(buf) or buf[at] not in (0x0A,0x0B):
                return None
            cmd=buf[at]
            code=buf[at+1]
            at+=2
            if cmd==0x0B:
                result.append("[Ícone %02X]"%code)
            continue
        if v==0:
            result.append(" ")
            continue
        if v>=len(glyphs) or not glyphs[v]:
            return None
        try:
            result.append(glyphs[v].to_bytes(2,"big").decode("shift_jis"))
        except (UnicodeDecodeError,OverflowError):
            return None
    if not ended:
        return None
    text=unicodedata.normalize("NFKC","".join(result))
    text=re.sub(r"[ \t]+"," ",text).strip()
    if not text or len(text)>400 or any(ord(c)<32 and c!="\n" for c in text):
        return None
    if sum(c.isalpha() for c in text)<3:
        return None
    return text


def extract_descriptions(exe: bytes) -> tuple[dict[int,dict],dict]:
    """Extrai textos indexados por ID exclusivamente de SLUS conhecido.

    Os offsets são validados por carta e também em lote. Uma ISO com
    tabela diferente é sinalizada, não recebe descrições incorretas.
    """
    result={}
    note={"source":"SLUS_014.11","pointer_table":hex(DESC_POINTERS),
          "text_base":hex(DESC_DATA),"recognized":0,"status":"não_validado"}
    if len(exe)<max(DESC_BANK_END,FONT_GLYPHS+93*4):
        note["status"]="slus_menor_que_layout"
        return result,note
    try:
        glyphs=_chars(exe)
    except ValueError:
        note["status"]="sem_fonte"
        return result,note
    pointers=[]
    for cid in range(1,CARD_COUNT+1):
        pointer=struct.unpack_from("<H",exe,DESC_POINTERS+cid*2)[0]
        pos=DESC_DATA+pointer
        if not DESC_DATA<=pos<DESC_BANK_END:
            note["status"]="ponteiro_fora_do_banco"
            return {},note
        pointers.append(pos)
    # Layout alterado pode ter outro sentido para o banco.
    if len(set(pointers))<600:
        note["status"]="ponteiros_repetidos_incompativeis"
        return {},note
    for cid,pos in enumerate(pointers,1):
        raw=exe[pos:min(pos+MAX_DESCRIPTION_BYTES,DESC_BANK_END)]
        text=_decode_psx_text(raw,glyphs)
        if text:
            result[cid]={
                "description":text,
                "description_source":"SLUS_014.11:tabela_descricoes",
                "description_offset":pos,
            }
    note["recognized"]=len(result)
    # Ao contrário de um manifesto com textos por ID, esse layout deve
    # renderizar quase todas as 722 cartas para ser considerado íntegro.
    if len(result)<600:
        note["status"]="codificacao_incompativel"
        return {},note
    note["status"]="texto_extraido_layout_fm_com_verificacao_estrutural"
    note["confidence"]="textos extraídos; sem validação manual de efeito no jogo"
    return result,note


def _rgb555(word: int) -> tuple[int,int,int]:
    return ((word&31)*255//31,((word>>5)&31)*255//31,
            ((word>>10)&31)*255//31)


def inspect_frame_palettes(wa: bytes) -> tuple[dict,dict]:
    """Lê CLUT das molduras: **cores** originais, NÃO geometria da moldura.

    A textura da moldura está no pacote de tela em posições e profundidades
    diferentes. Não gerar uma 'moldura original' falsa apenas de CLUT.
    """
    end=WA_FRAME_CLUT_BASE+(253-240+1)*PALETTE_BYTES
    metadata={"source":"DATA/WA_MRG.MRG",
              "palette_block_offset":WA_FRAME_CLUT_BASE,
              "variants":{},"status":"não_identificado"}
    if len(wa)<end:
        metadata["status"]="WA_incompleto_para_paletas"
        return {},metadata
    variants={}
    for label,vram_row in FRAME_VARIANTS.items():
        offset=WA_FRAME_CLUT_BASE+(vram_row-240)*PALETTE_BYTES
        colors=[_rgb555(v) for v in struct.unpack_from("<256H",wa,offset)]
        # Paleta real deve apresentar diversidade e cores úteis.
        usable=[c for c in colors[1:] if max(c)>16]
        if len(set(usable))<12:
            metadata["status"]="paletas_uniformes_ou_modificadas"
            return {},metadata
        # Valor amostrado da paleta da ISO; não é frame bitmap completo.
        ordered=sorted(set(usable),key=lambda c:(sum(c),max(c)))
        accent=ordered[min(len(ordered)-1,int(len(ordered)*0.75))]
        variants[label]={"vram_row":vram_row,"wa_offset":offset,
                          "accent":"#%02x%02x%02x"%accent,
                          "rgb555_palette_entries":len(colors),
                          "source":"WA_MRG.MRG:CLUT_campo_normal"}
    metadata["variants"]=variants
    metadata["status"]="paletas_lidas_layout_fm"
    metadata["warning"]="CLUT extraída: geometria completa da moldura ainda não decodificada."
    return variants,metadata


def save_metadata(path: Path,data:dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
