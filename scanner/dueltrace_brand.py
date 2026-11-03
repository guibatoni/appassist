"""Ícone vetorial/raster DUELTRACE sem bibliotecas gráficas externas.

Marca mínima: triângulo de rastreamento + olho central, ciano e dourado.
A arte conceitual aprovada é referência; este símbolo reduzido funciona
em 16x16, barra de tarefas e janela do Windows.
"""
from __future__ import annotations

import base64
import math
import struct
import zlib
from functools import lru_cache
from pathlib import Path


def _segment_distance(px,py,ax,ay,bx,by):
    dx=bx-ax;dy=by-ay
    t=max(0.0,min(1.0,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
    return math.hypot(px-ax-t*dx,py-ay-t*dy)


def _fallback_png_icon(size=64):
    if not 16<=size<=512:
        raise ValueError("Ícone precisa ter 16 a 512 pixels")
    pixels=bytearray()
    for y in range(size):
        pixels.append(0)
        for x in range(size):
            px=(x+0.5)/size;py=(y+0.5)/size
            radius=0.16
            qx=abs(px-0.5)-0.5+radius
            qy=abs(py-0.5)-0.5+radius
            outside=math.hypot(max(qx,0),max(qy,0))+min(max(qx,qy),0)-radius
            alpha=255 if outside<=-0.004 else max(0,min(255,int(0.5-outside*size)*255))
            d=min(_segment_distance(px,py,.23,.20,.77,.20),
                  _segment_distance(px,py,.77,.20,.50,.81),
                  _segment_distance(px,py,.50,.81,.23,.20))
            cyan=max(0.0,min(1.0,(0.040-d)*30.0))
            gold=0.0
            # Ícone do olho: arco superior e inferior em torno de uma pupila.
            if .31<px<.69:
                curve=math.sin((px-.31)/.38*math.pi)
                top=abs(py-(.47-.067*curve))
                bottom=abs(py-(.47+.067*curve))
                gold=max(0.0,min(1.0,(.011-min(top,bottom))*115))
            iris=math.hypot(px-.50,py-.47)
            if iris<.035:cyan=1
            glow=max(0.0,(0.085-d))*2.0
            base=[7+int(10*py),19+int(24*py),37+int(31*py)]
            c=(35,212,255);g=(247,192,100)
            for i in range(3):
                base[i]=int(min(255,base[i]+glow*max(0,c[i]-base[i])
                                +cyan*(c[i]-base[i])*.90
                                +gold*(g[i]-base[i])*min(1,1-cyan*.5)))
            pixels.extend((*base,alpha))
    def chunk(tag,data):
        return struct.pack(">I",len(data))+tag+data+struct.pack(">I",zlib.crc32(tag+data)&0xFFFFFFFF)
    data=b"".join(bytes(pixels[i:i+(4*size+1)]) for i in range(0,len(pixels),4*size+1))
    return (b"\x89PNG\r\n\x1a\n"+
            chunk(b"IHDR",struct.pack(">IIBBBBB",size,size,8,6,0,0,0))+
            chunk(b"IDAT",zlib.compress(data,9))+
            chunk(b"IEND",b""))



def _premium_png_icon(size):
    """DT com escudo egípcio abstrato, bordas metálicas e brilho ciano.

    Produção inteiramente original. Não utiliza personagens nem imagens do jogo.
    O ícone permanece legível nas resoluções pequenas do Windows.
    """
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont, ImageFilter

    factor = 3 if size <= 256 else 2
    n = size * factor
    img = Image.new("RGBA",(n,n),(0,0,0,0))
    draw = ImageDraw.Draw(img)
    radius = max(6,n//7)
    # Gradiente escuro metálico.
    for y in range(n):
        t=y/max(n-1,1)
        dark=(4+int(10*t),15+int(21*t),34+int(20*t),255)
        draw.line([(radius//2,y),(n-radius//2,y)],fill=dark,width=1)
    draw.rounded_rectangle((3,3,n-4,n-4),radius=radius,
                           outline=(241,184,83,255),width=max(2,n//85))
    draw.rounded_rectangle((n//46,n//46,n-n//46,n-n//46),
                           radius=max(3,radius-n//90),
                           outline=(35,214,255,255),width=max(1,n//118))
    # Luzes e órbita circular, inconfundíveis mesmo em tamanho reduzido.
    cx=n//2;cy=n//2
    draw.arc((n*.13,n*.18,n*.87,n*.88),205,333,
             fill=(235,172,67,220),width=max(2,n//90))
    draw.arc((n*.13,n*.18,n*.87,n*.88),17,160,
             fill=(34,216,252,230),width=max(2,n//90))
    tri=[(cx,n*.11),(n*.85,n*.76),(n*.15,n*.76)]
    draw.line(tri+[tri[0]],fill=(35,210,252,245),
              width=max(2,n//60),joint="curve")
    draw.line([(cx,n*.16),(n*.78,n*.73),(n*.23,n*.73),(cx,n*.16)],
              fill=(246,190,91,220),width=max(1,n//150),joint="curve")
    # Iniciais DT cromadas, desenho vetorial de fonte instalada no sistema.
    font=None
    for path in (
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            font=ImageFont.truetype(path,int(n*.36))
            break
        except (OSError,ValueError):
            pass
    if font is None:
        font=ImageFont.load_default()
    text="DT"
    bounds=draw.textbbox((0,0),text,font=font,stroke_width=max(1,n//65))
    tw=bounds[2]-bounds[0];th=bounds[3]-bounds[1]
    pos=((n-tw)/2-bounds[0],(n-th)/2-bounds[1]-n*.01)
    ink=Image.new("RGBA",img.size,(0,0,0,0))
    idraw=ImageDraw.Draw(ink)
    idraw.text(pos,text,font=font,fill=(232,242,254,255),
               stroke_width=max(1,n//65),stroke_fill=(242,180,76,255))
    halo=ink.filter(ImageFilter.GaussianBlur(max(1,n//50)))
    img=Image.alpha_composite(img,halo)
    img=Image.alpha_composite(img,ink)
    d=ImageDraw.Draw(img)
    # Faixa de acabamento na base.
    d.line((n*.27,n*.83,n*.73,n*.83),
           fill=(232,182,80,245),width=max(1,n//85))
    img=img.resize((size,size),Image.Resampling.LANCZOS)
    out=BytesIO()
    img.save(out,format="PNG",optimize=True)
    return out.getvalue()


@lru_cache(maxsize=8)
def png_icon(size=64):
    if not 16 <= size <= 512:
        raise ValueError("Ícone precisa ter 16 a 512 pixels")
    try:
        return _premium_png_icon(size)
    except ImportError:
        # Sem Pillow o aplicativo ainda funciona com a marca vetorial básica.
        return _fallback_png_icon(size)


def ico_icon(sizes=(16,32,48,64,256)):
    images=[png_icon(n) for n in sizes]
    header=struct.pack("<HHH",0,1,len(images))
    start=6+16*len(images)
    entries=[]
    for size,blob in zip(sizes,images):
        entries.append(struct.pack("<BBBBHHII",
                                   size if size<256 else 0,
                                   size if size<256 else 0,
                                   0,0,1,32,len(blob),start))
        start+=len(blob)
    return header+b"".join(entries)+b"".join(images)


def ensure_icons(directory: Path):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    png=directory/"dueltrace.png"
    ico=directory/"dueltrace.ico"
    if not png.is_file():png.write_bytes(png_icon(256))
    if not ico.is_file():ico.write_bytes(ico_icon())
    return png,ico


def apply_window_icon(window):
    import tkinter as tk
    icon=tk.PhotoImage(data=base64.b64encode(png_icon(64)))
    window.iconphoto(True,icon)
    window._dueltrace_photo_icon=icon


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default=".")
    args=parser.parse_args()
    print(ensure_icons(Path(args.output)))
