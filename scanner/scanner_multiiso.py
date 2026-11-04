#!/usr/bin/env python3
"""Leitor MULTI-ISO apenas para arquivos locais fornecidos/obtidos legitimamente.

Não baixa nem distribui imagens de jogos. Para formatos desconhecidos, não inventa dados.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, struct, sys, unicodedata
from pathlib import Path
from dueltrace_layout_discovery import discover_disc_layout, candidate_files_for_decoder
from dueltrace_name_layout_probe import find_opponent_pointer_candidates
from dueltrace_name_boundaries import inspect_opponent_name_boundaries, read_name_table

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
ART_PARSER_REVISION=6  # busca de RANK por conteúdo no WA completo, mesmo sem artes
SCAN_PARSER_REVISION=7  # limites de nomes, descoberta e validação de catálogos/drops


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

def inspect_file_signatures(disc, *, max_files=48):
    """Inventário de assinaturas dos arquivos ISO9660 sem extração de conteúdo.

    Lê até 32 bytes por arquivo. Não assume que um arquivo sem extensão
    SLUS/WA seja vazio ou que seu formato tenha sido reconhecido.
    """
    probes=[]
    for name,(lba,size) in sorted(disc.files.items())[:max_files]:
        if type(size) is not int or size<=0:
            probes.append({"nome":name,"assinatura":"vazio_ou_invalido",
                           "prefix_sha256":None})
            continue
        try:
            raw=disc.get(name,limit_bytes=32)
        except (OSError,ValueError,KeyError):
            probes.append({"nome":name,"assinatura":"erro_leitura",
                           "prefix_sha256":None})
            continue
        if raw.startswith(b"PS-X EXE"):
            signature="psx_executavel"
        elif raw.startswith(b"RIFF"):
            signature="riff"
        elif raw.startswith(b"TIM2"):
            signature="tim2"
        else:
            signature="desconhecida"
        probes.append({"nome":name,"assinatura":signature,
                       "prefix_sha256":hashlib.sha256(raw).hexdigest()[:16]})
    return probes


def inspect_system_cnf(disc):
    """Consulta apenas a indicação BOOT, sem executar nem extrair binários.

    Alguns mods usam nomes de executáveis diferentes das famílias SLUS/SCUS.
    O SYSTEM.CNF geralmente contém a referência explícita do executável.
    """
    candidates=sorted(name for name in disc.files
                      if name.rsplit("/",1)[-1]=="SYSTEM.CNF")
    if not candidates:
        return {"found":False,"boot_target":None,"status":"SYSTEM.CNF não localizado"}
    name=candidates[0]
    size=disc.files[name][1]
    if type(size) is not int or not 0<size<=16384:
        return {"found":True,"boot_target":None,
                "status":"SYSTEM.CNF com tamanho incomum; não foi lido"}
    raw=disc.get(name,limit_bytes=16384)
    text=raw.decode("latin-1",errors="replace")
    match=re.search(
        r"(?im)^\s*BOOT(?:2)?\s*=\s*(?:cdrom\d?:)?[/\\]*([A-Za-z0-9_.\\/-]+)(?:;\d+)?",
        text)
    if not match:
        return {"found":True,"boot_target":None,
                "status":"SYSTEM.CNF encontrado, mas BOOT não foi reconhecido"}
    target=match.group(1).replace("\\","/").strip("/").upper()
    if not target or ".." in target.split("/"):
        return {"found":True,"boot_target":None,
                "status":"Referência BOOT inválida"}
    return {"found":True,"boot_target":target,
            "status":"BOOT identificado, apenas como indicação de arquivo"}


def decode_names(sl):
    if len(sl)<0x1C9800+93*4: return [],[], 'Executável menor que o layout conhecido'
    try:
        records=read_name_table(sl,pointer_base=SLUS_PTR_BASE,
            text_base=SLUS_TEXT_BASE,glyph_base=SLUS_GLYPHS,
            indices=tuple(range(1,723))+tuple(range(0x329,0x350)))
    except (ValueError,struct.error):return [],[],'Fonte de glifos/ponteiros não encontrada'
    def txt(index):
        record=records[index]
        # Um FF além do próximo registro não termina este nome. Não adivinhar
        # terminadores alternativos nem retirar um glifo legível (como "v").
        return record['readablePrefix'] if record['recordStatus']=='ff_encontrado' else None
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

def inspect_known_name_layout(sl):
    """Amostras de offsets do FM original em mod não reconhecido.

    NÃO aprova o catálogo, oponente ou glifo. Seu único propósito é mostrar
    possíveis deslocamentos e caracteres ilegíveis para diagnóstico.
    """
    required=max(SLUS_GLYPHS+93*4,SLUS_PTR_BASE+(0x328+40)*2)
    if len(sl)<required:
        return {"state":"incompatível","reason":"Executável menor que a tabela de ponteiros/glifos conhecida",
                "cardSamples":[],"opponentSamples":[]}
    try:
        records=read_name_table(sl,pointer_base=SLUS_PTR_BASE,
            text_base=SLUS_TEXT_BASE,glyph_base=SLUS_GLYPHS,
            indices=tuple(range(1,723))+tuple(range(0x329,0x350)),max_bytes=100)
    except (ValueError,struct.error):
        return {"state":"incompatível","reason":"Tabela de glifos fora do arquivo",
                "cardSamples":[],"opponentSamples":[]}
    def sample(index):
        address=SLUS_PTR_BASE+index*2
        if address+2>len(sl):
            return {"index":index,"pointer":None,"name":"","status":"ponteiro_fora_do_arquivo"}
        ptr=struct.unpack_from("<H",sl,address)[0]
        record=records[index]
        name=record['readablePrefix'][:80]
        invalid=int(record['firstInvalidHex'] is not None)
        plausible=record['recordStatus']=='ff_encontrado' and bool(name) and len(name)<=64 and (
            sum(x.isalnum() for x in name)>=2)
        return {"index":index,"pointer":ptr,"name":name,
                "status":"caracteres_plausiveis" if plausible else "invalido_ou_vazio",
                "invalidGlyphs":invalid,"recordStatus":record['recordStatus'],
                "terminatorOffset":record['terminatorOffset']}
    ids=(1,2,3,10,25,50,100,200,400,722)
    opponent_ids=(1,2,3,10,20,30,39)
    cards=[sample(i) for i in ids]
    opponents=[sample(0x328+i) for i in opponent_ids]
    return {
        "state":"amostras_nao_validadas",
        "cardSamples":cards,"opponentSamples":opponents,
        "cardPlausibleSamples":sum(row["status"]=="caracteres_plausiveis" for row in cards),
        "opponentPlausibleSamples":sum(row["status"]=="caracteres_plausiveis" for row in opponents),
        "note":"Nomes e ponteiros são amostras de offsets conhecidos, não identidades confirmadas.",
    }


def select_known_executable_layout(disc, candidates, *, max_candidates=8):
    """Testa executáveis existentes; nunca adivinha/valida offsets novos.

    Sempre começa pela prioridade tradicional. Só muda de executável se
    `decode_names` reconhecer o catálogo completo pelo mesmo critério usado
    antes. Lê no máximo oito arquivos de até 8 MiB para reduzir custo.
    """
    if not candidates:
        raise ValueError("Nenhum executável candidato.")
    tried=[]
    chosen=candidates[0]
    sl=disc.get(chosen)
    opponents,cards,status=decode_names(sl)
    tried.append({"name":chosen,"status":status,"recognized":bool(opponents and cards)})
    if opponents and cards:
        return chosen,sl,opponents,cards,status,tried
    for alternative in candidates[1:max_candidates]:
        size=disc.files.get(alternative,(None,0))[1]
        if type(size) is not int or not 0<size<=8*1024*1024:
            tried.append({"name":alternative,"status":"tamanho fora do limite de análise",
                          "recognized":False})
            continue
        contender=disc.get(alternative)
        opp2,cards2,status2=decode_names(contender)
        tried.append({"name":alternative,"status":status2,
                      "recognized":bool(opp2 and cards2)})
        if opp2 and cards2:
            return alternative,contender,opp2,cards2,status2,tried
    return chosen,sl,opponents,cards,status,tried


# Tamanho da tabela de recursos observado em ISOs com WA_MRG.MRG.
# Coincidência de tamanho é indício para SONDAGEM, jamais validação de formato.
KNOWN_WA_SIZE_BYTES=38_148_608


def select_wa_candidates(files):
    """Seleciona apenas um recurso candidato; sem promover arquivo por tamanho.

    Formato retorno: (nomes selecionados, método, candidatas por tamanho).
    No layout clássico, o nome WA_MRG tem precedência. Em mods com
    contêiner renomeado, aceita UMA correspondência exata de tamanho apenas
    para executar as validações existentes. Ambiguidade aborta a tentativa.
    """
    named=sorted(
        (n for n in files if n.endswith("WA_MRG.MRG")),
        key=lambda x:(not x.startswith("DATA/"),x))
    possibilities=sorted(
        n for n,value in files.items()
        if isinstance(value,tuple) and len(value)==2
        and type(value[1]) is int and value[1]==KNOWN_WA_SIZE_BYTES
        and not n.endswith("WA_MRG.MRG"))
    if named:
        return named,"nome_convencional",possibilities
    if len(possibilities)==1:
        return possibilities,"tamanho_identico_nao_validado",possibilities
    return [],("multiplos_candidatos" if len(possibilities)>1
               else "nenhum_candidato"),possibilities


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
            check.append({'oponente_id':i+1,'rank':rank,'peso_total':sum(weights),'codificacao':enc,'source_offset':a})
            for cid,w in enumerate(weights,1):
                if w: rows.append({'oponente_id':i+1,'rank':rank,'carta_id':cid,'peso':w,'chance_percentual':round(w*100/2048,6),'source_offset':a+(cid-1)*2})
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
          'scan_parser_revision':SCAN_PARSER_REVISION,
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
        info['system_cnf']=inspect_system_cnf(disc)
        info['assinaturas_arquivos']=inspect_file_signatures(disc)
        # Independente de nomes e tamanho exato: verifica cabeçalho PS-X e
        # sondas estruturais limitadas nos contêineres grandes.
        info['layout_discovery']=discover_disc_layout(
            disc,boot_target=info['system_cnf'].get('boot_target'))
        # SLUS_014.11 pode estar na raiz ou dentro da pasta DATA.
        sl_names=[n for n in disc.files if re.fullmatch(
            r'(?:SLUS|SCUS|SLES|SCES|SLPS|SCPS|SLPM|SLED|SCED|SLKA)[A-Z0-9_.-]+',
            n.rsplit('/',1)[-1])]
        # Mods podem ter múltiplos executáveis: priorizar o SLUS solicitado
        # em DATA, sem perder compatibilidade com ISOs de executável na raiz.
        sl_names=sorted(sl_names,key=lambda x:(
            x!='DATA/SLUS_014.11',
            x.rsplit('/',1)[-1]!='SLUS_014.11',len(x),x))
        if not sl_names:
            sl_names=sorted(n for n in disc.files if n.endswith('.EXE'))
        boot_candidate=info["system_cnf"].get("boot_target")
        info['boot_alvo_indexado']=boot_candidate in disc.files if boot_candidate else None
        if (boot_candidate in disc.files
                and boot_candidate not in sl_names):
            # Apenas tentar um arquivo indicado explicitamente pelo sistema
            # de boot; a extração ainda depende do parser de nomes/atributos.
            sl_names=[boot_candidate]+sl_names
        for name in candidate_files_for_decoder(
                info['layout_discovery'],role="executavel"):
            if name not in sl_names:
                sl_names.append(name)
        wa_names,wa_source,size_matches=select_wa_candidates(disc.files)
        if not wa_names:
            structural=candidate_files_for_decoder(
                info['layout_discovery'],role="recursos")
            if structural:
                wa_names=structural
                wa_source="matrizes_2048_candidatas"
        info['wa_selecao_metodo']=wa_source
        info['wa_candidatos_por_tamanho']=size_matches[:12]
        # Nome alterado é SÓ hipótese: os decoders ainda devem validar
        # dados/offsets antes de habilitar cartas, artes e drops.
        info['wa_nome_alternativo_nao_validado']=wa_source in (
            "tamanho_identico_nao_validado","matrizes_2048_candidatas")
        # Registrar candidatos alternativos para análise, mas não assumir
        # automaticamente que outro .MRG contém as tabelas de Forbidden Memories.
        info['executaveis_candidatos']=sl_names[:20]
        info['wa_candidatos']=list(dict.fromkeys(
            [n for n in sorted(disc.files)
             if 'WA_MRG' in n or n.endswith('.MRG')]
            +size_matches
            +[row["name"] for row in info["layout_discovery"]["resources"]
              if row.get("dropArrayMatches",0)>=1]))[:20]
        if not sl_names or not wa_names:
            hint=('BOOT aponta para arquivo ausente do índice ISO9660.'
                  if boot_candidate and boot_candidate not in disc.files else
                  'BOOT identificado mas formato de recursos desconhecido.'
                  if boot_candidate else
                  'Nenhuma indicação BOOT utilizável.')
            raise ValueError(
                'Layout do mod ainda não reconhecido: '
                f'executáveis candidatos={sl_names[:6]}, '
                f'arquivos WA candidatos={info["wa_candidatos"][:6]}. '
                +hint+' Os arquivos podem ter nomes ou contêineres diferentes. '
                f'Indícios por tamanho: {size_matches[:4]} ({wa_source}).')
        # O catálogo e as imagens exigem o WA até os pacotes de duelo.
        # A extração profunda lê o WA completo, não apenas seu prefixo.
        wa_required=max(
            WA_OPP_BASE+(OPP_COUNT-1)*WA_OPP_STEP+3*WA_RANK_STRIDE+WA_ARRAY_BYTES,
            ((CARD_COUNT-1)*WA_CARD_SECTORS+WA_CARD_SECTOR_START)*2048+0x2840,
            7475*2048+0x16D0+39*3*2048+200,
        )
        if progress:progress("Lendo executáveis candidatos do jogo",0,1)
        selected_exe,sl,opponents,cards,nomes_status,exe_checks=(
            select_known_executable_layout(disc,sl_names))
        info['testes_executaveis']=exe_checks
        info['executavel_selecionado_por_catalogo']=selected_exe!=sl_names[0]
        if progress:progress("Lendo WA_MRG completo para localizar RANK",0,1)
        wa_size=disc.files[wa_names[0]][1]
        if wa_size>96*1024*1024:
            raise ValueError('WA_MRG maior que 96 MiB: análise interrompida por segurança')
        if wa_size<wa_required:
            info['wa_incompleto_para_layout_x15']=True
        # O RANK pode estar deslocado em outros mods. Sem a leitura integral,
        # um scan sem artes ignorava os últimos 216 bytes do bloco conhecido
        # e nunca conseguiria identificar tabelas realocadas.
        wa=disc.get(wa_names[0])
        info['executavel']=selected_exe
        info['hash_executavel']=hashlib.sha256(sl).hexdigest()
        from fm_rank_mips_evidence import inspect_mips_rank_routines
        info['rank_mips_evidence']=inspect_mips_rank_routines(sl)
        info['wa_prefix_bytes']=len(wa)
        info['wa_total_bytes']=disc.files[wa_names[0]][1]
        wa_sha=hashlib.sha256(wa).hexdigest()
        info['hash_wa_prefix']=wa_sha
        info['hash_wa']=wa_sha if len(wa)==wa_size else None
        info['wa_lido_integralmente']=len(wa)==wa_size
        if info['wa_nome_alternativo_nao_validado']:
            info['wa_identificacao_obs']=(
                "Contêiner sem nome WA_MRG selecionado por tamanho ou "
                "por matrizes candidatas no offset antigo. Isso NÃO valida "
                "drops, artes, cartas ou fusões; a extração continua sob "
                "as verificações estruturais completas.")
        from fm_rank_tables import extract_rank_table
        info['rank_analysis']=extract_rank_table(
            wa,slus=sl,rom_sha256=info['sha256'],known_rom_sha256=X15_SHA)
        info['versao_conhecida']='Remaster X15 1.2.1' if info['sha256']==X15_SHA else 'desconhecida — não atribuir dados X15'
        if progress:progress("Decodificando cartas e adversários",0,1)
        info['nomes_status']=nomes_status
        if not opponents or not cards:
            info["amostras_layout_nomes"]=inspect_known_name_layout(sl)
            # Quando 722 nomes parecem possíveis e a lista de oponentes
            # falha, sondar deslocamentos limitados na tabela de ponteiros.
            # Resultados são SOMENTE hipóteses de investigação.
            info["opponent_pointer_candidates"]=find_opponent_pointer_candidates(
                sl,pointer_base=SLUS_PTR_BASE,text_base=SLUS_TEXT_BASE,
                glyph_base=SLUS_GLYPHS)
            info["opponent_name_boundaries"]=inspect_opponent_name_boundaries(
                sl,pointer_base=SLUS_PTR_BASE,text_base=SLUS_TEXT_BASE,
                glyph_base=SLUS_GLYPHS)
        from fm_card_text import extract_descriptions
        descriptions,desc_state=extract_descriptions(sl,exe_name=selected_exe)
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
        from dueltrace_rank_system import CLASSIC_POOLS
        drops,drop_status=decode_drops(
            wa,RANKS if info['sha256']==X15_SHA else CLASSIC_POOLS)
        info['rank_display_model']=(
            'x15_sha_verificado' if info['sha256']==X15_SHA
            else 'padrao_original_presumido')
        info['rotulos_ranks_confirmados']=info['sha256']==X15_SHA
        info['drops_status']=drop_status
        info['drops_source']=wa_names[0]
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
                info['artes_origem']=(
                    wa_names[0]+": artes 102x96, miniatura 40x32 e moldura 52x60 "
                    "(layout sujeito a validação específica da ISO)")
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
