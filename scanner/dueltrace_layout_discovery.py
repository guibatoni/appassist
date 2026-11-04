"""Descoberta genérica e limitada de executáveis PS1 e contêineres candidatos.

Não depende da extensão ou nome e não atribui cartas/drops por tamanho.
As pistas são estritamente diagnósticas: só os decodificadores de cada
estrutura podem confirmar dados. Ollama pode interpretar a lista, mas não
executa parsers arbitrários nem escreve offsets, perfis ou arquivos.
"""
from __future__ import annotations

from dataclasses import dataclass
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
PSX_HEADER_BYTES = 0x800
PSX_RAM_BYTES = 2 * 1024 * 1024
MAX_RESOURCE_ADAPTERS = 4
EXEC_NAME = re.compile(
    r"^(?:SLUS|SCUS|SLES|SCES|SLPS|SCPS|SLPM|SLED|SCED|SLKA)[._A-Z0-9-]*$",
    re.I,
)


def _name(raw: str) -> str:
    return str(raw).replace("\\", "/").strip("/").upper()


def _read_bytes(disc, name: str, start: int, count: int) -> bytes:
    """Leitura limitada em setor lógico 2048, dentro de um arquivo ISO9660."""
    lba, file_size = disc.files[name]
    if (type(lba) is not int or lba < 0 or type(file_size) is not int
            or file_size < 0 or type(start) is not int or type(count) is not int
            or start < 0 or count < 0 or count > WEIGHT_BYTES
            or start + count > file_size):
        raise ValueError("Leitura candidata fora do arquivo ISO.")
    skip = start % 2048
    block = disc.read(lba + start // 2048, skip + count)
    if not isinstance(block, bytes) or len(block) != skip + count:
        raise ValueError("Leitura candidata truncada.")
    return block[skip:skip + count]


def _physical_ram_address(address: int) -> int | None:
    # Endereços canônicos KUSEG, KSEG0 e KSEG1, sem aceitar wrap de 32 bits.
    if (address & 0xE0000000) not in (0, 0x80000000, 0xA0000000):
        return None
    physical = address & 0x1FFFFFFF
    return physical if physical < PSX_RAM_BYTES else None


def inspect_psx_executable_header(prefix: bytes, file_size: int) -> dict:
    """Confere o mapeamento declarado sem ler ou executar o payload MIPS.

    PC, GP, destino e tamanho ficam em 0x10/0x14/0x18/0x1C. Uma assinatura
    isolada, um BOOT ou tamanho plausível não autoriza o decoder de nomes.
    Coerência do cabeçalho ainda não comprova que o arquivo é de FM.
    """
    result = {"state": "cabecalho_invalido", "headerCoherent": False,
              "entryPoint": None, "loadAddress": None,
              "payloadSize": None, "entryFileOffset": None,
              "validated": False}
    if (not isinstance(prefix, bytes) or not prefix.startswith(PSX_EXEC_MAGIC)
            or type(file_size) is not int or not 0 < file_size <= MAX_EXEC_BYTES):
        return result
    if len(prefix) < 0x20 or file_size < PSX_HEADER_BYTES:
        result["state"] = "cabecalho_truncado"
        return result
    entry, _, load, length = struct.unpack_from("<IIII", prefix, 0x10)
    result.update(entryPoint=entry, loadAddress=load, payloadSize=length)
    if not length or length % 4 or PSX_HEADER_BYTES + length > file_size:
        result["state"] = "payload_truncado_ou_invalido"
        return result
    start = _physical_ram_address(load)
    pc = _physical_ram_address(entry)
    if (start is None or load % 4 or length > PSX_RAM_BYTES - start):
        result["state"] = "destino_ram_invalido"
        return result
    if pc is None or entry % 4 or not start <= pc < start + length:
        result["state"] = "entrada_fora_do_payload"
        return result
    result.update(state="cabecalho_coerente_nao_validado",
                  headerCoherent=True,
                  entryFileOffset=PSX_HEADER_BYTES + pc - start)
    return result


@dataclass(frozen=True)
class DropLayoutAdapter:
    """Sonda determinística registrada pelo código, nunca por texto de IA.

    Cada adaptador descreve somente offsets com formato conhecido. Não é um
    parser completo nem uma busca irrestrita por offsets desconhecidos.
    """
    name: str
    table_offsets: tuple[int, ...]

    @property
    def minimum_size(self) -> int:
        return max(self.table_offsets, default=0) + WEIGHT_BYTES

    def probe(self, disc, name: str) -> dict:
        _, length = disc.files[name]
        base = {"adapter": self.name, "matchingTables": 0, "encodings": [],
                "testedTables": 0, "validated": False}
        if (len(self.table_offsets) != 3
                or len(set(self.table_offsets)) != 3
                or any(type(at) is not int or at < 0 for at in self.table_offsets)):
            return dict(base, state="adaptador_invalido")
        if length < self.minimum_size:
            return dict(base, state="arquivo_menor_que_offset_conhecido")
        matches = []
        for number, at in enumerate(self.table_offsets, 1):
            try:
                data = _read_bytes(disc, name, at, WEIGHT_BYTES)
                values = struct.unpack("<722H", data)
            except (AttributeError, OSError, ValueError, struct.error):
                return dict(base, matchingTables=len(matches), encodings=matches,
                            testedTables=number, state="falha_leitura")
            if max(values) <= 2048 and sum(values) == 2048:
                matches.append("u16_2048")
            elif (all(v >= 2512 and (v - 2512) % 8 <= 6 for v in values)
                  and sum((v - 2512) // 8 for v in values) == 2048):
                matches.append("mascarado_2048")
        return dict(base, matchingTables=len(matches), encodings=matches,
                    testedTables=3, state="parcial_nao_validado")


# Novos formatos exigem implementação/revisão e fixtures independentes. A lista
# é interna e limitada; nenhum arquivo de perfil fornece código ou offsets.
RESOURCE_ADAPTERS = (DropLayoutAdapter(
    "fm_wa_722_v1", tuple(FIRST_TABLE + i * RANK_STRIDE for i in range(1, 4))),)


def _known_drop_probe(disc, name: str) -> dict:
    """Valida SOMENTE três matrizes do 1º oponente no layout antigo.

    Duas ou mais matrizes com soma 2048 são pistas consistentes; NÃO são
    validação de 39 adversários, distribuição ou ranks.
    """
    return RESOURCE_ADAPTERS[0].probe(disc, name)


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
                or type(entry[0]) is not int or entry[0] < 0
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
            header = inspect_psx_executable_header(prefix, size)
            if is_psx:
                reasons.append("cabecalho_ps_x_exe")
                score += 20
                if header["headerCoherent"]:
                    reasons.append("mapeamento_psx_coerente")
                    score += 50
                else:
                    reasons.append(header["state"])
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
                "executableHeader": header,
                "signals": reasons,
                "validated": False,
            })

        adapters = RESOURCE_ADAPTERS[:MAX_RESOURCE_ADAPTERS]
        likely_container = any(size >= adapter.minimum_size for adapter in adapters)
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
        layout_probes = []
        if likely_container and probes < max_resource_probes:
            for adapter in adapters:
                if size < adapter.minimum_size or probes >= max_resource_probes:
                    continue
                probes += 1
                layout_probes.append(adapter.probe(disc, name))
            if layout_probes:
                probe = max(layout_probes, key=lambda row: row["matchingTables"])
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
            "layoutProbes": layout_probes,
            "validated": False,
        })
    exe_rows.sort(key=lambda row: (-row["score"], row["name"]))
    resource_rows.sort(key=lambda row: (-row["score"], row["name"]))
    return {
        "schema": 2, "indexedFiles": len(ordered),
        "inspectedFiles": min(len(ordered), max_files),
        "resourceProbes": probes,
        "probeLimitReached": probes >= max_resource_probes,
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
            if (row.get("psxHeader") is True
                and row.get("executableHeader", {}).get("headerCoherent") is True
                and 0 < row.get("size", 0) <= MAX_EXEC_BYTES)
        ]
    if role == "recursos":
        rows = [row for row in discovery.get("resources", [])
                if (row.get("dropArrayMatches", 0) >= 2
                    and row.get("probeState") == "parcial_nao_validado")]
        # Dois layouts coerentes dentro do mesmo arquivo continuam ambíguos,
        # mesmo quando um deles encontrou uma matriz a mais que o outro.
        if any(sum(probe.get("matchingTables", 0) >= 2
                   for probe in row.get("layoutProbes", [])) > 1 for row in rows):
            return []
        if not rows:
            return []
        strength = max(row["dropArrayMatches"] for row in rows)
        matches = [row["name"] for row in rows
                   if row["dropArrayMatches"] == strength]
        # Não inferir um vencedor entre dois contêineres igualmente plausíveis.
        return matches if len(matches) == 1 else []
    raise ValueError("Papel de arquivo inválido.")
