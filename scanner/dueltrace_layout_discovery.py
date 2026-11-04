"""Descoberta genérica e limitada de executáveis PS1 e contêineres candidatos.

Não depende da extensão ou nome e não atribui cartas/drops por tamanho.
As pistas são estritamente diagnósticas: só os decodificadores de cada
estrutura podem confirmar dados. Ollama pode interpretar a lista, mas não
executa parsers arbitrários nem escreve offsets, perfis ou arquivos.
"""
from __future__ import annotations

import re
import struct

# Poucos KB por arquivo, não milhares de leituras sobre uma ISO grande.
MAX_FILES = 128
MAX_RESOURCE_PROBES = 48
MAX_EXEC_BYTES = 8 * 1024 * 1024
KNOWN_WA_SIZE = 38_148_608
WEIGHT_COUNT = 722
WEIGHT_BYTES = WEIGHT_COUNT * 2
FIRST_TABLE = 0xE9B000
RANK_STRIDE = 0x5B4
PSX_EXEC_MAGIC = b"PS-X EXE"
EXEC_NAME = re.compile(
    r"^(?:SLUS|SCUS|SLES|SCES|SLPS|SCPS|SLPM|SLED|SCED|SLKA)[._A-Z0-9-]*$",
    re.I,
)


def _name(raw: str) -> str:
    return str(raw).replace("\\", "/").strip("/").upper()


def _read_bytes(disc, name: str, start: int, count: int) -> bytes:
    """Leitura limitada em setor lógico 2048, dentro de um arquivo ISO9660."""
    lba, file_size = disc.files[name]
    if (type(lba) is not int or type(file_size) is not int
            or start < 0 or count < 0 or count > WEIGHT_BYTES
            or start + count > file_size):
        raise ValueError("Leitura candidata fora do arquivo ISO.")
    skip = start % 2048
    return disc.read(lba + start // 2048, skip + count)[skip:skip + count]


def _known_drop_probe(disc, name: str) -> dict:
    """Valida SOMENTE três matrizes do 1º oponente no layout antigo.

    Duas ou mais matrizes com soma 2048 são pistas consistentes; NÃO são
    validação de 39 adversários, distribuição ou ranks.
    """
    _, length = disc.files[name]
    if length < FIRST_TABLE + 3 * RANK_STRIDE + WEIGHT_BYTES:
        return {"matchingTables": 0, "encodings": [],
                "testedTables": 0, "state": "arquivo_menor_que_offset_antigo"}
    matches = []
    for i in range(1, 4):
        at = FIRST_TABLE + i * RANK_STRIDE
        try:
            data = _read_bytes(disc, name, at, WEIGHT_BYTES)
            values = struct.unpack("<722H", data)
        except (AttributeError, OSError, ValueError, struct.error):
            return {"matchingTables": len(matches), "encodings": matches,
                    "testedTables": i, "state": "falha_leitura"}
        if max(values) <= 2048 and sum(values) == 2048:
            matches.append("u16_2048")
        elif (all(v >= 2512 and (v - 2512) % 8 <= 6 for v in values)
              and sum((v - 2512) // 8 for v in values) == 2048):
            matches.append("mascarado_2048")
    return {"matchingTables": len(matches), "encodings": matches,
            "testedTables": 3, "state": "parcial_nao_validado"}


def discover_disc_layout(disc, boot_target: str | None = None,
                         *, max_files: int = MAX_FILES,
                         max_resource_probes: int = MAX_RESOURCE_PROBES) -> dict:
    """Lista evidências classificadas por conteúdo independentemente do nome.

    Arquivos do usuário nunca saem da máquina. Resultado contém nomes do
    índice, tamanhos, classes de assinatura e contagem de tabelas candidatas.
    """
    max_files = max(1, min(int(max_files), MAX_FILES))
    max_resource_probes = max(1, min(int(max_resource_probes), MAX_RESOURCE_PROBES))
    boot = _name(boot_target or "")
    ordered = sorted(disc.files.items(), key=lambda item: item[0])
    exe_rows, resource_rows = [], []
    probes = 0
    for name, entry in ordered[:max_files]:
        if (not isinstance(entry, tuple) or len(entry) != 2
                or type(entry[1]) is not int):
            continue
        size = entry[1]
        if size < 1:
            continue
        filename = name.rsplit("/", 1)[-1]
        try:
            prefix = disc.get(name, limit_bytes=32)
        except (OSError, ValueError, KeyError):
            continue
        is_psx = prefix.startswith(PSX_EXEC_MAGIC)
        is_boot = _name(name) == boot
        conventional_exe = bool(EXEC_NAME.fullmatch(filename)
                                or filename.endswith(".EXE"))
        if is_psx or is_boot or conventional_exe:
            reasons = []
            score = 0
            if is_psx:
                reasons.append("cabecalho_ps_x_exe")
                score += 70
            if is_boot:
                reasons.append("referencia_system_cnf")
                score += 40
            if conventional_exe:
                reasons.append("nome_executavel_comum")
                score += 10
            if 512 * 1024 <= size <= MAX_EXEC_BYTES:
                reasons.append("tamanho_executavel_possivel")
                score += 5
            exe_rows.append({
                "name": name, "size": size, "score": score,
                "psxHeader": is_psx, "bootTarget": is_boot,
                "signals": reasons,
                "validated": False,
            })

        likely_container = (size >= FIRST_TABLE + 3 * RANK_STRIDE + WEIGHT_BYTES)
        conventional_wa = filename.endswith("WA_MRG.MRG")
        size_match = size == KNOWN_WA_SIZE
        if not (conventional_wa or size_match or likely_container):
            continue
        reasons = []
        score = 0
        if conventional_wa:
            reasons.append("nome_wa_convencional")
            score += 25
        if size_match:
            reasons.append("tamanho_wa_conhecido")
            score += 15
        probe = {"matchingTables": 0, "encodings": [],
                 "testedTables": 0, "state": "não_testado"}
        if likely_container and probes < max_resource_probes:
            probes += 1
            probe = _known_drop_probe(disc, name)
            if probe["matchingTables"] >= 2:
                reasons.append("matrizes_2048_no_layout_antigo")
                score += 65
            elif probe["matchingTables"] == 1:
                reasons.append("uma_matriz_2048_nao_conclusiva")
                score += 20
        elif likely_container:
            reasons.append("limite_de_sondagem_alcancado")
        if not reasons:
            # Arquivo grande sem assinatura, nome ou estrutura conhecida:
            # ele pode conter recursos, mas não há prova da localização.
            reasons = ["arquivo_grande_formato_desconhecido"]
        resource_rows.append({
            "name": name, "size": size, "score": score,
            "signals": reasons,
            "dropArrayMatches": probe["matchingTables"],
            "dropArrayEncodings": probe["encodings"],
            "probeState": probe["state"],
            "validated": False,
        })
    exe_rows.sort(key=lambda row: (-row["score"], row["name"]))
    resource_rows.sort(key=lambda row: (-row["score"], row["name"]))
    return {
        "schema": 1, "indexedFiles": len(ordered),
        "inspectedFiles": min(len(ordered), max_files),
        "resourceProbes": probes,
        "executables": exe_rows[:20],
        "resources": resource_rows[:20],
        "notes": (
            "Tamanho e assinatura são indícios. Mesmo três matrizes "
            "compatíveis não confirmam cards, drops, efeitos, artes ou fusões."
        ),
        "validated": False,
    }


def candidate_files_for_decoder(discovery: dict, *, role: str) -> list[str]:
    """Seleção experimental restrita: sem nomes, exigir evidência estrutural."""
    if role == "executavel":
        return [
            row["name"] for row in discovery.get("executables", [])
            if row.get("psxHeader") is True and 0 < row.get("size", 0) <= MAX_EXEC_BYTES
        ]
    if role == "recursos":
        rows = [row for row in discovery.get("resources", [])
                if row.get("dropArrayMatches", 0) >= 2]
        if not rows:
            return []
        strength = max(row["dropArrayMatches"] for row in rows)
        matches = [row["name"] for row in rows
                   if row["dropArrayMatches"] == strength]
        # Não inferir um vencedor entre dois contêineres igualmente plausíveis.
        return matches if len(matches) == 1 else []
    raise ValueError("Papel de arquivo inválido.")
