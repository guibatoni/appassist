"""Decodificador de artes e molduras do próprio WA_MRG.MRG.

Validado contra Remaster X15 e FM13 reais: 722 registros de 7 setores
(setor 722); sprite da mão UV(0,128), 52x60 em **8bpp**, paletas de
256 cores nas linhas 1-6 da primeira cena de duelo. O índice da fase
está organizado em colunas de 64 words x 256 linhas (16 setores por
coluna). Não inclui bytes nem código de terceiros.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path

CARD_COUNT=722
SECTOR=2048
RECORD_SECTORS=7
FIRST_CARD_SECTOR=722
LARGE_PIXELS=102*96
THUMB_PIXELS=40*32
DUEL_IMAGE_START=0xB63000
DUEL_CLUT_START=DUEL_IMAGE_START+64*SECTOR
DUEL_COL_SIZE=16*SECTOR
FRAME_ATLAS_COLUMN=2
FRAME_V,FRAME_W,FRAME_H=128,52,60
FRAME_ROW_STRIDE=64*2
FRAME_NAMES=("monstro","magica","armadilha","ritual","roxo","laranja")
ASSET_REVISION=1


def bgr555(value:int,*,transparent_zero=False):
    if transparent_zero and value==0:
        return (0,0,0,0)
    return ((value&31)*255//31,((value>>5)&31)*255//31,
            ((value>>10)&31)*255//31,255)


def frame_index(type_id)->int|None:
    """Frame de varejo por código de tipo, nunca inferido pelo nome."""
    if type(type_id) is not int:
        return None
    if 0<=type_id<20:
        return 0
    if type_id in (20,23):
        return 1
    if type_id==21:
        return 2
    if type_id==22:
        return 3
    return None


def _paletted(raw:bytes,size:tuple[int,int],colors:list[int]):
    from PIL import Image
    if len(raw)!=size[0]*size[1]:
        raise ValueError("Tamanho incompatível de pixels")
    palette=[v for color in colors for v in bgr555(color)[:3]]
    if len(palette)>768:
        raise ValueError("Paleta com mais de 256 entradas")
    picture=Image.frombytes("P",size,raw)
    picture.putpalette(palette+[0]*(768-len(palette)))
    return picture


def _palette(wa:bytes,at:int,entries:int)->list[int]:
    if at<0 or at+entries*2>len(wa):
        raise ValueError("Paleta fora do WA_MRG")
    return list(struct.unpack_from("<"+str(entries)+"H",wa,at))


def decode_hand_frame(wa:bytes,color_index:int):
    """Frame 52x60 **8bpp**, usando CLUT original de 256 cores por quadro."""
    if type(color_index) is not int or not 0<=color_index<len(FRAME_NAMES):
        raise ValueError("Cor da moldura inválida")
    at=DUEL_IMAGE_START+FRAME_ATLAS_COLUMN*DUEL_COL_SIZE
    start=at+FRAME_V*FRAME_ROW_STRIDE
    length=FRAME_W
    if start+(FRAME_H-1)*FRAME_ROW_STRIDE+length>len(wa):
        raise ValueError("Bloco de molduras do duelo incompleto")
    colors=_palette(wa,DUEL_CLUT_START+(color_index+1)*256*2,256)
    # WA armazena 8bpp como 52 pixels consecutivos por linha da
    # coluna de 128 bytes. O primeiro decodificador 4bpp produzia
    # listras; validação real de ambas as ISOs confirmou 8bpp.
    raw=b"".join(wa[start+y*FRAME_ROW_STRIDE:
                    start+y*FRAME_ROW_STRIDE+length] for y in range(FRAME_H))
    frame=_paletted(raw,(FRAME_W,FRAME_H),colors)
    # Na GPU do PS1 a entrada 0 da CLUT costuma ser transparente.
    # Só aplicar alpha quando a paleta real confirmar cor 0.
    if colors[0]==0:
        frame.info["transparency"]=0
    return frame.convert("RGBA")


def _large(wa:bytes,card_id:int):
    base=(FIRST_CARD_SECTOR+(card_id-1)*RECORD_SECTORS)*SECTOR
    if base+0x2840>len(wa):
        raise ValueError("Registro grande fora do WA_MRG")
    return _paletted(
        wa[base:base+LARGE_PIXELS],(102,96),
        _palette(wa,base+0x2640,256)),base


def _small(wa:bytes,card_id:int):
    base=(card_id-1)*SECTOR
    repeated=(FIRST_CARD_SECTOR+(card_id-1)*RECORD_SECTORS)*SECTOR+0x2AE0
    if base+0x580>len(wa) or repeated+0x580>len(wa):
        raise ValueError("Miniatura 40x32 incompleta")
    primary=wa[base:base+0x580]
    secondary=wa[repeated:repeated+0x580]
    if any(x>=64 for x in primary[:THUMB_PIXELS]):
        raise ValueError("Miniatura usa índices fora da paleta de 64 cores")
    colors=list(struct.unpack_from("<64H",primary,0x500))
    return _paletted(primary[:THUMB_PIXELS],(40,32),colors),primary==secondary,base


def _has_detail(im)->bool:
    colors=im.convert("RGB").getcolors(maxcolors=32768)
    return colors is None or len(colors)>=7


def extract_asset_pack(wa:bytes,cards:list[dict],out:Path,*,
                       rom_sha256:str,wa_name="DATA/WA_MRG.MRG")->dict:
    """Extrai 722 PNGs grandes, 722 miniaturas e composições por tipo localmente."""
    try:
        from PIL import Image
    except ImportError:
        return {"revision":ASSET_REVISION,"art_count":0,"thumbnail_count":0,
                "composed_count":0,"frame_count":0,"status":"pillow_ausente",
                "warnings":["Pillow indisponível"]}
    ids=[c.get("id") for c in cards]
    if (len(cards)!=CARD_COUNT or ids!=list(range(1,CARD_COUNT+1)) or
            type(rom_sha256) is not str or not re.fullmatch(r"[0-9a-fA-F]{64}",rom_sha256)):
        raise ValueError("Catálogo deve ter 722 IDs e SHA válido")
    out=Path(out)
    folders={kind:out/kind for kind in
             ("artes_722","miniaturas_722","molduras_wa","cartas_com_moldura")}
    for folder in folders.values():
        folder.mkdir(parents=True,exist_ok=True)
    warnings=[]
    frames={}
    for index,name in enumerate(FRAME_NAMES):
        try:
            im=decode_hand_frame(wa,index)
            if not _has_detail(im):
                warnings.append(f"Moldura {name}: dados gráficos pouco variados")
                continue
            frames[index]=im
            im.save(folders["molduras_wa"]/f"{index}-{name}.png",optimize=True)
        except (OSError,ValueError,struct.error) as exc:
            warnings.append(f"Moldura {index}: {str(exc)[:120]}")
    good_art=good_thumb=composed=duplicate=0
    metadata=[]
    for card in cards:
        cid=card["id"]
        try:
            art, art_offset=_large(wa,cid)
            thumb, match,thumb_offset=_small(wa,cid)
            if not (_has_detail(art) and _has_detail(thumb)):
                warnings.append(f"ID {cid}: pixels sem variedade suficiente")
                continue
            art.save(folders["artes_722"]/f"{cid:03d}.png",optimize=True)
            good_art+=1
            thumb.save(folders["miniaturas_722"]/f"{cid:03d}.png",optimize=True)
            good_thumb+=1
            if match:duplicate+=1
            fi=frame_index(card.get("type_id",card.get("tipo")))
            if fi in frames:
                picture=frames[fi].copy()
                # Visual da mão do PS1: miniatura sobre o frame em (6,6).
                picture.paste(thumb.convert("RGBA"),(6,6))
                picture.save(folders["cartas_com_moldura"]/f"{cid:03d}.png",optimize=True)
                composed+=1
            metadata.append({
                "id":cid,"source":wa_name,"art_offset":art_offset,
                "art_size":[102,96],"thumbnail_offset":thumb_offset,
                "thumbnail_size":[40,32],"thumbnail_matches_record":match,
                "frame_palette":fi,"composed":fi in frames,
            })
        except (OSError,ValueError,struct.error) as exc:
            warnings.append(f"ID {cid}: {str(exc)[:120]}")
    # Miniaturas repetidas divergentes são uma característica auditável do
    # mod, não tornam inválidas as imagens extraídas com sucesso.
    unmatched=good_thumb-duplicate
    if unmatched:
        warnings.append(f"{unmatched} miniaturas diferem da cópia no registro; ambas as origens foram auditadas")
    report={
        "revision":ASSET_REVISION,"rom_sha256":rom_sha256,
        "source":wa_name,"source_bytes":len(wa),
        "source_sha256":hashlib.sha256(wa).hexdigest(),
        "art_count":good_art,"thumbnail_count":good_thumb,
        "frame_count":len(frames),"composed_count":composed,
        "thumbnail_duplicate_matches":duplicate,
        "thumbnail_duplicate_mismatches":unmatched,
        "status":"completo" if good_art==good_thumb==composed==CARD_COUNT
                 and len(frames)==6 else "parcial",
        "warnings":warnings[:80],"records":metadata,
    }
    temp=out/"recursos_wa.json.tmp"
    temp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    temp.replace(out/"recursos_wa.json")
    return {k:v for k,v in report.items() if k!="records"}
