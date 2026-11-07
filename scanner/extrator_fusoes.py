"""Leitor de bancos de fusões no WA_MRG.MRG — somente leitura.

Formato documentado no projeto fmscrambler (MIT), arquivo
FMLib/Randomizer/DataScrambler.cs, LoadDataFromWaMrg/WriteChangesToFile:
- 722 ponteiros uint16 (após os dois primeiros bytes do bloco)
- ponteiro 0 significa nenhuma fusão;
- 1 byte de quantidade (<256), ou 0 seguido de 511-byte;
- duas receitas compartilhando 5 bytes; o último par ímpar usa 3 bytes;
- IDs de parceiro e resultado em 10 bits, numerados de 1 a 722.
Existem sete bancos espelhados, mas mods podem divergir entre eles.

Um banco parseável NÃO significa que as fusões foram comprovadas no jogo.
Este módulo NUNCA grava na ROM nem ativa receitas no overlay.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
import json
import struct

from scanner_multiiso import Disc

NUM_CARDS=722
BLOCK_SIZE=0x10000
MIN_INDEX_SIZE=2+2*NUM_CARDS
FUSION_BANK_OFFSETS=(0xB87800,0xBFD000,0xC72800,0xCE8000,
                     0xD5D800,0xDD3000,0xE48800)
MAX_RESULTS=50000


class FusionFormatError(ValueError):
    pass


def decode_bank(block: bytes, *, num_cards: int = NUM_CARDS) -> dict:
    """Decodifica formato histórico com limites e evidências verificáveis."""
    if len(block)!=BLOCK_SIZE:
        raise FusionFormatError("Bloco de fusões incompleto")
    if num_cards<1 or num_cards>722:
        raise FusionFormatError("Quantidade de cartas fora do formato suportado")
    pairs=[]
    pointer_count=0
    for a in range(1,num_cards+1):
        ptr=struct.unpack_from("<H",block,2+(a-1)*2)[0]
        if not ptr:
            continue
        if not MIN_INDEX_SIZE<=ptr<len(block):
            raise FusionFormatError(f"Ponteiro inválido na carta {a}: 0x{ptr:04X}")
        pointer_count+=1
        pos=ptr
        count=block[pos]
        pos+=1
        if count==0:
            if pos>=len(block):
                raise FusionFormatError("Quantidade estendida truncada")
            count=511-block[pos]
            pos+=1
        if count<1 or count>511:
            raise FusionFormatError(f"Quantidade inválida na carta {a}")
        for _ in range((count+1)//2):
            needed=5 if count>1 else 3
            if pos+needed>len(block):
                raise FusionFormatError(f"Receita truncada na carta {a}")
            packed=block[pos]
            b1=((packed&3)<<8)|block[pos+1]
            r1=(((packed>>2)&3)<<8)|block[pos+2]
            if not (1<=b1<=num_cards and 1<=r1<=num_cards):
                raise FusionFormatError(f"IDs de fusão fora do limite na carta {a}")
            pairs.append((a,b1,r1))
            if needed==5:
                b2=(((packed>>4)&3)<<8)|block[pos+3]
                r2=(((packed>>6)&3)<<8)|block[pos+4]
                if not (1<=b2<=num_cards and 1<=r2<=num_cards):
                    raise FusionFormatError(f"IDs da segunda fusão fora do limite na carta {a}")
                pairs.append((a,b2,r2))
            pos+=needed
            count-=2 if needed==5 else 1
            if len(pairs)>MAX_RESULTS:
                raise FusionFormatError("Quantidade suspeita de fusões")
    if pointer_count<20 or len(pairs)<50:
        raise FusionFormatError("Poucas fusões plausíveis para confirmar este formato")
    # Detectar divergência dentro de uma tabela e avisar; não escolher um resultado.
    seen={}
    conflicts=[]
    for a,b,r in pairs:
        for key in ((a,b),(b,a)):
            prev=seen.get(key)
            if prev is not None and prev!=r:
                conflicts.append({"a":key[0],"b":key[1],"results":[prev,r]})
            else:
                seen[key]=r
    pairs_unique=sorted(set(pairs))
    fingerprint=sha256(json.dumps(pairs_unique,separators=(",",":")).encode("ascii")).hexdigest()
    return {
        "pointer_count":pointer_count,
        "recipe_count":len(pairs),
        "unique_recipe_count":len(pairs_unique),
        "recipelist_sha256":fingerprint,
        "conflicts":conflicts[:30],
        "conflict_count":len(conflicts),
        "recipes":[{"a":a,"b":b,"result":r} for a,b,r in pairs_unique],
    }


def select_fusion_resource(disc) -> tuple[str, str]:
    """Keep canonical WA unchanged; accept renamed resources with seven mirrors.

    A few contradictory *pairs* inside seven identical banks must be
    quarantined as pairs, not invalidate the whole resource. Mere
    structural consistency does not prove fusion execution in the mod.
    """
    named = [n for n in disc.files if n.upper().endswith("WA_MRG.MRG")]
    if len(named) == 1:
        return named[0], "canonical_name"
    if len(named) > 1:
        raise FusionFormatError("WA_MRG.MRG ambíguo")
    max_end = max(FUSION_BANK_OFFSETS) + BLOCK_SIZE
    candidates = [
        name for name, entry in disc.files.items()
        if isinstance(name, str) and isinstance(entry, tuple)
        and len(entry) == 2 and type(entry[1]) is int
        and max_end <= entry[1] <= 96 * 1024 * 1024
    ]
    if not candidates:
        raise FusionFormatError("Contêiner de fusões não localizado")
    if len(candidates) > 8:
        raise FusionFormatError("Contêineres demais: limite da sonda")
    strong = []
    for name in sorted(candidates):
        try:
            raw = disc.get(name, limit_bytes=max_end)
            if len(raw) != max_end:
                continue
            hashes = set()
            valid = True
            for off in FUSION_BANK_OFFSETS:
                bank = decode_bank(raw[off:off+BLOCK_SIZE])
                hashes.add(bank["recipelist_sha256"])
                if len(hashes) > 1:
                    valid = False
                    break
            if valid and len(hashes) == 1:
                strong.append(name)
        except (FusionFormatError, ValueError, OSError, KeyError, MemoryError,
                OverflowError, struct.error):
            continue
    if len(strong) != 1:
        raise FusionFormatError(
            "Formato de fusões não identificado unicamente em sete bancos")
    return strong[0], "seven_identical_banks_in_renamed_resource"


def analyze_fusion_banks(rom_path: Path, *, expected_size=None,
                         expected_mtime_ns=None, progress=None,
                         resource_name: str | None = None) -> dict:
    """Varre as 7 cópias de fusões do disco, valida formato e cruza assinaturas."""
    rom=Path(rom_path).resolve(strict=True)
    before=rom.stat()
    if expected_size is not None and before.st_size!=expected_size:
        raise RuntimeError("ISO alterada desde a importação: tamanho diferente")
    if expected_mtime_ns is not None and before.st_mtime_ns!=expected_mtime_ns:
        raise RuntimeError("ISO alterada desde a importação: data diferente")
    disc=None
    reports=[]
    all_recipes={}
    try:
        disc=Disc(rom)
        if resource_name is not None:
            if (not isinstance(resource_name,str)
                    or resource_name not in disc.files
                    or type(disc.files[resource_name][1]) is not int
                    or disc.files[resource_name][1] > 96*1024*1024):
                raise FusionFormatError("Contêiner solicitado não está no índice da ISO")
            wa_name, resource_method = resource_name, "same_iso_structural_family"
        else:
            wa_name, resource_method = select_fusion_resource(disc)
        # Lê prefixo limitado (sem carregar os ~38 MB de WA nem os ~518 MB da ISO).
        max_end=max(FUSION_BANK_OFFSETS)+BLOCK_SIZE
        wa=disc.get(wa_name,limit_bytes=max_end)
        if len(wa)<max_end:
            raise FusionFormatError("WA_MRG.MRG menor que os sete bancos conhecidos")
        for n,off in enumerate(FUSION_BANK_OFFSETS):
            if progress:
                progress("Decodificando banco de fusões",n,len(FUSION_BANK_OFFSETS))
            block=wa[off:off+BLOCK_SIZE]
            row={"bank":n+1,"wa_offset":off,"raw_sha256":sha256(block).hexdigest()}
            try:
                data=decode_bank(block)
                all_recipes[data["recipelist_sha256"]]=data["recipes"]
                row.update({k:v for k,v in data.items() if k!="recipes"})
                row["status"]="decodificado"
            except (ValueError,struct.error) as exc:
                row.update({"status":"incompatível","problem":str(exc)})
            reports.append(row)
    finally:
        if disc is not None:
            disc.close()
    after=rom.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise RuntimeError("ISO modificada durante a leitura: resultados descartados")

    valid=[r for r in reports if r["status"]=="decodificado"]
    counts=Counter(r["recipelist_sha256"] for r in valid)
    winner,mirrors=(counts.most_common(1)[0] if counts else (None,0))
    # Permitir exibir candidato se ao menos um banco for parseável, mas não
    # promover automaticamente a confirmado. Espelhos são evidência adicional.
    selected=(all_recipes[winner] if winner else [])
    conflicting_banks=len(counts)>1
    conflicting_pairs=next((r["conflict_count"] for r in valid
                            if r["recipelist_sha256"]==winner),0)
    # Conflicting A+B/B+A outcomes must not invalidate the evidence that
    # other pairs were decoded. Count *unordered* pairs conservatively:
    # never activate the unambiguous subset automatically.
    outcomes={}
    for row in selected:
        key=(min(int(row["a"]),int(row["b"])),
             max(int(row["a"]),int(row["b"])))
        outcomes.setdefault(key,set()).add(int(row["result"]))
    ambiguous_pairs=sum(len(values)>1 for values in outcomes.values())
    clean_pairs=sum(len(values)==1 for values in outcomes.values())
    return {
        "schema":1,"rom_file":rom.name,
        "resource_selection_method":resource_method,
        "fusion_layout":"WA_MRG 7 bancos de 0x10000, ponteiros uint16, compactação 10-bit",
        "banks":reports,"valid_banks":len(valid),"matching_banks":mirrors,
        "divergent_banks":conflicting_banks,
        "bank_conflicts":conflicting_pairs,
        "candidate_count":len(selected),
        "unique_unordered_pairs_without_conflict":clean_pairs,
        "unordered_pairs_with_conflicting_results":ambiguous_pairs,
        "candidate_fingerprint":winner,
        "status":("candidatas espelhadas, NÃO confirmadas no jogo"
                  if winner and mirrors>=2 and not conflicting_banks and not conflicting_pairs
                  else "candidatas parciais/divergentes — REVISÃO NECESSÁRIA"
                  if winner else "layout não reconhecido — nenhuma fusão extraída"),
        "verified_in_game":False,
        "candidates":selected,
    }


def save_fusion_report(path: Path, report: dict) -> None:
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)
