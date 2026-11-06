"""Conservative FM text-bank 0xFD jump audit, never an ID decoder.

Retail FM's Text_SetCursorOffset reads FD lo hi as a little-endian target
that replaces the low 16 bits of the current text cursor. This hypothesis
is tested ONLY inside the same observed text bank; mods may redefine the
control. Nothing here publishes reconstructed opponent names or ranks.
"""
from __future__ import annotations
from collections import Counter

MAX_WINDOWS=5
OPP_COUNT=39
MAX_NAME_BYTES=96
MAX_EXE_BYTES=8*1024*1024
BANK_BYTES=0x10000

def audit_fd_jumps(exe:bytes, *, start_index:int, records:dict,
                   pointers:dict, text_base:int) -> dict:
    data={
      "schema":1,"state":"incompleto","recordCount":0,
      "fdRecords":0,"fdWithTwoArguments":0,"fdTruncated":0,
      "jumpTargetInBank":0,"jumpTargetOutOfFile":0,
      "jumpTargetAtSource":0,"jumpTargetHasFF":0,
      "jumpTargetStartsFD":0,"jumpTargetStartsF8":0,
      "jumpTargetStartsFF":0,"jumpTargetSameAsAnotherPointer":0,
      "jumpTargetDistinctCount":0,"fdArgumentHighZero":0,
      "fdArgumentHighNonZero":0,"directFFAfterFD":0,
      "inGameVerified":False,"validated":False,"mayPromote":False,
      "dropsVerified":False,"rankVerified":False
    }
    if (not isinstance(exe,bytes) or not 0<len(exe)<=MAX_EXE_BYTES
        or type(start_index) is not int or start_index<0
        or type(text_base) is not int or text_base<0
        or not isinstance(records,dict) or not isinstance(pointers,dict)):
        data["state"]="entrada_invalida"
        return data
    try:
        ids=range(start_index,start_index+OPP_COUNT)
        positions=[text_base+pointers[i] for i in ids]
        rows=[records[i] for i in ids]
    except (KeyError,TypeError):
        data["state"]="ponteiros_ausentes"
        return data
    if (any(type(p) is not int or not 0<=p<len(exe) for p in positions)
        or any(not isinstance(row,dict) for row in rows)):
        data["state"]="registros_invalidos"
        return data
    pointer_positions=set(positions)
    seen_targets=set()
    for pos,row in zip(positions,rows):
        span=row.get("spanBytes")
        if type(span) is not int or span<=0:
            continue
        start=pos+(3 if row.get("headerPresent") is True else 0)
        end=min(len(exe),pos+min(span,MAX_NAME_BYTES))
        if start>=end:
            continue
        data["recordCount"]+=1
        raw=exe[start:end]
        ff=raw.find(b"\xff")
        # FD appearing after FF is not part of that terminated string.
        limit=ff if ff>=0 else len(raw)
        fd=raw.find(b"\xfd",0,limit)
        if fd<0:continue
        data["fdRecords"]+=1
        if fd+2>=limit:
            data["fdTruncated"]+=1
            continue
        low,high=raw[fd+1],raw[fd+2]
        data["fdWithTwoArguments"]+=1
        data["fdArgumentHighZero" if high==0 else "fdArgumentHighNonZero"]+=1
        if fd+3<limit and raw[fd+3]==0xff:
            data["directFFAfterFD"]+=1
        target=text_base+(low|(high<<8))
        if not text_base<=target<text_base+BANK_BYTES or target>=len(exe):
            data["jumpTargetOutOfFile"]+=1
            continue
        data["jumpTargetInBank"]+=1
        seen_targets.add(target)
        if target==start or target==pos:
            data["jumpTargetAtSource"]+=1
        if target in pointer_positions:
            data["jumpTargetSameAsAnotherPointer"]+=1
        first=exe[target]
        if first==0xfd:data["jumpTargetStartsFD"]+=1
        if first==0xf8:data["jumpTargetStartsF8"]+=1
        if first==0xff:data["jumpTargetStartsFF"]+=1
        stop=min(len(exe),text_base+BANK_BYTES,target+MAX_NAME_BYTES)
        if b"\xff" in exe[target:stop]:
            data["jumpTargetHasFF"]+=1
    data["jumpTargetDistinctCount"]=len(seen_targets)
    if data["fdRecords"]:
        data["state"]="salto_fd_hipotese_estrutural"
    else:
        data["state"]="nenhum_salto_fd"
    return data


def inspect_fd_jump_windows(exe:bytes, *, hypotheses:list, records:dict,
                            pointers:dict, text_base:int) -> dict:
    result={"schema":1,"state":"sem_janelas","windows":[],
            "inGameVerified":False,"mayPromote":False}
    if not isinstance(hypotheses,list):
        return result
    for hypothesis in hypotheses:
        if len(result["windows"])>=MAX_WINDOWS:break
        start=hypothesis.get("startIndex") if isinstance(hypothesis,dict) else None
        if type(start) is not int:continue
        result["windows"].append(audit_fd_jumps(
            exe,start_index=start,records=records,
            pointers=pointers,text_base=text_base))
    if result["windows"]:
        result["state"]="janelas_auditadas"
    return result
