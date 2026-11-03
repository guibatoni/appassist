"""Controles negativos e monitor de endereços do campo: apenas hipóteses, leitura.

Os pontos monitorados são IDs/flags *não validados* observados em estudos
anteriores. Não são um mapa de slots; não permitem concluir ocupação.
Nunca armazena dump bruto, apenas valores pontuais e contagens resumidas.
"""
from __future__ import annotations

CHUNK_SIZE = 4096
HAND_START = 0xBFF484
HAND_END = HAND_START + 140
# Um único bloco adicional é lido quando o escopo normal é 96 KiB.
FOCUS_CHUNK = 0xC39000
FOCUS_FROM = 0xC39000
FOCUS_TO = 0xC39400  # 1 KiB, dentro de um único bloco de 4 KiB.
FOCUS_MAX_CHANGES = 64
SLOT_ID_START = 0xBFF510
SLOT_ID_STRIDE = 28
SLOT_COUNT = 5

# Endereços encontrados em três relatórios, não confirmados como campo.
WATCH_ADDRESSES = (
    0xBFF6B3,     # alterado desde PREPARADA: possível flag de seleção
    0xC38F80, 0xC3911E, 0xC392DF,       # slot 1, carta #547
    0xC39234, 0xC39265, 0xC39277,
    0xC392B8, 0xC392B9, 0xC3939C,
    0xC393A3,                           # slot 2, carta #291
    0xC3920C, 0xC39353, 0xC39374,
    0xC393D0, 0xC393D1,                # slot 1, carta #291
)
assert len(set(WATCH_ADDRESSES)) == len(WATCH_ADDRESSES)
assert all(not HAND_START <= address < HAND_END for address in WATCH_ADDRESSES)


def _get_byte(chunks: dict[int, bytes], address: int) -> int | None:
    chunk = chunks.get(address & ~(CHUNK_SIZE - 1))
    off = address % CHUNK_SIZE
    if not isinstance(chunk, bytes) or len(chunk) != CHUNK_SIZE:
        return None
    return chunk[off]


def focus_watch_values(chunks: dict[int, bytes]) -> list[dict]:
    """Valores pontuais em endereços de análise, nunca bytes brutos em bloco."""
    return [
        {"address":f"0x{address:08X}", "u8":_get_byte(chunks,address),
         "field_address_verified":False}
        for address in WATCH_ADDRESSES
    ]


def focus_slot_u16_values(chunks: dict[int,bytes]) -> list[dict]:
    """Cinco registros de 28 B de hipótese, com leitura segura de uint16 LE."""
    rows = []
    for i in range(SLOT_COUNT):
        addr = SLOT_ID_START + i * SLOT_ID_STRIDE
        lo,hi = _get_byte(chunks,addr),_get_byte(chunks,addr+1)
        number = lo+(hi<<8) if lo is not None and hi is not None else None
        rows.append({
            "hypothetical_slot":i+1,"address":f"0x{addr:08X}",
            "u16_le":number,"field_slot_verified":False,
            "does_not_prove_occupancy":True,
        })
    return rows


def focus_phase_differences(before: dict[int,bytes],
                            after: dict[int,bytes]) -> dict:
    """Diferenças numa faixa candidata de 1 KiB; não exporta dumps."""
    changes = []
    comparable=0
    for addr in range(FOCUS_FROM, FOCUS_TO):
        a,b=_get_byte(before,addr),_get_byte(after,addr)
        if a is None or b is None:
            continue
        comparable+=1
        if a!=b:
            changes.append({"address":f"0x{addr:08X}","before_u8":a,"after_u8":b})
    return {
        "range_start":f"0x{FOCUS_FROM:08X}",
        "range_end_exclusive":f"0x{FOCUS_TO:08X}",
        "compared_bytes":comparable,
        "changed_bytes":len(changes),
        "sample":changes[:FOCUS_MAX_CHANGES],
        "sample_truncated":len(changes)>FOCUS_MAX_CHANGES,
        "field_address_verified":False,
    }


def cancelled_preparation_analysis(before: dict[int,bytes],
                                   prepared: dict[int,bytes],
                                   cancelled: dict[int,bytes]) -> dict:
    """O mesmo byte em três instantes: antes, preparado e depois de cancelar.

    Categorias apenas observacionais, não sinalizam que um slot foi limpo.
    A mão já conhecida fica excluída e nenhum byte bruto é persistido.
    """
    counts={
        "prepared_changes":0,
        "restored_after_cancel":0,
        "persisted_after_cancel":0,
        "different_after_cancel":0,
        "changed_only_on_cancel":0,
        "comparable_bytes":0,
        "skipped_unreadable_chunks":0,
    }
    watched=[]
    for addr in sorted(set(before)|set(prepared)|set(cancelled)):
        b,p,c=before.get(addr),prepared.get(addr),cancelled.get(addr)
        if any(not isinstance(v,bytes) or len(v)!=CHUNK_SIZE for v in (b,p,c)):
            counts["skipped_unreadable_chunks"]+=1
            continue
        for i in range(CHUNK_SIZE):
            pos=addr+i
            if HAND_START <= pos < HAND_END: continue
            counts["comparable_bytes"]+=1
            first,second,last=b[i],p[i],c[i]
            if first != second:
                counts["prepared_changes"]+=1
                if first == last:
                    counts["restored_after_cancel"]+=1
                    kind="RESTAURADO"
                elif second == last:
                    counts["persisted_after_cancel"]+=1
                    kind="PERSISTIU"
                else:
                    counts["different_after_cancel"]+=1
                    kind="OUTRO"
            elif last != first:
                counts["changed_only_on_cancel"]+=1
                kind="SOMENTE_CANCELAMENTO"
            else:
                continue
            if pos in WATCH_ADDRESSES or SLOT_ID_START <= pos < SLOT_ID_START+(SLOT_COUNT-1)*SLOT_ID_STRIDE+2:
                watched.append({"address":f"0x{pos:08X}",
                                "before_u8":first,"prepared_u8":second,
                                "cancelled_u8":last,"category":kind,
                                "field_address_verified":False})
    return {
        **counts,
        "watched_changes":watched[:100],
        "watched_changes_truncated":len(watched)>100,
        "focus_before_to_prepared":focus_phase_differences(before,prepared),
        "focus_prepared_to_cancelled":focus_phase_differences(prepared,cancelled),
        "focus_before_to_cancelled":focus_phase_differences(before,cancelled),
        "field_slot_verified":False,
        "occupancy_verified":False,
        "notes":[
            "Uma selecao cancelada nao pode ser interpretada como invocacao.",
            "A confirmacao de cancelamento e declarada visualmente pelo jogador.",
            "Estados intermediarios, interfaces e outras acoes podem alterar bytes.",
            "Nenhum bloco bruto, ROM, save ou escrita na RAM e incluido.",
        ],
    }
