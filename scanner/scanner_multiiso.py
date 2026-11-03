#!/usr/bin/env python3
"""Leitor MULTI-ISO apenas para arquivos locais fornecidos/obtidos legitimamente.

Não baixa nem distribui imagens de jogos. Para formatos desconhecidos, não inventa dados.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, struct, sys, unicodedata
from pathlib import Path

OPP_COUNT=39
CARD_COUNT=722
SLUS_PTR_BASE=0x1C6000
SLUS_TEXT_BASE=0x1C0800
SLUS_GLYPHS=0x1C9800
SLUS_ATTRIBUTES=0x1C4A44
WA_OPP_BASE=0xE9B000
WA_OPP_STEP=0x1800
WA_ARRAY_BYTES=722*2
WA_RANK_STRIDE=0x5B4  # espaço por tabela inclui 16 bytes de preenchimento
WA_CARD_SECTOR_START=722
WA_CARD_SECTORS=7
RANKS=('Z-POW','S-POW','S-TEC')
X15_SHA='aff9410791ac107de9bd48a00c495d88f582fec28994f30a0c9f4e6241b74776'
ART_PARSER_REVISION=3  # arte grande + miniatura 40x32 + moldura autêntica + texto de SLUS


def sha256(path:Path, progress=None):
    """SHA-256 em streaming, uma vez por ISO; progresso a cada ~32 MB."""
    h=hashlib.sha256()
    total=path.stat().st_size
    count=0
    next_report=32*1024*1024
    with path.open('rb') as f:
        while True:
            block=f.read(8*1024*1024)
            if not block:break
            h.update(block)
            count+=len(block)
            if progress and (count>=next_report or count>=total):
                progress("Identificando ISO (SHA-256)",count,total)
                next_report=count+32*1024*1024
    return h.hexdigest()

class Disc:
    def __init__(self,p:Path):
        self.p=p; self.f=p.open('rb'); self.size=p.stat().st_size
        if self.size%2352==0:
            self.sector=2352
            self.offset=24 if self._magic(16,24)==b'CD001' else 16
            if self._magic(16,self.offset)!=b'CD001':raise ValueError('CD-ROM de 2352 B sem ISO9660 detectado')
        elif self.size%2048==0:
            self.sector=2048;self.offset=0
            if self._magic(16,1)!=b'CD001':raise ValueError('Imagem de 2048 B sem ISO9660 detectado')
        else:raise ValueError('Tamanho não corresponde a CD-ROM raw 2352 B ou ISO 2048 B')
        self.files=self.list_files()
    def _magic(self,lba,off):
        self.f.seek(lba*self.sector+off+1)
        return self.f.read(5)
    def read(self,lba:int,length:int):
        """Lê setores em lote; evita centenas de milhares de seek/read de 2 KiB."""
        if lba<0 or length<0 or length>self.size:
            raise ValueError('Intervalo de leitura inválido')
        sectors=(length+2047)//2048
        if sectors and (lba+sectors)*self.sector>self.size:
            raise ValueError('Leitura além do fim do disco')
        if not length:return b''
        self.f.seek(lba*self.sector)
        out=bytearray()
        remaining=sectors
        while remaining:
            n=min(remaining,2048)  # <= ~4.8 MB de dados físicos por lote
            raw=self.f.read(n*self.sector)
            if len(raw)!=n*self.sector:
                raise ValueError('Fim inesperado do disco')
            if self.sector==2048:
                out.extend(raw)
            else:
                mv=memoryview(raw)
                for i in range(n):
                    begin=i*self.sector+self.offset
                    out.extend(mv[begin:begin+2048])
                mv.release()
            remaining-=n
        return bytes(out[:length])
    @staticmethod
    def _records(data):
        at=0
        while at<len(data):
            length=data[at]
            if length==0:
                at=((at//2048)+1)*2048;continue
            if at+length>len(data):break
            chunk=data[at:at+length]
            if len(chunk)>=34:
                lba=struct.unpack_from('<I',chunk,2)[0]
                size=struct.unpack_from('<I',chunk,10)[0]
                flag=chunk[25]; nlen=chunk[32]
                name=chunk[33:33+nlen].decode('ascii','replace').split(';')[0]
                yield(name,lba,size,flag)
            at+=length
    def list_files(self):
        pvd=self.read(16,2048)
        root=pvd[156:156+pvd[156]]
        if len(root)<34:raise ValueError('Diretório raiz inválido')
        start,size=struct.unpack_from('<I',root,2)[0],struct.unpack_from('<I',root,10)[0]
        found={}
        def walk(prefix,lba,length,depth):
            if depth>8:raise ValueError('Árvore de diretórios muito profunda')
            for name,entry_lba,nbytes,flag in self._records(self.read(lba,length)):
                if name in ('\x00','\x01','.', '..'):continue
                name=name.upper().strip()
                p=(prefix+'/'+name).lstrip('/')
                if flag&2:walk(p,entry_lba,nbytes,depth+1)
                else:found[p]=(entry_lba,nbytes)
        walk('',start,size,0)
        return found
    def get(self,name,limit_bytes=None):
        name=name.upper()
        if name not in self.files:raise KeyError(f'Arquivo ausente: {name}')
        lba,size=self.files[name]
        if limit_bytes is not None:
            size=min(size,max(0,int(limit_bytes)))
        return self.read(lba,size)
    def close(self):self.f.close()

def decode_names(sl):
    if len(sl)<0x1C9800+93*4: return [],[], 'Executável menor que o layout conhecido'
    try: glyphs=[struct.unpack_from('<H',sl,SLUS_GLYPHS+4*i)[0] for i in range(93)]
    except struct.error:return [],[],'Fonte de glifos não encontrada'
    def txt(index):
        ptr=struct.unpack_from('<H',sl,SLUS_PTR_BASE+index*2)[0]
        pos=SLUS_TEXT_BASE+ptr
        if pos<0 or pos>=len(sl):return None
        raw=sl[pos+3:pos+150] if sl[pos:pos+2]==b'\xf8\x0a' else sl[pos:pos+150]
        s=[]
        for c in raw:
            if c==255:break
            if c==0:s.append(' ');continue
            if c<len(glyphs) and glyphs[c]:
                try:s.append(glyphs[c].to_bytes(2,'big').decode('shift_jis'))
                except UnicodeError:s.append('?')
            else:s.append('�')
        return unicodedata.normalize('NFKC',''.join(s)).strip()
    opponents=[];cards=[]
    for i in range(1,40):opponents.append({'id':i,'nome':txt(0x328+i) or ''})
    for i in range(1,723):
        name=txt(i) or ''
        packed=struct.unpack_from('<I',sl,SLUS_ATTRIBUTES+(i-1)*4)[0]
        detail=sl[0x1C5B33+i-1] if 0x1C5B33+i-1<len(sl) else 0
        cards.append({'id':i,'nome':name,'atk':(packed&511)*10,
            'def':((packed>>9)&511)*10,'tipo':(packed>>26)&31,
            'nivel':detail&15,'atributo':(detail>>4)&15,
            'estrela_1':(packed>>18)&15,'estrela_2':(packed>>22)&15})
    def plausible(s):return bool(s) and len(s)<=64 and '�' not in s and '[' not in s and sum(ch.isalpha() or ch.isdigit() for ch in s)>=2
    n_good=sum(plausible(x['nome']) for x in opponents)
    card_good=sum(plausible(x['nome']) for x in cards)
    if n_good<30 or card_good<600:
        return [],[],f'Codificação diferente/ambígua: {n_good}/39 nomes, {card_good}/722 cartas plausíveis'
    return opponents,cards,f'{n_good}/39 nomes, {card_good}/722 cartas decodificados'

def decode_drops(wa,rank_names=None):
    # A interpretação dos três grupos de drops varia por mod. Somente X15
    # tem os nomes Z-POW/S-POW/S-TEC confirmados nesta base.
    rank_names = rank_names or tuple(f"TABELA_{i+1}_RANK_DESCONHECIDO" for i in range(3))
    if len(wa)<WA_OPP_BASE+(OPP_COUNT-1)*WA_OPP_STEP+3*WA_RANK_STRIDE+WA_ARRAY_BYTES:
        return None,'Arquivo WA menor que a tabela conhecida'
    rows=[];check=[];deck=[];encodings=[]
    for i in range(OPP_COUNT):
        base=WA_OPP_BASE+i*WA_OPP_STEP
        deckweights=struct.unpack_from('<722H',wa,base)
        for cid,w in enumerate(deckweights,1):
            if w:deck.append({'oponente_id':i+1,'carta_id':cid,'peso':w})
        for ri,rank in enumerate(rank_names):
            a=base+(ri+1)*WA_RANK_STRIDE
            raw=struct.unpack_from('<722H',wa,a)
            candidates=[]
            if max(raw)<=2048 and sum(raw)==2048:
                candidates.append(('simples',raw))
            if all(v>=2512 and (v-2512)%8<=6 for v in raw):
                w=tuple((v-2512)//8 for v in raw)
                if sum(w)==2048:candidates.append(('mascarado_X15',w))
            if len(candidates)!=1:
                return None,f'Drops não validados para ID {i+1} / {rank}: formato desconhecido (opções={len(candidates)}), sem probabilidades atribuídas'
            enc,weights=candidates[0];encodings.append(enc)
            check.append({'oponente_id':i+1,'rank':rank,'peso_total':sum(weights),'codificacao':enc})
            for cid,w in enumerate(weights,1):
                if w: rows.append({'oponente_id':i+1,'rank':rank,'carta_id':cid,'peso':w,'chance_percentual':round(w*100/2048,6)})
    return {'drops':rows,'decks':deck,'verificacao':check,'codificacoes':sorted(set(encodings))},'117/117 tabelas validadas; soma 2048 por tabela'

def art_extract(wa,cards,dest):
    """Exporta artes somente do layout conhecido, com erro explicativo."""
    try:
        from PIL import Image
    except ImportError:
        return 0, "Pillow indisponível: nenhuma arte exportada"
    dest.mkdir(parents=True,exist_ok=True)
    n=0
    low_detail=0
    seen_ids=set()
    for card in cards:
        cid=int(card['id'])
        if not 1 <= cid <= CARD_COUNT or cid in seen_ids:
            return n, f"ID de arte inválido ou duplicado: {cid}"
        seen_ids.add(cid)
        base=((cid-1)*7+WA_CARD_SECTOR_START)*2048
        if base+0x2840>len(wa):
            return n, (f"Arquivo WA_MRG insuficiente para a arte ID {cid}; "
                       f"exportadas {n}/{len(cards)} imagens")
        raw_pixels=wa[base:base+0x2640]
        if len(raw_pixels)!=102*96:
            return n, f"Pixels incompletos na arte ID {cid}; exportadas {n}/{len(cards)}"
        if len(set(raw_pixels[::37])) < 4:
            low_detail+=1
        try:
            palette_raw=struct.unpack_from('<256H',wa,base+0x2640)
            pal=[]
            for value in palette_raw:
                pal.extend([(value&31)*255//31,((value>>5)&31)*255//31,
                            ((value>>10)&31)*255//31])
            img=Image.frombytes('P',(102,96),raw_pixels)
            img.putpalette(pal)
            img.save(dest/f"{cid:03d}.png",optimize=True)
            n+=1
        except (OSError,ValueError,struct.error) as exc:
            return n, f"Falha na arte ID {cid}: {type(exc).__name__}: {str(exc)[:130]}"
    if n==CARD_COUNT and low_detail>int(n*.80):
        return 0, ("Layout gráfico incompatível: muitas imagens uniformes; "
                   "as figuras não serão marcadas como extraídas.")
    return n, (f"{n}/{len(cards)} imagens exportadas e identificadas pelo ID, "
               f"102×96 PNG, origem WA_MRG 7 setores/carta. "
               f"Prévia visual em jogo ainda requer confirmação.")

def write_csv(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def process(path,output,with_art=False,digest=None,progress=None):
    info={'arquivo':path.name,'tamanho':path.stat().st_size,
          'sha256':digest or sha256(path,progress=progress),'status':'não validado',
          'art_requested':bool(with_art),
          'art_parser_revision':ART_PARSER_REVISION if with_art else None}
    key=re.sub(r'[^a-zA-Z0-9_-]+','_',path.stem)[:42]+'_'+info['sha256'][:10]
    dest=output/key;dest.mkdir(parents=True,exist_ok=True)
    # Contrato de dados: o scanner é a única fonte do caminho da extração.
    # O importador NÃO deve tentar reconstruir esse nome a partir da ISO.
    info['resultado_dir']=str(dest.resolve())
    # Não reaproveitar CSVs desatualizados de uma tentativa anterior.
    for previous in ('cartas.csv','oponentes.csv','drops_por_oponente.csv',
                     'decks.csv','validacao_pesos.csv'):
        (dest/previous).unlink(missing_ok=True)
    disc=None
    try:
        if progress:progress("Lendo índice ISO9660",0,1)
        disc=Disc(path);info['tipo_setor']=disc.sector
        info['arquivos_discos']=[{'nome':n,'lba':lba,'tamanho':sz} for n,(lba,sz) in sorted(disc.files.items())]
        # SLUS_014.11 pode estar na raiz ou dentro da pasta DATA.
        sl_names=[n for n in disc.files if re.fullmatch(
            r'SL[UP][A-Z0-9_.]+',n.rsplit('/',1)[-1])]
        sl_names=sorted(sl_names,key=lambda x:(
            x.rsplit('/',1)[-1]!='SLUS_014.11',len(x),x))
        if not sl_names:
            sl_names=sorted(n for n in disc.files if n.endswith('.EXE'))
        wa_names=sorted((n for n in disc.files if n.endswith('WA_MRG.MRG')),
                        key=lambda x:(not x.startswith('DATA/'),x))
        if not sl_names or not wa_names:
            raise ValueError(f'Layout FM PS1 incompleto; executáveis={sl_names}, WA={wa_names}')
        # O catálogo e as imagens exigem o WA até os pacotes de duelo.
        # A extração profunda lê o WA completo, não apenas seu prefixo.
        wa_required=max(
            WA_OPP_BASE+(OPP_COUNT-1)*WA_OPP_STEP+3*WA_RANK_STRIDE+WA_ARRAY_BYTES,
            ((CARD_COUNT-1)*WA_CARD_SECTORS+WA_CARD_SECTOR_START)*2048+0x2840,
        )
        if progress:progress("Lendo executável do jogo",0,1)
        sl=disc.get(sl_names[0])
        if progress:progress("Lendo tabelas necessárias do WA_MRG",0,1)
        wa_size=disc.files[wa_names[0]][1]
        if wa_size>96*1024*1024:
            raise ValueError('WA_MRG maior que 96 MiB: análise interrompida por segurança')
        wa=disc.get(wa_names[0]) if with_art else disc.get(wa_names[0],limit_bytes=wa_required)
        info['executavel']=sl_names[0]
        info['hash_executavel']=hashlib.sha256(sl).hexdigest()
        info['wa_prefix_bytes']=len(wa)
        info['wa_total_bytes']=disc.files[wa_names[0]][1]
        info['hash_wa_prefix']=hashlib.sha256(wa).hexdigest()
        info['hash_wa']=hashlib.sha256(wa).hexdigest() if len(wa)==wa_size else None
        info['wa_lido_integralmente']=len(wa)==wa_size
        info['versao_conhecida']='Remaster X15 1.2.1' if info['sha256']==X15_SHA else 'desconhecida — não atribuir dados X15'
        if progress:progress("Decodificando cartas e adversários",0,1)
        opponents,cards,nomes_status=decode_names(sl)
        info['nomes_status']=nomes_status
        from fm_card_text import extract_descriptions
        descriptions,desc_state=extract_descriptions(sl,exe_name=sl_names[0])
        info['descricoes_slus']=desc_state
        if cards and desc_state.get('valid'):
            for card in cards:
                row=descriptions.get(card['id'])
                card['descricao']=row['text'] if row else ''
                card['descricao_fonte']=row['source'] if row else ''
        if opponents:
            write_csv(dest/'oponentes.csv',opponents)
            write_csv(dest/'cartas.csv',cards)
            info['oponentes']=len(opponents);info['cartas']=len(cards)
        if progress:progress("Validando pesos das tabelas de drops",0,1)
        drops,drop_status=decode_drops(wa,RANKS if info['sha256']==X15_SHA else None)
        info['rotulos_ranks_confirmados']=info['sha256']==X15_SHA
        info['drops_status']=drop_status
        if drops is not None:
            info['tabelas_drops']=len(drops['verificacao']);info['drops']=len(drops['drops'])
            for keyname,filename in [('drops','drops_por_oponente.csv'),('decks','decks.csv'),('verificacao','validacao_pesos.csv')]:write_csv(dest/filename,drops[keyname])
            info['codificacao_drops']=drops['codificacoes']
        if with_art:
            if opponents:
                from fm_deep_assets import extract_asset_pack
                pack=extract_asset_pack(wa,cards,dest,rom_sha256=info['sha256'],
                                        wa_name=wa_names[0])
                info['artes_extraidas']=pack['art_count']
                info['miniaturas_extraidas']=pack['thumbnail_count']
                info['molduras_extraidas']=pack['frame_count']
                info['cartas_com_moldura']=pack['composed_count']
                info['artes_status']=pack['status']
                info['artes_obs']=' | '.join(pack.get('warnings',[])[:4]) or pack['status']
                info['artes_origem']='WA_MRG.MRG: arte 102x96, miniatura 40x32 e moldura 52x60 do duelo'
                info['artes_layout_confirmado_na_versao']=info['sha256']==X15_SHA
            else:
                info['artes_extraidas']=0
                info['artes_obs']="O scanner não reconheceu uma tabela de cartas compatível com a extração de artes."
        if opponents and drops:
            info['status']='validado: nomes e drops'
        elif opponents:info['status']='parcial: nomes/cartas identificados; drops sem validação'
        else:info['status']='incerto: estrutura não reconhecida; sem atribuições automáticas'
    except Exception as e:
        info['status']='erro/estrutura incompatível';info['problema']=str(e)
    finally:
        if disc:disc.close()
    (dest/'relatorio.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf8')
    if progress:progress("Análise concluída",1,1)
    return info

def main():
    ap=argparse.ArgumentParser(description='Extração MultiMod de ISOs locais, sem download e sem alterar arquivos')
    ap.add_argument('--entrada',required=True,type=Path,help='Pasta de ISOs .bin/.iso ou arquivo individual')
    ap.add_argument('--saida',default=Path('analises_multimod'),type=Path)
    ap.add_argument('--artes',action='store_true',help='Extrair artes individuais quando a estrutura for reconhecida')
    args=ap.parse_args()
    paths=sorted(p for p in args.entrada.rglob('*') if p.is_file() and p.suffix.lower() in ('.bin','.iso')) if args.entrada.is_dir() else [args.entrada]
    args.saida.mkdir(parents=True,exist_ok=True)
    all_infos=[];processed={}
    for path in paths:
        digest=sha256(path)
        if digest in processed:
            print('ISO duplicada:',path.name,'igual a',processed[digest]);continue
        processed[digest]=path.name
        print('Analisando:',path.name,flush=True)
        info=process(path,args.saida,args.artes,digest=digest)
        all_infos.append(info)
        print('  ->',info['status'],info.get('drops_status',''))
    summary=[{'nome':r['arquivo'],'sha256':r['sha256'],'versao':r.get('versao_conhecida',''),'status':r['status'],'oponentes':r.get('oponentes',0),'cartas':r.get('cartas',0),'drops':r.get('drops',0),'codificacao':','.join(r.get('codificacao_drops',[]))} for r in all_infos]
    write_csv(args.saida/'resumo_mods.csv',summary)
    print(f'Concluído: {len(all_infos)} ISO(s); resultados em {args.saida}')
if __name__=='__main__':main()
