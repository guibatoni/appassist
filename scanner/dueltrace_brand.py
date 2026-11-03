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
from pathlib import Path


def _segment_distance(px,py,ax,ay,bx,by):
    dx=bx-ax;dy=by-ay
    t=max(0.0,min(1.0,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
    return math.hypot(px-ax-t*dx,py-ay-t*dy)


def png_icon(size=64):
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
