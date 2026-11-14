"""Classificações de duelo versus bancos de drop de Forbidden Memories.

O jogo original possui DEZ classificações de resultado e apenas TRÊS
tabelas de drops por oponente. A ordem física dos bancos em WA_MRG.MRG:
    +0x05B4 S/A POW
    +0x0B68 B/C/D POW/TEC
    +0x111C S/A TEC
Estes offsets são relativos ao registro de cada oponente; não alteramos
pesos/IDs extraídos. Para mods não identificados, é o layout ORIGINAL
presumido, nunca execução do algoritmo do SLUS verificada.

A ISO Remaster X15 conhecida por SHA possui 3 RANKs próprios. Não
misturar seus limites/pools com os dez rankings do original.
"""
from __future__ import annotations

from scanner_multiiso import X15_SHA, X15_RANK_LABEL_ONLY_SHA

X15_RANKS = ("Z-POW", "S-POW", "S-TEC")
X15_RANK_TABLE_SHA256 = "dffacc55349f6b565d9e9a70db20ce9fe5f5ef5702a5bcc7c35926b764af28e0"
X15_RANK_TABLE_FIRST_OFFSET = 7475 * 2048 + 0x16D0
X15_RANK_TABLE_STRIDE = 3 * 2048
CLASSIC_RANKS = (
    "S-POW", "A-POW", "B-POW", "C-POW", "D-POW",
    "D-TEC", "C-TEC", "B-TEC", "A-TEC", "S-TEC",
)
CLASSIC_POOLS = ("S/A POW", "B/C/D POW/TEC", "S/A TEC")
X15_POOLS = X15_RANKS

# Only dropdown choices, not the ten real duel ranks. Original WA_MRG
# stores S/A POW together (pool 0), all B/C/D POW/TEC in pool 1, and
# S/A TEC together (pool 2). No new tables or probabilities are created.
CLASSIC_DROP_FILTERS = (
    "SA-POW", "BCD-POW", "BCD-TEC", "SA-TEC",
)

CLASSIC_POOL_RANKS = (
    ("S-POW","A-POW"),
    ("B-POW","C-POW","D-POW","D-TEC","C-TEC","B-TEC"),
    ("A-TEC","S-TEC"),
)
X15_POOL_RANKS = (("Z-POW",),("S-POW",),("S-TEC",))

# Valores do sistema original, APENAS para pontuações comprovadas por mod.
# Não transformar automaticamente leitura da tabela WA em RANK ao vivo.
CLASSIC_SCORE_RANKS = (
    (90,"S-POW"),(80,"A-POW"),(70,"B-POW"),(60,"C-POW"),
    (50,"D-POW"),(40,"D-TEC"),(30,"C-TEC"),(20,"B-TEC"),
    (10,"A-TEC"),(0,"S-TEC"),
)


def is_x15_sha(sha: str | None) -> bool:
    """True apenas para a imagem exata cujo modelo X15 foi validado."""
    return type(sha) is str and sha.casefold() == X15_SHA.casefold()


def is_x15_rank_label_sha(sha: str | None) -> bool:
    """Identifica ISOs que usam a nomenclatura de três RANKs X15."""
    return (type(sha) is str and sha.casefold() in {
        X15_SHA.casefold(), X15_RANK_LABEL_ONLY_SHA.casefold(),
    })


def has_verified_x15_rank_labels(sha: str | None, analysis: dict | None) -> bool:
    """Confirma a tabela e o layout no BIN traduzido, sem validar execução MIPS."""
    if is_x15_sha(sha):
        return True
    if (type(sha) is not str or
            sha.casefold() != X15_RANK_LABEL_ONLY_SHA.casefold() or
            not isinstance(analysis, dict)):
        return False
    return (
        analysis.get("structure_verified") is True
        and analysis.get("table_sha256") == X15_RANK_TABLE_SHA256
        and analysis.get("table_count") == 40
        and analysis.get("first_offset") == X15_RANK_TABLE_FIRST_OFFSET
        and analysis.get("repeat_stride") == X15_RANK_TABLE_STRIDE
    )


def rank_system(sha: str | None) -> str:
    return "x15" if is_x15_rank_label_sha(sha) else "classic"


def available_ranks(sha: str | None) -> tuple[str, ...]:
    return X15_RANKS if is_x15_rank_label_sha(sha) else CLASSIC_RANKS


def drop_filter_ranks(sha: str | None) -> tuple[str, ...]:
    """Dropdown choices for reward tables; NOT the duel's RANK system."""
    return X15_RANKS if is_x15_rank_label_sha(sha) else CLASSIC_DROP_FILTERS


def pool_index_for_drop_filter(sha: str | None, rank: str) -> int:
    """Map UI groups to original WA_MRG banks, leaving duel RANKs intact.

    Old individual rank filters remain accepted for existing API clients.
    The X15 ISO never receives these classic-only grouped filter labels.
    """
    if type(rank) is str and not is_x15_rank_label_sha(sha):
        classic_group_pools = {
            "SA-POW": 0,
            "BCD-POW": 1,
            "BCD-TEC": 1,
            "SA-TEC": 2,
        }
        if rank in classic_group_pools:
            return classic_group_pools[rank]
    return pool_index_for_rank(sha, rank)


def drop_pool_labels(sha: str | None) -> tuple[str, ...]:
    return X15_POOLS if is_x15_rank_label_sha(sha) else CLASSIC_POOLS


def pool_ranks(sha: str | None) -> tuple[tuple[str, ...], ...]:
    return X15_POOL_RANKS if is_x15_rank_label_sha(sha) else CLASSIC_POOL_RANKS


def pool_index_for_rank(sha: str | None, rank: str) -> int:
    if type(rank) is not str:
        raise ValueError("RANK inválido.")
    for index, ranks in enumerate(pool_ranks(sha)):
        if rank in ranks:
            return index
    raise ValueError("RANK incompatível com esta ISO.")


def classic_rank_for_verified_score(points: int) -> str:
    """Somente pontuação observada/validada (0–99); não lê RAM."""
    if type(points) is not int or not 0 <= points <= 99:
        raise ValueError("Pontuação original fora do intervalo de 0 a 99.")
    return next(rank for minimum,rank in CLASSIC_SCORE_RANKS if points>=minimum)


def x15_rank_for_verified_score(points: int) -> str:
    """Condições do Remaster X15 para resultado validado no jogo."""
    if type(points) is not int or not 0 <= points <= 300:
        raise ValueError("Pontuação X15 fora do intervalo compatível.")
    return "Z-POW" if points>=95 else "S-POW" if points>=50 else "S-TEC"


def rank_label_for_existing_score(sha: str | None, score: int) -> str:
    """Apenas classifica um SCORE JÁ CALCULADO pelo motor autorizado.

    Não lê RAM, não modifica contadores, regras ou bônus de vitória.
    Os jogos limitam as letras aos extremos de sua escala, mesmo quando
    a soma intermediária fica abaixo de zero ou acima de 99.
    """
    if type(score) is not int or not -10000 <= score <= 10000:
        raise ValueError("Pontuação calculada inválida.")
    if is_x15_rank_label_sha(sha):
        return x15_rank_for_verified_score(max(0,min(score,300)))
    return classic_rank_for_verified_score(max(0,min(score,99)))


def score_rank_for_verified_result(sha: str | None, points: int) -> str:
    return (x15_rank_for_verified_score(points) if is_x15_rank_label_sha(sha)
            else classic_rank_for_verified_score(points))
