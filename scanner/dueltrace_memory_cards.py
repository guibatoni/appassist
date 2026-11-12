"""Leitura segura de memory cards PS1/ePSXe por mod, somente leitura.

O ePSXe continua sendo o único escritor do cartão original. DUELTRACE apenas
lê a imagem selecionada, cria cópias imutáveis e guarda decks localmente.
Formato: 128 KiB, 16 blocos de 8 KiB, diretório MC, save SC.
A posição da lista de 40 IDs é compatível com o layout FM pesquisado;
sem checksum de jogo confirmado a saída informa 'estrutural', não 'verificado'.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
from dueltrace_save_integrity import decode_save_block
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

SIZE = 131072
BLOCK = 8192
CARD_LIMIT = 722
CARD_EXTENSIONS = frozenset((".mcr",".mcd",".mc",".srm",".mem",".vm1"))
ROM_RE = re.compile(r"[a-f0-9]{64}\Z")
SAVE_NAME_RE = re.compile(r"(YUGIOH|YU-GI-OH)",re.IGNORECASE)
COPY_OFFSET = 0x200
CARD_COUNT = 40
MAX_SAVED = 256


def _frame_checksum(frame):
    check = 0
    for byte in frame[:127]:
        check ^= byte
    return check == frame[127]


def _extract_saves(blob):
    if len(blob) != SIZE or blob[:2] != b"MC" or not _frame_checksum(blob[:128]):
        raise ValueError("Arquivo não é memory card PS1 bruto de 128 KB.")
    found=[]
    for block in range(1,16):
        directory=blob[block*128:(block+1)*128]
        if directory[:4] != b"\x51\x00\x00\x00":
            continue
        if not _frame_checksum(directory):
            continue
        filename=directory[10:31].split(b"\x00",1)[0].decode("ascii","replace")
        if not SAVE_NAME_RE.search(filename):
            continue
        data=blob[block*BLOCK:(block+1)*BLOCK]
        checked=decode_save_block(data)
        if checked is None:
            continue
        found.append({"block":block,"saveName":filename,
                      "deckCount":CARD_COUNT,
                      "status":"save_ps1_integridade_validada_nao_comprovado_ativo",
                      **checked})
    return found

def parse_memory_card(blob):
    if not isinstance(blob,bytes):
        raise ValueError("Conteúdo do cartão inválido.")
    saves=_extract_saves(blob)
    return {"schema":1,"format":"PS1-RAW","bytes":len(blob),
            "saves":saves,"detectedSaveCount":len(saves),
            "gameIntegrityVerified":bool(saves)}


def _write_atomic(path,contents):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.parent/(path.name+"."+uuid4().hex+".tmp")
    try:
        with temp.open("xb") as f:
            f.write(contents)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)


class MemoryCardStore:
    def __init__(self,home):
        self.home=Path(home)
        self.binding_file=self.home/"memory_card_bindings.json"

    def _binding_data(self):
        try:
            data=json.loads(self.binding_file.read_text(encoding="utf-8"))
            return data if isinstance(data,dict) and data.get("schema")==1 else {"schema":1,"links":{}}
        except (OSError,ValueError,TypeError):
            return {"schema":1,"links":{}}

    def has_bindings(self):
        return bool(self._binding_data().get("links"))

    def _load_card(self,path):
        path=Path(path).expanduser().resolve(strict=True)
        if (not path.is_file() or path.is_symlink()
                or path.suffix.lower() not in CARD_EXTENSIONS
                or path.stat().st_size != SIZE):
            raise ValueError("Selecione um cartão PS1 bruto .mcr/.mcd/.srm de 128 KB.")
        before=path.stat()
        with path.open("rb") as stream:
            blob=stream.read(SIZE+1)
        after=path.stat()
        if (before.st_size!=after.st_size or before.st_mtime_ns!=after.st_mtime_ns
                or before.st_ino!=after.st_ino):
            raise ValueError("Memory Card está sendo gravado; leitura será repetida.")
        result=parse_memory_card(blob)
        return path,blob,result

    def select(self,rom_sha256,path):
        if not isinstance(rom_sha256,str) or not ROM_RE.fullmatch(rom_sha256):
            raise ValueError("Ative primeiro uma ISO cadastrada.")
        source,blob,result=self._load_card(path)
        data=self._binding_data()
        data.setdefault("links",{})[rom_sha256]={
            "path":str(source),
            "selectedBlock":result["saves"][0]["block"]
                if len(result["saves"])==1 else None,
        }
        _write_atomic(self.binding_file,
                      (json.dumps(data,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
        self._backup(rom_sha256,blob,result)
        return {"selected":True,"cardName":source.name,
                "detectedSaveCount":result["detectedSaveCount"],
                "status":"Cartão vinculado. Leitura automática habilitada; o ePSXe continua salvando o original."}

    def select_save(self,rom_sha256,block):
        if (not isinstance(rom_sha256,str) or not ROM_RE.fullmatch(rom_sha256)
                or type(block) is not int or not 1 <= block <= 15):
            raise ValueError("Save do Memory Card inválido.")
        data=self._binding_data()
        link=data.get("links",{}).get(rom_sha256)
        if not isinstance(link,dict) or not link.get("path"):
            raise ValueError("Selecione primeiro o Memory Card desta ISO.")
        _path,blob,parsed=self._load_card(link["path"])
        if block not in [save["block"] for save in parsed["saves"]]:
            raise ValueError("Esse save não foi validado no cartão atual.")
        data["links"][rom_sha256]["selectedBlock"]=block
        _write_atomic(self.binding_file,
                      (json.dumps(data,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
        return {"selected":True,"block":block}

    def _backup(self,sha,blob,parsed):
        digest=hashlib.sha256(blob).hexdigest()
        folder=self.home/"memory_card_backups"/sha
        target=folder/(digest+".mcr")
        if not target.is_file():
            folder.mkdir(parents=True,exist_ok=True)
            if target.is_symlink():
                raise ValueError("Caminho de backup inseguro.")
            _write_atomic(target,blob)
        # Decks automáticos são capturados somente para saves estruturais.
        for save in parsed["saves"]:
            deck=save["deckIds"]
            fp=hashlib.sha256(bytes().join(
                int(cid).to_bytes(2,"little") for cid in deck)).hexdigest()
            folder2=self.home/"deck_snapshots"/sha
            dest=folder2/("auto-"+fp+".json")
            if not dest.exists():
                snapshot={"schema":1,"rom_sha256":sha,
                          "id":"auto-"+fp,"name":"Deck automático · bloco "+str(save["block"]),
                          "cards":deck,"source":"memory_card","saveName":save["saveName"],
                          "verifiedInGame":False,
                          "saveIntegrityVerified":True,
                          "duelistCode":save["duelistCode"],
                          "saveSequence":save["saveSequence"],
                          "createdAt":datetime.now(timezone.utc).isoformat()}
                _write_atomic(dest,(json.dumps(snapshot,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
        return digest

    def _saved(self,sha):
        folder=self.home/"deck_snapshots"/sha
        if not folder.is_dir():
            return []
        found=[]
        for path in sorted(folder.glob("*.json"),key=lambda p:p.stat().st_mtime_ns,reverse=True)[:MAX_SAVED]:
            if path.is_symlink() or path.stat().st_size>16000:
                continue
            try:
                payload=json.loads(path.read_text("utf-8"))
            except (OSError,ValueError):
                continue
            if (payload.get("rom_sha256")!=sha
                    or (payload.get("saveIntegrityVerified") is not True
                        and payload.get("liveRamVerified") is not True)
                    or not isinstance(payload.get("cards"),list) or
                    len(payload["cards"])!=CARD_COUNT or
                    not all(type(x) is int and 1<=x<=CARD_LIMIT for x in payload["cards"])):
                continue
            found.append({"id":str(payload.get("id") or "")[:90],
                          "name":str(payload.get("name") or "Deck salvo")[:90],
                          "ids":payload["cards"],
                          "createdAt":str(payload.get("createdAt") or "")[:60],
                          "source":str(payload.get("source") or "local")[:30]})
        return found

    def read(self,rom_sha256):
        if not isinstance(rom_sha256,str) or not ROM_RE.fullmatch(rom_sha256):
            return {"linked":False,"status":"Nenhum mod ativo.","saved":[],
                    "deckIds":[],"saves":[],"selectedBlock":None}
        data=self._binding_data()
        link=(data.get("links") or {}).get(rom_sha256)
        base={"linked":False,
              "status":"Selecione um Memory Card na Biblioteca de Mods.",
              "saved":self._saved(rom_sha256),"deckIds":[],"cardName":None,
              "saveName":None,"saves":[],"selectedBlock":None,
              "gameIntegrityVerified":False,"activeInEmulatorVerified":False}
        if not isinstance(link,dict) or not link.get("path"):
            return base
        try:
            path,blob,result=self._load_card(link["path"])
        except (OSError,ValueError):
            return {**base,"linked":True,
                    "status":"Memory Card indisponível, inválido ou sendo gravado pelo ePSXe."}
        digest=self._backup(rom_sha256,blob,result)
        saves=result["saves"]
        choices=[{"block":row["block"],"saveName":row["saveName"],
                  "duelistCode":row["duelistCode"],
                  "saveSequence":row["saveSequence"]} for row in saves]
        selected=link.get("selectedBlock")
        if not type(selected) is int or selected not in {row["block"] for row in saves}:
            selected=saves[0]["block"] if len(saves)==1 else None
        chosen=next((row for row in saves if row["block"]==selected),None)
        status=(
            "Save válido e íntegro; este é o deck GRAVADO no cartão, não necessariamente o deck ativo no emulador."
            if chosen else
            "Há vários saves; escolha o bloco correto. Nenhum deck é presumido como ativo."
            if saves else
            "Memory Card válido, mas não há save FM com integridade comprovada.")
        return {**base,"linked":True,"cardName":path.name,
                "saves":choices,"selectedBlock":selected,
                "backupFingerprint":digest[:16],
                "saveName":chosen["saveName"] if chosen else None,
                "deckIds":chosen["deckIds"] if chosen else [],
                "saved":self._saved(rom_sha256),
                "gameIntegrityVerified":bool(chosen),
                "status":status}


    def save_live_snapshot(self,sha,name,ids):
        """Save a manually requested snapshot of a verified live RAM deck."""
        if not isinstance(sha,str) or not ROM_RE.fullmatch(sha):
            raise ValueError("ISO ativa inválida.")
        if not isinstance(name,str) or not 1<=len(name.strip())<=72:
            raise ValueError("Nome do deck deve ter 1 a 72 caracteres.")
        if (not isinstance(ids,list) or len(ids)!=40 or
                not all(type(cid) is int and 1<=cid<=CARD_LIMIT for cid in ids)):
            raise ValueError("Deck em RAM inválido.")
        fp=uuid4().hex
        item={"schema":1,"rom_sha256":sha,"id":"manual-"+fp,
              "name":name.strip(),"cards":list(ids),
              "source":"live_ram","liveRamVerified":True,
              "verifiedInGame":True,
              "createdAt":datetime.now(timezone.utc).isoformat()}
        dest=self.home/"deck_snapshots"/sha/("manual-"+fp+".json")
        _write_atomic(dest,(json.dumps(item,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
        return {"saved":True,"name":item["name"],"id":item["id"],
                "status":"Deck ativo salvo no DUELTRACE sem modificar o ePSXe."}

    def save_snapshot(self,sha,name):
        if not isinstance(name,str) or not 1<=len(name.strip())<=72:
            raise ValueError("Nome do deck deve ter 1 a 72 caracteres.")
        current=self.read(sha)
        ids=current.get("deckIds",[])
        if len(ids)!=40:
            raise ValueError("Não há deck de 40 cartas para salvar.")
        fp=uuid4().hex
        item={"schema":1,"rom_sha256":sha,"id":"manual-"+fp,
              "saveIntegrityVerified":bool(current.get("gameIntegrityVerified")),
              "name":name.strip(),"cards":ids,
              "source":"user_snapshot","verifiedInGame":False,
              "createdAt":datetime.now(timezone.utc).isoformat()}
        dest=self.home/"deck_snapshots"/sha/("manual-"+fp+".json")
        _write_atomic(dest,(json.dumps(item,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
        return {"saved":True,"name":item["name"],"id":item["id"],
                "status":"Deck salvo no DUELTRACE sem modificar o Memory Card do ePSXe."}
