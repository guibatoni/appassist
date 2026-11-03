"""Fluxo automático e seguro de reconhecimento MultiMod.

O usuário escolhe uma ISO/BIN ou uma pasta. O motor aproveita o cache por
arquivo/hash e devolve evidências reais; não afirma compatibilidade universal,
não infere efeitos/fusões e não inicia executáveis nem escreve na imagem.
"""
from __future__ import annotations

from pathlib import Path
from collections import Counter

from auto_mods import EXTENSIONS, ModCatalog
from card_catalog import CARD_CATEGORIES, category_summary

MAX_DISC_IMAGES = 128


def discover_images(folder: Path, *, recursive: bool = False) -> list[Path]:
    folder = Path(folder).expanduser()
    if not folder.is_dir():
        raise NotADirectoryError(f"Pasta indisponível: {folder}")
    iterator = folder.rglob("*") if recursive else folder.iterdir()
    found = []
    for p in iterator:
        if not p.is_file() or p.is_symlink() or p.suffix.lower() not in EXTENSIONS:
            continue
        found.append(p)
        if len(found) > MAX_DISC_IMAGES:
            raise ValueError("Pasta com muitas imagens; escolha uma subpasta com até 128 ISO/BIN")
    return sorted(found, key=lambda p: p.name.casefold())


def profile_summary(entry: dict, profile: dict | None) -> dict:
    """Nunca mostrar quantidade ou compatibilidade não extraída."""
    if not profile:
        return {
            "sha256":entry.get("sha256"), "file_name":entry.get("file_name"),
            "name":entry.get("file_name"),"status":"PERFIL_INDISPONIVEL",
            "categories":{}, "effect_count":0, "fusion_count":0,
            "cards_total":0,"requires_review":True,
        }
    verified=profile.get("verified",{})
    features=profile.get("supported_features",{})
    cards=profile.get("cards",[]) if features.get("cards") else []
    counts=category_summary(cards) if cards else {}
    effects=sum(bool(c.get("effect_text") and c.get("effect_source")) for c in cards)
    recipes=profile.get("fusion_recipes",[]) if features.get("fusions") else []
    status=entry.get("level","desconhecido")
    return {
        "sha256":entry.get("sha256"),
        "file_name":entry.get("file_name"),
        "name":profile.get("name") or entry.get("file_name"),
        "status":status,
        "cards_total":len(cards),
        "categories":counts,
        "effect_count":effects,
        "effect_source":(profile.get("effects_provenance") or {}).get("status","nao_identificado"),
        "fusion_count":len(recipes),
        "requires_review":status!="conhecido_validado",
        "validated":{k:verified.get(k) for k in
                     ("cartas","oponentes","tabelas_drops","fusoes","efeitos")},
        "iso_verified_in_emulator":False,
    }


class ModAutopilot:
    def __init__(self, catalog: ModCatalog):
        self.catalog=catalog

    def analyze_file(self, image: Path, progress=None, *, with_art=False) -> dict:
        """Determinístico e local; artes locais opcionais quando o parser suportar."""
        if with_art:
            entry=self.catalog.analyse(image, with_art=True, progress=progress)
        else:
            entry=self.catalog.analyse(image, progress=progress)
        return profile_summary(entry,self.catalog.profile_for(entry))

    def analyze_folder(self, folder: Path, callback=None, *, recursive=False) -> list[dict]:
        images=discover_images(folder,recursive=recursive)
        results=[]
        for i,p in enumerate(images,1):
            if callback:callback({"event":"found","file":p.name,"index":i,"total":len(images)})
            try:
                result=self.analyze_file(
                    p, progress=(lambda stage,done,total:
                                 callback({"event":"progress","file":p.name,"stage":stage,
                                           "done":done,"total":total})
                                 if callback else None))
                results.append(result)
                if callback:callback({"event":"done","file":p.name,"result":result})
            except (OSError,ValueError,RuntimeError) as e:
                result={"file_name":p.name,"status":"ERRO",
                        "error":str(e)[:250],"requires_review":True}
                results.append(result)
                if callback:callback({"event":"error","file":p.name,"message":result["error"]})
        if callback:callback({"event":"finished","total":len(images)})
        return results
