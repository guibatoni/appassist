"""Identificação determinística e somente leitura da geometria de ISO/BIN PS1.

O nome ou extensão do arquivo não determina a geometria. Somente um PVD
ISO-9660 na posição esperada e um layout físico coerente permitem abrir disco.
Suporta dados de 2048 bytes, RAW CDDA 2352 (Mode 1 / Mode 2 Form 1),
Mode 2 sem sync (2336), e BIN 2448 com subchannel de 96 bytes.

Este módulo não deduz estrutura de cartas, fusões ou drops nem altera a ROM.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO

LOGICAL_SECTOR_SIZE = 2048
PRIMARY_VOLUME_DESCRIPTOR_LBA = 16
PVD_MAGIC = b"\x01CD001\x01"
SUPPORTED_LAYOUTS = (
    (2048, 0, "iso2048"),
    (2352, 24, "raw2352_mode2_form1"),
    (2352, 16, "raw2352_mode1"),
    (2336, 8, "mode2_2336_form1"),
    (2448, 24, "raw2448_mode2_form1_subchannel"),
    (2448, 16, "raw2448_mode1_subchannel"),
)

@dataclass(frozen=True)
class DiscGeometry:
    sector: int
    offset: int
    format: str


def detect_disc_geometry(file: BinaryIO, size: int) -> DiscGeometry:
    """Detecta ISO9660 por conteúdo e não pelo sufixo .iso/.bin.

    Não assume o primeiro múltiplo de setor: 2048 e 2352 podem dividir
    um mesmo tamanho e o formato errado gera arquivos fantasmas.
    """
    if type(size) is not int or size < 17 * LOGICAL_SECTOR_SIZE:
        raise ValueError("Imagem muito pequena para conter o índice ISO9660.")
    try:
        pos = file.tell()
    except (OSError, ValueError):
        pos = None
    candidates = []
    try:
        for sector, offset, name in SUPPORTED_LAYOUTS:
            if size % sector != 0 or offset + LOGICAL_SECTOR_SIZE > sector:
                continue
            start = PRIMARY_VOLUME_DESCRIPTOR_LBA * sector + offset
            if start + LOGICAL_SECTOR_SIZE > size:
                continue
            file.seek(start)
            pvd = file.read(LOGICAL_SECTOR_SIZE)
            if len(pvd) != LOGICAL_SECTOR_SIZE or pvd[:7] != PVD_MAGIC:
                continue
            # Um cabeçalho ISO9660 válido deve trazer um registro raiz
            # minimamente coerente. Não aceitar bytes "CD001" isolados.
            record_size = pvd[156]
            if record_size < 34 or 156 + record_size > LOGICAL_SECTOR_SIZE:
                continue
            root = pvd[156:156 + record_size]
            if root[25] & 2 == 0 or root[32] != 1 or root[33] != 0:
                continue
            candidates.append(DiscGeometry(sector, offset, name))
    finally:
        if pos is not None:
            file.seek(pos)
    if not candidates:
        raise ValueError(
            "Imagem sem diretório ISO9660 válido nas geometrias suportadas "
            "(2048, RAW 2352, Mode2 2336 ou RAW 2448 bytes por setor). "
            "Não foi possível identificar a imagem com segurança."
        )
    # Um cabeçalho válido em dois formatos físicos seria ambíguo. Nunca
    # arbitrar baseado no nome do arquivo.
    if len(candidates) != 1:
        raise ValueError("Geometria ISO9660 ambígua; leitura suspensa.")
    return candidates[0]
