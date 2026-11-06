"""Evidência MIPS R3000: referências estáticas a tabelas dentro de PS-X EXE.

Integra Capstone 5 quando disponível, apenas para exibir instruções
encontradas; a detecção determinística funciona sem dependências externas.
NÃO executa instruções, não emula o jogo, não identifica significados de
cartas/drops e não altera nenhuma ISO ou perfil. Endereços são pistas.
"""
from __future__ import annotations

import hashlib
import struct

from dueltrace_layout_discovery import inspect_psx_executable_header

HEADER_BYTES=0x800
MAX_EXECUTABLE_BYTES=8*1024*1024
MAX_SCAN_BYTES=2*1024*1024
MAX_TARGETS=8
MAX_RESULTS=16
MAX_PAIR_DISTANCE=5
# São apenas as primeiras posições da tabela; referências para posições
# muito distantes não identificam com segurança o início da estrutura.
MAX_TARGET_DELTA_BYTES=32

def _signed16(value:int)->int:
    return value-0x10000 if value&0x8000 else value

def _physical(value:int)->int|None:
    value &= 0xFFFFFFFF
    if value & 0xE0000000 not in (0,0x80000000,0xA0000000):
        return None
    physical=value&0x1FFFFFFF
    return physical if physical<0x200000 else None

def _capstone_context(exe:bytes,offset:int,base:int,count:int)->list[dict]:
    """Até oito instruções, sem depender do Capstone para reconhecer tabelas."""
    try:
        from capstone import Cs,CS_ARCH_MIPS,CS_MODE_MIPS32,CS_MODE_LITTLE_ENDIAN
        md=Cs(CS_ARCH_MIPS,CS_MODE_MIPS32|CS_MODE_LITTLE_ENDIAN)
        fragment=exe[offset:min(offset+count*4,len(exe))]
        result=[]
        for inst in md.disasm(fragment,base):
            result.append({"pc":f"0x{inst.address:08X}",
                           "mnemonic":str(inst.mnemonic)[:16],
                           "operands":str(inst.op_str)[:80]})
            if len(result)>=8:
                break
        return result
    except (ImportError,Exception) as exc:
        # Algumas compilações Windows podem não incluir o componente
        # opcional. A varredura estruturada ainda funciona sem Capstone.
        return []

def inspect_mips_table_references(exe:bytes,table_file_offsets,
                                  *,max_scan_bytes:int=MAX_SCAN_BYTES)->dict:
    """Cruza LUI+ADDIU/ORI/loads com endereços de tabelas candidatas.

    O endereço PS1 é obtido do cabeçalho PS-X EXE e normalizado para RAM
    física; KSEG0 e KSEG1 são aliases. Um match é estático e não demonstra
    que a instrução foi executada nem que os IDs estão corretos.
    """
    result={"schema":1,"state":"sem_evidencia","validated":False,
            "executionConfirmed":False,"engine":"mips32_structural",
            "capstoneAvailable":False,"exeSha256":None,
            "scanBytes":0,"targets":[],"references":[]}
    if not isinstance(exe,bytes) or not HEADER_BYTES<len(exe)<=MAX_EXECUTABLE_BYTES:
        result["state"]="executavel_invalido"
        return result
    result["exeSha256"]=hashlib.sha256(exe).hexdigest()
    header=inspect_psx_executable_header(exe[:HEADER_BYTES],len(exe))
    # A GOG executable can have a PS-X EXE signature but an unsupported
    # RAM/load mapping, or may not have the signature at all. Report which
    # validation failed instead of guessing a load address and decoding
    # arbitrary bytes as MIPS code.
    safe_header_states={
        "cabecalho_invalido","cabecalho_truncado",
        "payload_truncado_ou_invalido","destino_ram_invalido",
        "entrada_fora_do_payload","cabecalho_coerente_nao_validado",
    }
    header_state=header.get("state")
    result["headerEvidence"]={
        "state":header_state if header_state in safe_header_states
                else "cabecalho_invalido",
        "magicPresent":exe.startswith(b"PS-X EXE"),
        "fileHasPayloadRegion":len(exe)>HEADER_BYTES,
        "mappingCoherent":bool(header.get("headerCoherent")),
        "validated":False
    }
    if not header.get("headerCoherent"):
        result["state"]="psx_header_invalido"
        return result
    if not isinstance(table_file_offsets,(tuple,list)) or len(table_file_offsets)>MAX_TARGETS:
        result["state"]="alvos_invalidos"
        return result
    payload=header["payloadSize"]
    load=header["loadAddress"]
    load_phys=_physical(load)
    if load_phys is None:
        result["state"]="mapeamento_ram_invalido"
        return result
    targets={}
    for offset in table_file_offsets:
        if (type(offset) is not int or offset<HEADER_BYTES or
                offset>=HEADER_BYTES+payload or offset%2):
            result["state"]="alvos_invalidos"
            return result
        phys=load_phys+offset-HEADER_BYTES
        if phys>=0x200000:
            result["state"]="alvos_invalidos"
            return result
        targets[offset]=phys
        result["targets"].append({"fileOffset":offset,
                                  "physicalAddress":f"0x{phys:08X}"})
    limit=min(payload,MAX_SCAN_BYTES,
              max(0,int(max_scan_bytes)) if type(max_scan_bytes) is int else 0)
    limit-=limit%4
    result["scanBytes"]=limit
    if not targets or limit<8:
        return result
    try:
        import capstone
        result["capstoneAvailable"]=True
        result["capstoneVersion"]=str(capstone.__version__)[:16]
    except ImportError:
        pass
    data=exe[HEADER_BYTES:HEADER_BYTES+limit]
    words=tuple(x[0] for x in struct.iter_unpack("<I",data))
    seen=set()
    refs=[]
    for index,word in enumerate(words):
        if word>>26!=0x0F:
            continue
        reg=(word>>16)&31
        if reg==0:
            continue
        high=(word&0xFFFF)<<16
        for distance in range(1,MAX_PAIR_DISTANCE+1):
            j=index+distance
            if j>=len(words):
                break
            w=words[j]
            op=w>>26
            rs=(w>>21)&31
            rt=(w>>16)&31
            low=w&0xFFFF
            kind=None
            address=None
            if rs==reg:
                if op==0x09 and rt==reg:
                    kind="lui_addiu"
                    address=(high+_signed16(low))&0xFFFFFFFF
                elif op==0x0D and rt==reg:
                    kind="lui_ori"
                    address=(high|low)&0xFFFFFFFF
                elif op in (0x20,0x21,0x23,0x24,0x25,0x27):
                    kind="lui_load"
                    address=(high+_signed16(low))&0xFFFFFFFF
            if address is not None:
                physical=_physical(address)
                if physical is not None:
                    for offset,target in targets.items():
                        delta=physical-target
                        if not 0<=delta<=MAX_TARGET_DELTA_BYTES:
                            continue
                        key=(index,j,offset)
                        if key in seen:
                            continue
                        seen.add(key)
                        pc=(load+index*4)&0xFFFFFFFF
                        reference={"tableFileOffset":offset,"deltaBytes":delta,
                                   "pc":f"0x{pc:08X}",
                                   "fileOffset":HEADER_BYTES+index*4,
                                   "matchType":kind,
                                   "targetAddress":f"0x{address:08X}",
                                   "validated":False}
                        if result["capstoneAvailable"]:
                            context=_capstone_context(
                                exe,HEADER_BYTES+index*4,pc,distance+1)
                            if context:
                                reference["disassembly"]=context
                        refs.append(reference)
                        if len(refs)>=MAX_RESULTS:
                            break
            # Nunca ligar LUI com instruções depois de saltos/branches.
            if op in (0x02,0x03,0x04,0x05,0x06,0x07):
                break
            # Quando outro LUI sobrescreve o registrador, o par anterior
            # deixa de identificar o endereço; evita falsos positivos.
            if op==0x0F and rt==reg:
                break
            if len(refs)>=MAX_RESULTS:
                break
        if len(refs)>=MAX_RESULTS:
            break
    result["references"]=refs
    result["state"]="referencias_mips_candidatas" if refs else "sem_evidencia"
    return result
