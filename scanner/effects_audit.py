"""Auditoria segura de fontes de efeitos da imagem PS1.

Procura contêineres e trechos textuais candidatos. Não converte texto
isolado em efeito de carta: para isso são necessários IDs e offsets mapeados
no mod, ou documento estruturado vinculado à assinatura da ISO.
"""
from __future__ import annotations

import hashlib
import re
import struct
import unicodedata
from pathlib import Path

from scanner_multiiso import Disc, SLUS_PTR_BASE, SLUS_TEXT_BASE, SLUS_GLYPHS

SIGNALS=("EFFECT","CARD","SPELL","MAGIC","SCRIPT","MECHANIC","DESCRI",
         "HINT","GUIDE","RULE","ABILIT","DECK","MONSTER")
TOKENS=re.compile(rb"\b(?:attack|defense|destroy|restore|tribute|summon|equip|effect|"
                  rb"graveyard|field|damage|increase|decrease|defesa|ataque|"
                  rb"efeito|invocar|cemiterio|destruir|dano)\b",re.I)
RUNS=re.compile(rb"[\x20-\x7e]{20,240}")
MAX_FILES=100
MAX_SAMPLE_BYTES=2_200_000
MAX_STRINGS=12



TEXT_TOKENS=re.compile(r"\b(?:attack|defense|destroy|summon|effect|equip|"
                       r"graveyard|damage|field|increase|decrease|"
                       r"ataque|defesa|efeito|equipamento|invocar|cemitério|dano)\b",re.I)


def find_fm_text_candidates(executable: bytes, *, max_index: int = 2200) -> list[dict]:
    """Amostra textos na codificação de glifos de FM; índice NÃO é ID de carta."""
    if len(executable) < SLUS_GLYPHS + 93*4:
        return []
    try:
        glyphs=[struct.unpack_from("<H",executable,SLUS_GLYPHS+4*i)[0]
                for i in range(93)]
    except struct.error:
        return []
    results=[]
    for index in range(723,max_index):
        if SLUS_PTR_BASE+index*2+2>len(executable):
            break
        pointer=struct.unpack_from("<H",executable,SLUS_PTR_BASE+2*index)[0]
        pos=SLUS_TEXT_BASE+pointer
        if pos<0 or pos>=len(executable):
            continue
        if executable[pos:pos+2]==b"\xf8\x0a":
            pos+=3
        raw=executable[pos:pos+220]
        end=raw.find(b"\xff")
        if end < 12 or end > 215:
            continue
        decoded=[]
        invalid=0
        for byte in raw[:end]:
            if byte==0:
                decoded.append(" ")
            elif byte<len(glyphs) and glyphs[byte]:
                try:
                    decoded.append(glyphs[byte].to_bytes(2,"big").decode("shift_jis"))
                except UnicodeError:
                    invalid+=1
            else:
                invalid+=1
        if invalid>2 or not decoded:
            continue
        label=unicodedata.normalize("NFKC","".join(decoded)).strip()
        if not 14<=len(label)<=180 or not TEXT_TOKENS.search(label):
            continue
        results.append({
            "text_pointer_index":index,
            "executable_offset":pos,
            "text_preview":label[:160],
            "verified_card_id":None,
        })
        if len(results)>=24:
            break
    return results


def audit_effect_sources(image: Path, *, rom_sha256: str) -> dict:
    """Leituras limitadas de metadados sem atribuir semântica inexistente."""
    disc=Disc(Path(image))
    try:
        candidates=[]
        for name,(lba,size) in sorted(disc.files.items()):
            name_upper=name.upper()
            if any(token in name_upper for token in SIGNALS):
                candidates.append({"name":name[:120],"size":size})
        # Textos candidatos só em contêineres/executáveis potencialmente úteis.
        selected=[name for name in disc.files
                  if name.upper().startswith(("SLUS_","SLES_","SLPS_","SLPM_"))
                  or name.upper().endswith("WA_MRG.MRG")]
        samples=[]
        glyph_candidates=[]
        for name in selected[:3]:
            raw=disc.get(name,limit_bytes=MAX_SAMPLE_BYTES)
            if name.upper().startswith(("SLUS_","SLES_","SLPS_","SLPM_")):
                glyph_candidates.extend(find_fm_text_candidates(raw))
            for match in RUNS.finditer(raw):
                value=match.group()
                if TOKENS.search(value) and len(samples)<MAX_STRINGS:
                    samples.append({
                        "source":name[:120],
                        "offset":match.start(),
                        "text_preview":value[:180].decode("ascii","replace"),
                        "verified_card_id":None,
                    })
            if len(samples)>=MAX_STRINGS:
                break
        return {
            "schema":1,"rom_sha256":rom_sha256,"image_name":Path(image).name,
            "candidate_files":candidates[:MAX_FILES],
            "candidate_text_runs":samples,
            "candidate_fm_text_records":glyph_candidates[:24],
            "card_effects_mapped":0,
            "status":"fontes_identificadas_sem_mapeamento"
                     if candidates or samples or glyph_candidates else "sem_textos_estruturados_identificados",
            "confidence":"investigacao_apenas",
            "notice":(
                "Nomes e trechos são pistas de engenharia reversa. Nenhum efeito "
                "foi atribuído automaticamente a cartas sem ID, offset ou "
                "descrição estruturada com origem comprovada."
            ),
        }
    finally:
        disc.close()
