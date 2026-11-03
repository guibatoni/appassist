"""Auditoria segura de fontes de efeitos da imagem PS1.

Procura contêineres e trechos textuais candidatos. Não converte texto
isolado em efeito de carta: para isso são necessários IDs e offsets mapeados
no mod, ou documento estruturado vinculado à assinatura da ISO.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from scanner_multiiso import Disc

SIGNALS=("EFFECT","CARD","SPELL","MAGIC","SCRIPT","MECHANIC","DESCRI",
         "HINT","GUIDE","RULE","ABILIT","DECK","MONSTER")
TOKENS=re.compile(rb"\b(?:attack|defense|destroy|restore|tribute|summon|equip|effect|"
                  rb"graveyard|field|damage|increase|decrease|defesa|ataque|"
                  rb"efeito|invocar|cemit[eé]rio|destr[uó]i|dano)\b",re.I)
RUNS=re.compile(rb"[\x20-\x7e]{20,240}")
MAX_FILES=100
MAX_SAMPLE_BYTES=1_800_000
MAX_STRINGS=12


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
        for name in selected[:3]:
            raw=disc.get(name,limit_bytes=MAX_SAMPLE_BYTES)
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
            "card_effects_mapped":0,
            "status":"fontes_identificadas_sem_mapeamento"
                     if candidates or samples else "sem_textos_estruturados_identificados",
            "confidence":"investigacao_apenas",
            "notice":(
                "Nomes e trechos são pistas de engenharia reversa. Nenhum efeito "
                "foi atribuído automaticamente a cartas sem ID, offset ou "
                "descrição estruturada com origem comprovada."
            ),
        }
    finally:
        disc.close()
