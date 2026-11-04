"""Comparação local e somente leitura de cartas de duas ISOs já escaneadas.

Compara identidade de cartas por nome normalizado e pixels das artes WA
(como sinais fortes), atributos/tipo/nível (sinais auxiliares). ID na ISO
NÃO constitui evidência de equivalência e não é usado como peso.

O resultado contém CANDIDATAS para revisão. Nunca remapeia mãos, fusões,
drops, arquivos locais ou perfis automaticamente; não transmite ISO/PNG.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

MAX_CARDS = 722
MAX_IMAGE_BYTES = 500_000
SHA = re.compile(r"^[a-f0-9]{64}$")


def _name(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))[:150]


def _cards(profile: dict) -> list[dict]:
    if (not isinstance(profile, dict)
            or profile.get("supported_features", {}).get("cards") is not True
            or profile.get("verified", {}).get("cartas") != "verificado"):
        raise ValueError("O catálogo da ISO ainda não foi extraído e validado.")
    raw = profile.get("cards")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_CARDS:
        raise ValueError("Catálogo da ISO incompleto ou inválido.")
    indexed = {}
    for row in raw:
        if not isinstance(row, dict):
            raise ValueError("Carta com formato inválido.")
        cid = row.get("id")
        if type(cid) is not int or not 1 <= cid <= MAX_CARDS or cid in indexed:
            raise ValueError("ID de carta inválido ou duplicado.")
        if not _name(row.get("name")):
            raise ValueError("Carta sem nome legível no SLUS.")
        indexed[cid] = row
    return list(indexed.values())


def _art_fingerprints(profile: dict, home: Path, cards: list[dict]) -> dict[int, str]:
    """Hash SHA-256 dos pixels RGB 102x96, nunca dos bytes PNG/metadados.

    O diretório de arte é derivado apenas da pasta de análise já aprovada.
    Nem art_root nem caminhos arbitrários fornecidos pelo modelo são lidos.
    """
    if profile.get("supported_features", {}).get("art") is not True:
        return {}
    scan = profile.get("scan_result_dir")
    if not isinstance(scan, str) or not scan:
        return {}
    try:
        allowed = (Path(home) / "analises").resolve(strict=True)
        folder = (Path(scan) / "artes_722").resolve(strict=True)
        if not folder.is_relative_to(allowed) or not folder.is_dir():
            return {}
        from PIL import Image
    except (ImportError, OSError, RuntimeError):
        return {}
    result = {}
    for card in cards:
        cid = card["id"]
        path = folder / f"{cid:03d}.png"
        try:
            real = path.resolve(strict=True)
            if not real.is_relative_to(folder) or not real.is_file():
                continue
            if not 0 < real.stat().st_size <= MAX_IMAGE_BYTES:
                continue
            with Image.open(real) as image:
                if image.format != "PNG" or image.size != (102, 96):
                    continue
                rgb = image.convert("RGB")
                # Artes uniformes/sem detalhe não identificam uma carta.
                if rgb.getcolors(maxcolors=7) is not None:
                    continue
                pixels = rgb.tobytes()
            result[cid] = hashlib.sha256(pixels).hexdigest()
        except (OSError, ValueError, RuntimeError):
            continue
    return result


def _number(card: dict, key: str):
    value = card.get(key)
    return value if type(value) is int else None


def _type(card: dict):
    # O código numérico do SLUS é preferível a categorias traduzidas.
    raw = _number(card, "type_id")
    return ("id", raw) if raw is not None else (
        ("label", _name(card.get("type_label"))) if _name(card.get("type_label")) else None)


def _score(a: dict, b: dict, *, name_unique: bool, art_same: bool) -> tuple[int, list[str]]:
    evidence = []
    score = 0
    an, bn = _name(a.get("name")), _name(b.get("name"))
    if an == bn:
        evidence.append("nome_exato")
        score += 65 if name_unique else 30
        if not name_unique:
            evidence.append("nome_repetido")
    elif min(len(an), len(bn)) >= 6:
        similarity = SequenceMatcher(None, an, bn, autojunk=False).ratio()
        if similarity >= .90:
            evidence.append("nome_parecido")
            score += 26
    if art_same:
        evidence.append("arte_rgb_identica")
        score += 85
    atk_a, atk_b = _number(a, "atk"), _number(b, "atk")
    def_a, def_b = _number(a, "def"), _number(b, "def")
    if (atk_a is not None and def_a is not None
            and atk_a == atk_b and def_a == def_b):
        evidence.append("atk_def_iguais")
        score += 11
    ta, tb = _type(a), _type(b)
    if ta is not None and tb is not None and ta == tb:
        evidence.append("tipo_igual")
        score += 6
    la, lb = _number(a, "level"), _number(b, "level")
    if la is not None and lb is not None and la == lb:
        evidence.append("nivel_igual")
        score += 3
    return score, evidence


def compare_profiles(source: dict, target: dict, home: Path) -> dict:
    """Gera correspondências candidatas entre catálogos locais distintos.

    Alto grau de confiança exige nome único com atributos coerentes, ou arte
    RGB idêntica e única nas duas ISOs. Sem confirmação por partida/usuário,
    nem mesmo candidatos fortes são promovidos a identidade oficial.
    """
    a, b = _cards(source), _cards(target)
    sha_a, sha_b = source.get("rom_sha256"), target.get("rom_sha256")
    if (type(sha_a) is not str or type(sha_b) is not str
            or not SHA.fullmatch(sha_a) or not SHA.fullmatch(sha_b)
            or sha_a == sha_b):
        raise ValueError("Selecione duas ISOs diferentes com SHA-256 válido.")

    image_a = _art_fingerprints(source, home, a)
    image_b = _art_fingerprints(target, home, b)
    name_count_a = Counter(_name(c.get("name")) for c in a)
    name_count_b = Counter(_name(c.get("name")) for c in b)
    art_count_a, art_count_b = Counter(image_a.values()), Counter(image_b.values())
    by_name = defaultdict(list)
    by_art = defaultdict(list)
    by_stats = defaultdict(list)
    for row in b:
        key = _name(row["name"])
        by_name[key].append(row)
        picture = image_b.get(row["id"])
        if picture:
            by_art[picture].append(row)
        atk, defense = _number(row, "atk"), _number(row, "def")
        if atk is not None and defense is not None:
            by_stats[(atk, defense)].append(row)

    rows = []
    for card in a:
        cid = card["id"]
        name_key = _name(card["name"])
        art = image_a.get(cid)
        candidates = {}
        # Nunca comparar somente pelo número do ID.
        for other in by_name[name_key]:
            candidates[other["id"]] = other
        if art and art_count_a[art] == 1 and art_count_b[art] == 1:
            for other in by_art[art]:
                candidates[other["id"]] = other
        atk, defense = _number(card, "atk"), _number(card, "def")
        if atk is not None and defense is not None:
            # Busca fuzzy limitada a cartas com os mesmos atributos.
            # Atributos sem nome ou arte NÃO formam um match sozinhos.
            for other in by_stats[(atk, defense)]:
                name_other = _name(other["name"])
                if (name_key[:3] == name_other[:3]
                        and SequenceMatcher(None, name_key, name_other,
                                            autojunk=False).ratio() >= .90):
                    candidates[other["id"]] = other

        ranked = []
        for other in candidates.values():
            unique_name = (name_count_a[name_key] == 1
                           and name_count_b[name_key] == 1)
            same_art = (art is not None
                        and image_b.get(other["id"]) == art
                        and art_count_a[art] == 1 and art_count_b[art] == 1)
            points, evidence = _score(card, other, name_unique=unique_name,
                                      art_same=same_art)
            # Sem um âncora identificador (nome ou arte), não existe match.
            if not any(x in evidence for x in (
                    "nome_exato", "arte_rgb_identica", "nome_parecido")):
                continue
            ranked.append((points, other["id"], other, evidence))
        ranked.sort(key=lambda row: (-row[0], row[1]))
        best = ranked[0] if ranked else None
        rival = ranked[1] if len(ranked) > 1 else None
        ambiguous = bool(best and rival and best[0] - rival[0] < 15)
        if best:
            points, other_id, other, evidence = best
            high = (
                not ambiguous and (
                    "arte_rgb_identica" in evidence
                    or ("nome_exato" in evidence
                        and "nome_repetido" not in evidence
                        and "atk_def_iguais" in evidence)
                )
            )
            label = "alta" if high else "revisar"
            target_id, target_name = other_id, str(other["name"])[:150]
        else:
            points, label, evidence = 0, "sem_correspondencia", []
            target_id, target_name = None, None
        rows.append({
            "sourceId": cid,
            "sourceName": str(card["name"])[:150],
            "targetId": target_id,
            "targetName": target_name,
            "confidence": label,
            "signals": evidence,
            "sameId": target_id == cid if target_id is not None else None,
            "ambiguous": ambiguous,
            "candidateCount": len(ranked),
            "score": points if best else None,
        })

    # Cardinalidade 1:1: múltiplos IDs de origem não podem ser mapeados
    # silenciosamente para a mesma carta de destino.
    claimed = Counter(row["targetId"] for row in rows
                      if row["targetId"] is not None and row["confidence"] == "alta")
    for row in rows:
        if row["confidence"] == "alta" and claimed[row["targetId"]] > 1:
            row["confidence"] = "revisar"
            row["ambiguous"] = True

    counts = Counter(row["confidence"] for row in rows)
    return {
        "sourceSha": sha_a,
        "targetSha": sha_b,
        "sourceCards": len(a),
        "targetCards": len(b),
        "summary": {
            "alta": counts["alta"],
            "revisar": counts["revisar"],
            "sem_correspondencia": counts["sem_correspondencia"],
            "reordered": sum(row["confidence"] == "alta"
                             and row["sameId"] is False for row in rows),
            "sourceArtCount": len(image_a),
            "targetArtCount": len(image_b),
        },
        "rows": rows,
        "status": "CANDIDATAS — leitura local, sem alterar IDs, fusões ou drops",
        "verifiedInGame": False,
    }
