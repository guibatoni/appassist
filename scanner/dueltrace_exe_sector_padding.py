"""Recover only verified zero padding in a PS-X EXE's final ISO sector.

Some PS1 mods declare a PS-X EXE payload ending at a sector boundary while
their ISO9660 directory entry omits trailing zeros. Those zeros still exist
inside the file's last, already allocated, physical sector. Never synthesize
missing executable bytes, read another file's extent, or loosen RAM checks.
"""
from __future__ import annotations

import struct

from dueltrace_layout_discovery import inspect_psx_executable_header

MAX_EXE_BYTES = 8 * 1024 * 1024
SECTOR_BYTES = 2048
MAX_PADDING = SECTOR_BYTES - 1


def load_executable_sector_padding(disc, name: str) -> tuple[bytes, dict]:
    original = disc.get(name)
    report = {"schema": 1, "state": "nao_necessario",
              "paddingBytes": 0, "headerCoherent": False,
              "validated": False}
    if (not isinstance(original, bytes) or not
            SECTOR_BYTES <= len(original) <= MAX_EXE_BYTES
            or not original.startswith(b"PS-X EXE")):
        return original, report
    raw_size = len(original)
    payload_size = struct.unpack_from("<I", original, 0x1C)[0]
    expected = SECTOR_BYTES + payload_size
    current = inspect_psx_executable_header(
        original[:SECTOR_BYTES], raw_size)
    if current.get("headerCoherent"):
        report["headerCoherent"] = True
        return original, report
    difference = expected - raw_size
    allocation = ((raw_size + SECTOR_BYTES - 1) // SECTOR_BYTES) * SECTOR_BYTES
    if (payload_size == 0 or payload_size % 4
            or not 1 <= difference <= MAX_PADDING
            or expected > allocation or expected > MAX_EXE_BYTES):
        report["state"] = "declaracao_incompativel"
        return original, report
    source = disc.files.get(name.upper())
    if not isinstance(source, tuple) or len(source) != 2:
        report["state"] = "extent_ausente"
        return original, report
    start_lba, directory_size = source
    if (type(start_lba) is not int or start_lba < 0
            or directory_size != raw_size):
        report["state"] = "extent_invalido"
        return original, report
    end_lba = start_lba + allocation // SECTOR_BYTES
    # No other ISO directory entry may share a physical sector with the
    # executable. Disallow extending through an overlapping extent.
    for other, entry in disc.files.items():
        if other == name.upper():
            continue
        if not isinstance(entry, tuple) or len(entry) != 2:
            report["state"] = "extent_ambiguo"
            return original, report
        other_lba, other_size = entry
        if (type(other_lba) is not int or type(other_size) is not int
                or other_lba < 0 or other_size < 0):
            report["state"] = "extent_ambiguo"
            return original, report
        other_end = other_lba + (other_size + SECTOR_BYTES - 1) // SECTOR_BYTES
        if other_lba < end_lba and other_end > start_lba:
            report["state"] = "extents_sobrepostos"
            return original, report
    try:
        full = disc.read(start_lba, allocation)
    except (OSError, ValueError, AttributeError):
        report["state"] = "setor_indisponivel"
        return original, report
    if (len(full) != allocation or full[:raw_size] != original
            or any(full[raw_size:expected])):
        report["state"] = "padding_nao_nulo_ou_incoerente"
        return original, report
    complete = full[:expected]
    header = inspect_psx_executable_header(
        complete[:SECTOR_BYTES], len(complete))
    if not header.get("headerCoherent"):
        report["state"] = "mapeamento_psx_invalido"
        return original, report
    report.update(state="padding_zero_verificado", paddingBytes=difference,
                  headerCoherent=True)
    return complete, report
