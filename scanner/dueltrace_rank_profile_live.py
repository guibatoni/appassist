"""Motor de pontuação reutilizável por mod, independente da fórmula X15.

Duas condições para calcular uma projeção: regras decodificadas dos bytes
da ISO e um mapeamento de contadores+bonificações validado para a MESMA
combinação de hashes ROM/SLUS/tabela. Nenhuma dessas condições é inferida
de nome, skin ou semelhança de mod.
"""
from __future__ import annotations

import re

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_CRITERIA = 32
MAX_STEPS = 12


def x15_compatible_runtime(profile: dict | None) -> bool:
    """Indício estático: SLUS e toda tabela RANK são idênticos ao X15.

    Não autoriza endereços RAM de outro mod nem substitui um binding por SHA
    validado em duelos independentes.
    """
    from fm_rank_tables import (
        KNOWN_X15_SLUS_SHA256, KNOWN_X15_TABLE_SHA256, LEGACY_OFFSET, STRIDE
    )
    if not isinstance(profile,dict):
        return False
    info=profile.get("rank_points")
    if not isinstance(info,dict):
        return False
    return (
        profile.get("exe_sha256")==KNOWN_X15_SLUS_SHA256
        and info.get("table_sha256")==KNOWN_X15_TABLE_SHA256
        and info.get("structure_verified") is True
        and info.get("first_offset")==LEGACY_OFFSET
        and info.get("repeat_stride")==STRIDE
        and info.get("available") is True
    )



def validate_live_rank_binding(profile: dict | None) -> dict | None:
    if not isinstance(profile, dict):
        return None
    ruleset=profile.get("rank_points")
    binding=profile.get("rank_runtime_binding")
    if not isinstance(ruleset,dict) or not isinstance(binding,dict):
        return None
    if ruleset.get("available") is not True:
        return None
    rom=profile.get("rom_sha256")
    exe=profile.get("exe_sha256")
    table=ruleset.get("table_sha256")
    if not all(type(x) is str and SHA256.fullmatch(x.lower())
               for x in (rom,exe,table)):
        return None
    if (binding.get("rom_sha256") != rom
            or binding.get("exe_sha256") != exe
            or binding.get("table_sha256") != table):
        return None
    # Um binding só fica habilitado quando foi conferido com dois duelos
    # registrados independentemente do próprio algoritmo candidato.
    if (binding.get("validation_method") != "independent_duel_trace"
            or type(binding.get("verified_duels")) is not int
            or binding["verified_duels"] < 2):
        return None
    # Host pointer do processo ePSXe (não o endereço MIPS 0x80000000).
    address=binding.get("record_address")
    if type(address) is not int or not 0x10000 <= address <= 0xFFFFFFFF:
        return None
    if type(binding.get("record_length")) is not int or not 28 <= binding["record_length"] <= 256:
        return None
    rules=ruleset.get("rules")
    offsets=binding.get("criterion_offsets")
    if not isinstance(rules,dict) or not isinstance(offsets,dict):
        return None
    if not 1 <= len(rules) <= MAX_CRITERIA or set(offsets)!=set(rules):
        return None
    for name, bands in rules.items():
        if (not isinstance(name,str) or not 1<=len(name)<=64
                or not isinstance(bands,list) or not 1<=len(bands)<=MAX_STEPS):
            return None
        if any(not isinstance(b,dict) or type(b.get("below")) is not int
               or type(b.get("points")) is not int
               or b["below"] < 0 or b["below"] > 32767
               or not -100 <= b["points"] <= 100 for b in bands):
            return None
        if sorted({b["below"] for b in bands}) != [b["below"] for b in bands]:
            return None
    if (binding.get("life_points_criterion") not in offsets or
            binding.get("turns_criterion") not in offsets):
        return None
    for name, offset in offsets.items():
        if (not isinstance(offset,dict)
                or offset.get("type") not in ("u8","u16le")
                or type(offset.get("offset")) is not int):
            return None
        width=1 if offset["type"]=="u8" else 2
        if not 0 <= offset["offset"] <= binding["record_length"]-width:
            return None
    if type(binding.get("base_points")) is not int:
        return None
    if not -1000 <= binding["base_points"] <= 1000:
        return None
    win=binding.get("victory_bonuses")
    if not isinstance(win,dict) or "lp" not in win or any(
        type(p) is not int or not -1000 <= p <= 1000 for p in win.values()
    ):
        return None
    bands=binding.get("rank_bands")
    if not isinstance(bands,list) or not 1 <= len(bands) <= 10:
        return None
    last=1_000_000
    for item in bands:
        if (not isinstance(item,dict)
                or not isinstance(item.get("label"),str)
                or not 1<=len(item["label"])<=32
                or type(item.get("minimum")) is not int
                or item["minimum"] >= last):
            return None
        last=item["minimum"]
    return binding


def read_counters_from_record(raw: bytes, binding: dict) -> dict:
    if not isinstance(raw,bytes) or len(raw)!=binding["record_length"]:
        raise ValueError("Registro de RAM inválido.")
    result={}
    for name,field in binding["criterion_offsets"].items():
        start=field["offset"]
        width=1 if field["type"]=="u8" else 2
        value=int.from_bytes(raw[start:start+width],"little")
        if value > 32766:
            raise ValueError("Contador fora do intervalo seguro.")
        result[name]=value
    return result


def project_rank_for_mod(profile: dict, counters: dict,
                         *, victory: str="lp") -> dict:
    binding=validate_live_rank_binding(profile)
    if binding is None:
        raise ValueError("O mod não possui mapeamento de RANK validado em duelos.")
    if not isinstance(counters,dict) or set(counters)!=set(binding["criterion_offsets"]):
        raise ValueError("Contadores incompletos ou de outra versão do mod.")
    if victory not in binding["victory_bonuses"]:
        raise ValueError("Resultado de vitória não validado.")
    for value in counters.values():
        if type(value) is not int or not 0 <= value <= 32766:
            raise ValueError("Contador inválido.")
    rules=profile["rank_points"]["rules"]
    points={}
    for name, value in counters.items():
        steps=rules[name]
        points[name]=next((b["points"] for b in steps if value<b["below"]),
                          steps[-1]["points"])
    score=binding["base_points"]+binding["victory_bonuses"][victory]+sum(points.values())
    rank=next((r["label"] for r in binding["rank_bands"]
               if score>=r["minimum"]), None)
    if rank is None:
        raise ValueError("Pontuação fora das faixas validadas.")
    return {
        "score":score, "category":rank, "breakdown":points,
        "model":"Modelo por SHA do mod, validado por duelos independentes",
        "final":False,
    }
