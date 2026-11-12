"""Integrity verifier for the original Forbidden Memories 0x680-byte save.

Based on the game's independent three CRC-16/XMODEM seeded masks in the
decompilation. This module reads but never writes PlayStation save files.
The first or secondary duplicate must pass all 3 seals before a deck is read.
"""
from __future__ import annotations

import struct

STATE_SIZE = 0x680
STATE_OFFSET = 0x200
DUPLICATE_OFFSET = 0x880
MAX_CARD = 722
TABLES = (
    (0x000, 0x340, 0x378, 15, 0x37C),
    (0x380, 0x06C, 0x3F8, 4, 0x3FC),
    (0x400, 0x204, 0x624, 8, 0x604),
)


def crc_xmodem(data: bytes) -> int:
    checksum = 0
    for byte in data:
        checksum ^= byte << 8
        for _ in range(8):
            checksum = (((checksum << 1) ^ 0x1021)
                        if checksum & 0x8000 else (checksum << 1)) & 0xFFFF
    return checksum


def _mask_words(seed: int, count: int):
    low = high = seed | (seed << 16)
    for _ in range(count):
        word = ((high << 31) | (low >> 1)) & 0xFFFFFFFF
        word = (word ^ ((low << 12) & 0xFFFFFFFF)) & 0xFFFFFFFF
        high = (high + high + (low & 1)) & 0xFFFFFFFF
        low = (word ^ (word >> 20)) & 0xFFFFFFFF
        yield low


def valid_state(block: bytes) -> bool:
    if not isinstance(block, bytes) or len(block) != STATE_SIZE:
        return False
    if not any(block[:80]):
        return False
    for start, length, mask_at, count, crc_at in TABLES:
        crc = crc_xmodem(block[start:start+length])
        if (struct.unpack_from("<HH", block, crc_at) != (crc, crc)):
            return False
        for i, expected in enumerate(_mask_words(crc, count)):
            if struct.unpack_from("<I", block, mask_at - 4*i)[0] != expected:
                return False
    return True


def valid_deck(block: bytes) -> list[int] | None:
    if not valid_state(block):
        return None
    cards = list(struct.unpack_from("<40H", block, 0))
    if not all(1 <= card <= MAX_CARD for card in cards):
        return None
    return cards


def decode_save_block(data: bytes) -> dict | None:
    if len(data) < DUPLICATE_OFFSET + STATE_SIZE or data[:2] != b"SC":
        return None
    first = data[STATE_OFFSET:STATE_OFFSET + STATE_SIZE]
    second = data[DUPLICATE_OFFSET:DUPLICATE_OFFSET + STATE_SIZE]
    for location, block in (("primary", first), ("duplicate", second)):
        deck = valid_deck(block)
        if deck is not None:
            duelist = struct.unpack_from("<i", block, 0x334)[0]
            sequence = struct.unpack_from("<I", block, 0x404)[0]
            return {"deckIds":deck, "duelistCode":duelist,
                    "saveSequence":sequence,
                    "integrityCopy":location,
                    "gameIntegrityVerified":True}
    return None
