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
from dueltrace_save_labels import label_saves, safe_mod_name, title_from_ps1_header
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
                      "saveTitle":title_from_ps1_header(data),
                      "deckCount":CARD_COUNT,
                      "status":"save_ps1_integridade_validada_nao_comprovado_ativo",
                      **checked})
    return found

def _list_card_blocks(blob, saves):
    """Report all 15 PHYSICAL PS1 blocks, not just validated FM saves.

    A valid PS1 directory entry is not a valid FM deck. Only a separately
    CRC/seal-verified FM save may be selected. Unknown and corrupt slots
    remain visible so the player understands why the picker has one save.
    """
    valid={row["block"]:row for row in saves}
    slots=[]
    for block in range(1,16):
        directory=blob[block*128:(block+1)*128]
        flag=directory[0] if directory[1:4]==bytes(3) else None
        checksum=_frame_checksum(directory)
        name=directory[10:31].split(bytes(1),1)[0].decode("ascii","replace")
        name="".join(ch for ch in name if 32<=ord(ch)<127)[:21]
        if block in valid:
            status="fm_valid"
            label="Save FM validado"
        elif not checksum and any(directory):
            status="unverified"
            label="Diretório não validado"
        elif flag==0x51:
            status="unverified" if SAVE_NAME_RE.search(name) else "other_game"
            label=("Save FM não validado" if status=="unverified"
                   else "Outro jogo")
        elif flag in (0x52,0x53):
            status="continuation"
            label="Continuação de save"
        elif flag in (0xA0,0xA1,0xA2,0xA3) or not any(directory):
            status="empty"
            label="Livre / não ocupado"
        else:
            status="unverified"
            label="Bloco não identificado"
        slots.append({"block":block,"status":status,
                      "label":label,"selectable":status=="fm_valid",
                      "saveName":name if status=="fm_valid" else None})
    return slots


def parse_memory_card(blob):
    if not isinstance(blob,bytes):
        raise ValueError("Conteúdo do cartão inválido.")
    saves=_extract_saves(blob)
    return {"schema":1,"format":"PS1-RAW","bytes":len(blob),
            "saves":saves,"blocks":_list_card_blocks(blob,saves),
            "detectedSaveCount":len(saves),
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

    @staticmethod
    def _matches_selected_save(link, save):
        """A pin is for one mod and one save, not an ever-changing sequence.

        Older v0.17.2 links stored only the block. Accept their existing
        selection for backward compatibility, then record the game identity
        if the user explicitly selects or reselects the same memory card.
        """
        if not isinstance(link, dict) or not isinstance(save, dict):
            return False
        name=link.get("selectedSaveName")
        duelist=link.get("selectedDuelistCode")
        if name is not None and name != save.get("saveName"):
            return False
        if type(duelist) is int and duelist != save.get("duelistCode"):
            return False
        return True

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

    def select(self,rom_sha256,path,mod_name=None):
        if not isinstance(rom_sha256,str) or not ROM_RE.fullmatch(rom_sha256):
            raise ValueError("Ative primeiro uma ISO cadastrada.")
        source,blob,result=self._load_card(path)
        data=self._binding_data()
        links=data.setdefault("links",{})
        previous=links.get(rom_sha256)
        selected_save=None
        if isinstance(previous,dict):
            previous_block=previous.get("selectedBlock")
            previous_path=previous.get("path")
            # A different Memory Card must never inherit an unrelated slot.
            same_card=previous_path==str(source)
            for row in result["saves"]:
                if (type(previous_block) is int
                        and row["block"]==previous_block
                        and (same_card or (
                            previous.get("selectedSaveName") is not None
                            and previous.get("selectedDuelistCode") is not None))
                        and self._matches_selected_save(previous,row)):
                    selected_save=row
                    break
        if selected_save is None and len(result["saves"])==1:
            # A newly chosen card is an explicit new choice; its sole valid
            # FM save is unambiguous even if the previous card had a pin.
            # Never silently switch slots inside an already linked card.
            if (not isinstance(previous,dict)
                    or previous.get("selectedBlock") is None
                    or previous.get("path") != str(source)):
                selected_save=result["saves"][0]
        keep_missing_pin=(
            selected_save is None
            and isinstance(previous,dict)
            and previous.get("path")==str(source)
            and type(previous.get("selectedBlock")) is int
            and 1 <= previous["selectedBlock"] <= 15)
        links[rom_sha256]={
            "path":str(source),
            "selectedBlock":(
                selected_save["block"] if selected_save else
                previous["selectedBlock"] if keep_missing_pin else None),
            "selectedSaveName":(
                selected_save["saveName"] if selected_save else
                previous.get("selectedSaveName") if keep_missing_pin else None),
            "selectedDuelistCode":(
                selected_save["duelistCode"] if selected_save else
                previous.get("selectedDuelistCode") if keep_missing_pin else None),
            "modName":(safe_mod_name(mod_name)
                       or safe_mod_name(previous.get("modName") if isinstance(previous,dict) else "")),
        }
        _write_atomic(self.binding_file,
                      (json.dumps(data,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
        self._backup(rom_sha256,blob,result)
        return {"selected":True,"cardName":source.name,
                "detectedSaveCount":result["detectedSaveCount"],
                "status":"Cartão vinculado. Leitura automática habilitada; o ePSXe continua salvando o original."}

    def select_save(self,rom_sha256,block,mod_name=None):
        if (not isinstance(rom_sha256,str) or not ROM_RE.fullmatch(rom_sha256)
                or type(block) is not int or not 1 <= block <= 15):
            raise ValueError("Save do Memory Card inválido.")
        data=self._binding_data()
        link=data.get("links",{}).get(rom_sha256)
        if not isinstance(link,dict) or not link.get("path"):
            raise ValueError("Selecione primeiro o Memory Card desta ISO.")
        _path,blob,parsed=self._load_card(link["path"])
        chosen=next((row for row in parsed["saves"]
                     if row["block"]==block),None)
        if chosen is None:
            raise ValueError("Esse save não foi validado no cartão atual.")
        link["selectedBlock"]=block
        link["selectedSaveName"]=chosen["saveName"]
        link["selectedDuelistCode"]=chosen["duelistCode"]
        if safe_mod_name(mod_name):
            link["modName"]=safe_mod_name(mod_name)
        # sequence intentionally NOT pinned: it increments on each game save.
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
        # A full-card backup always includes all 15 slots; deck snapshots do
        # NOT. Older versions incorrectly cloned every save under every ROM.
        # Only the explicitly linked save is eligible for this mod.
        linked=self._binding_data().get("links",{}).get(sha)
        if not isinstance(linked,dict):
            linked={}
        chosen=next((save for save in parsed["saves"]
                     if type(linked.get("selectedBlock")) is int
                     and save["block"]==linked["selectedBlock"]
                     and self._matches_selected_save(linked,save)),None)
        if chosen is not None:
            save=chosen
            deck=save["deckIds"]
            fp=hashlib.sha256(bytes().join(
                int(cid).to_bytes(2,"little") for cid in deck)).hexdigest()
            folder2=self.home/"deck_snapshots"/sha
            # Use slot in the key: older releases wrote auto-<hash>.json
            # for ALL saves under any mod. Preserve them as backups, but do
            # not let their filenames suppress correctly linked snapshots.
            snapshot_id="auto-"+str(save["block"])+"-"+fp
            dest=folder2/(snapshot_id+".json")
            if not dest.exists():
                mod=safe_mod_name(linked.get("modName")) or "mod vinculado"
                snapshot={"schema":1,"rom_sha256":sha,
                          "id":snapshot_id,
                          "name":("Deck · Bloco "+str(save["block"])+" · "+mod)[:90],
                          "cards":deck,"source":"memory_card","saveName":save["saveName"],
                          "saveBlock":save["block"],
                          "verifiedInGame":False,
                          "saveIntegrityVerified":True,
                          "duelistCode":save["duelistCode"],
                          "saveSequence":save["saveSequence"],
                          "createdAt":datetime.now(timezone.utc).isoformat()}
                _write_atomic(dest,(json.dumps(snapshot,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
        return digest

    def _saved(self,sha):
        folder=self.home/"deck_snapshots"/sha
        link=(self._binding_data().get("links") or {}).get(sha) or {}
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
                    or (payload.get("source")=="memory_card"
                        and (type(payload.get("saveBlock")) is not int
                             or payload.get("saveBlock")!=link.get("selectedBlock")
                             or not self._matches_selected_save(
                                 link, {"saveName":payload.get("saveName"),
                                        "duelistCode":payload.get("duelistCode")})))
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

    def read(self,rom_sha256,mod_name=None):
        if not isinstance(rom_sha256,str) or not ROM_RE.fullmatch(rom_sha256):
            return {"linked":False,"status":"Nenhum mod ativo.","saved":[],
                    "deckIds":[],"saves":[],"blocks":[],"selectedBlock":None}
        data=self._binding_data()
        link=(data.get("links") or {}).get(rom_sha256)
        base={"linked":False,
              "status":"Selecione um Memory Card na Biblioteca de Mods.",
              "saved":self._saved(rom_sha256),"deckIds":[],"cardName":None,
              "saveName":None,"saves":[],"blocks":[],"selectedBlock":None,
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
        choices=label_saves(
            saves, data.get("links",{}), current_sha=rom_sha256,
            memory_path=str(path),
            mod_name=safe_mod_name(mod_name) or link.get("modName"))
        selected=link.get("selectedBlock")
        pinned=type(selected) is int and 1<=selected<=15
        chosen=next((row for row in saves
                     if pinned and row["block"]==selected
                     and self._matches_selected_save(link,row)),None)
        if not pinned and len(saves)==1:
            # Single-save cards can be displayed without inventing a pin.
            chosen=saves[0]
            selected=chosen["block"]
        if pinned and chosen is None:
            status=(
                f"O save fixado no Bloco {selected} não está disponível ou "
                "não corresponde à partida escolhida. Não foi trocado por outro save.")
        elif chosen:
            status=(
                "Save válido e íntegro; este é o deck GRAVADO no cartão, "
                "não necessariamente o deck ativo no emulador.")
        elif saves:
            status="Há vários saves; escolha o correto. Nenhum deck é presumido como ativo."
        else:
            status="Memory Card válido, mas não há save FM com integridade comprovada."
        chosen_label=next((row for row in choices
                          if chosen and row["block"]==chosen["block"]),None)
        return {**base,"linked":True,"cardName":path.name,
                "saves":choices,
                "blocks":result["blocks"],
                "saveDisplayName":(chosen_label or {}).get("displayName"),
                "activeModName":(safe_mod_name(mod_name)
                                 or safe_mod_name(link.get("modName"))),
                "selectedBlock":selected if chosen else None,
                "savePinned":pinned and chosen is not None,
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
