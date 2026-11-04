"""Diagnóstico de novos mods usando apenas metadados extraídos localmente.

Não interpreta tabelas desconhecidas como válidas. Gera razões específicas
para zeros de extração e pistas para análise opcional do Ollama.
"""
from __future__ import annotations

import re

_SUPPORTED_BOOT = re.compile(
    r"^(?:SLUS|SCUS|SLES|SCES|SLPS|SCPS|SLPM|SLED|SCED|SLKA)[_0-9A-Z.\-]*$",
    re.I,
)


def diagnose_layout(report: dict, profile: dict | None = None) -> dict:
    if not isinstance(report,dict):
        report={}
    profile=profile if isinstance(profile,dict) else {}
    raw=report.get("arquivos_discos") or []
    files=[x for x in raw[:1200] if isinstance(x,dict)]
    names=[str(x.get("nome") or "").upper()[:150] for x in files]
    # Índice resumido para identificar a estrutura de novas ISOs: o usuário
    # precisa enxergar os nomes que o parser conseguiu ler. Sem bytes privados.
    inventory=[{
        "name":str(x.get("nome") or "")[:150],
        "size":x.get("tamanho") if type(x.get("tamanho")) is int else None,
        "lba":x.get("lba") if type(x.get("lba")) is int else None,
    } for x in files[:80]]
    boot_config=report.get("system_cnf") if isinstance(report.get("system_cnf"),dict) else {}
    boot_target=str(boot_config.get("boot_target") or "")[:150]
    boot_found=bool(boot_target and boot_target.upper() in names)
    signatures=(report.get("assinaturas_arquivos") or [])
    signatures_by_name={
        str(x.get("nome") or "").upper():x
        for x in signatures[:80] if isinstance(x,dict)}
    boot_signature=signatures_by_name.get(boot_target.upper(),{}).get("assinatura")
    inventory=[{**row,
        "signature":str(signatures_by_name.get(row["name"].upper(),{}).get(
            "assinatura") or "não examinada")[:40]}
        for row in inventory]
    # Apenas pistas por tamanho. Não afirmar que esses arquivos têm cartas
    # ou que podem ser tratados como WA_MRG sem validação estrutural.
    resource_candidates=sorted([
        {"name":row["name"],"size":row["size"]}
        for row in inventory if type(row["size"]) is int
        and row["size"]>=1024*1024
        and row["name"].upper() not in ("SYSTEM.CNF",boot_target.upper())
    ],key=lambda x:-x["size"])[:12]
    boot=[x for x in names
          if _SUPPORTED_BOOT.fullmatch(x.rsplit("/",1)[-1])
          or x.endswith(".EXE")]
    wa=[x for x in names
        if "WA_MRG" in x.rsplit("/",1)[-1]
        or x.rsplit("/",1)[-1].endswith(".MRG")]
    # Formato alternativo do GOG MOD: contêineres podem ser renomeados.
    # Comparação pelo tamanho serve como evidência de busca, não prova.
    wa_size_matches=[str(x)[:150] for x in
                     (report.get("wa_candidatos_por_tamanho") or [])[:12]
                     if isinstance(x,str)]
    suspected_wa=str(report.get("drops_source") or "")[:150]
    wa_selection=str(report.get("wa_selecao_metodo") or "sem_sondagem")[:70]
    errors=[]
    if not files:
        errors.append("Índice ISO9660 indisponível ou não reconhecido.")
    else:
        if not boot and not boot_target:
            errors.append("Nenhum executável PS1 conhecido foi identificado no índice.")
        elif not boot and boot_target and boot_found:
            errors.append("Executável indicado pelo BOOT ("+boot_target+
                          ") está indexado, mas seu layout não foi validado.")
        elif not boot and boot_target:
            errors.append("BOOT indica "+boot_target+
                          ", porém não há executável conhecido no índice.")
        if not any(x.endswith("WA_MRG.MRG") for x in wa):
            if wa_selection in (
                    "tamanho_identico_nao_validado",
                    "matrizes_2048_candidatas"):
                errors.append(
                    "WA_MRG.MRG não encontrado pelo nome; arquivo "
                    +suspected_wa+" selecionado apenas por tamanho para "
                    "testar as validações. Identidade não confirmada.")
            else:
                errors.append("Nenhum WA_MRG.MRG com nome esperado foi localizado.")
    status=str(report.get("status") or "não analisado")
    problem=str(report.get("problema") or "")[:250]
    if problem:
        errors.append("Erro de leitura: "+problem)
    card_state=str(report.get("nomes_status") or "")[:250]
    if card_state and (not profile.get("supported_features",{}).get("cards")):
        errors.append("Nomes/atributos SLUS: "+card_state)
    drop_state=str(report.get("drops_status") or "")[:250]
    if drop_state and not profile.get("supported_features",{}).get("drops"):
        errors.append("Drops WA: "+drop_state)
    art_state=str(report.get("artes_obs") or "")[:180]
    if art_state and not profile.get("supported_features",{}).get("art"):
        errors.append("Artes WA: "+art_state)
    name_probe=report.get("amostras_layout_nomes")
    if not isinstance(name_probe,dict):
        name_probe={}
    def safe_name_samples(key, limit):
        samples=name_probe.get(key)
        if not isinstance(samples,list):return []
        return [{
            "index":row.get("index") if type(row.get("index")) is int else None,
            "pointer":row.get("pointer") if type(row.get("pointer")) is int else None,
            "name":str(row.get("name") or "")[:80],
            "status":str(row.get("status") or "")[:40],
            "invalidGlyphs":row.get("invalidGlyphs") if type(row.get("invalidGlyphs")) is int else None,
        } for row in samples[:limit] if isinstance(row,dict)]
    discovery=report.get("layout_discovery")
    if not isinstance(discovery,dict):discovery={}
    def safe_candidates(role,limit=12):
        raw=discovery.get(role,[])
        if not isinstance(raw,list):return []
        rows=[]
        for item in raw[:limit]:
            if not isinstance(item,dict):continue
            rows.append({
                "name":str(item.get("name") or "")[:150],
                "size":item.get("size") if type(item.get("size")) is int else None,
                "signals":[str(v)[:55] for v in item.get("signals",[])[:5]
                           if isinstance(v,str)],
                "score":item.get("score") if type(item.get("score")) is int else 0,
                "dropArrayMatches":(
                    item.get("dropArrayMatches")
                    if type(item.get("dropArrayMatches")) is int else 0),
                "psxHeader":item.get("psxHeader") is True,
                "validated":False,
            })
        return rows
    boundaries=report.get("opponent_name_boundaries")
    if not isinstance(boundaries,dict):
        boundaries={}
    boundary_samples=[]
    for row in boundaries.get("samples",[])[:7]:
        if not isinstance(row,dict):continue
        boundary_samples.append({
            "id":row.get("id") if type(row.get("id")) is int else None,
            "pointer":row.get("pointer") if type(row.get("pointer")) is int else None,
            "nextPointerDelta":row.get("nextPointerDelta"),
            "headerPresent":row.get("headerPresent") is True,
            "hasFFBeforeNext":row.get("hasFFBeforeNext"),
            "firstInvalidHex":str(row.get("firstInvalidHex") or "")[:6] or None,
            "firstInvalidOffset":row.get("firstInvalidOffset"),
            "endByteHex":str(row.get("endByteHex") or "")[:6] or None,
            "tailHex":str(row.get("tailHex") or "")[:35],
            "readablePrefix":str(row.get("readablePrefix") or "")[:70],
        })
    pointer_report=report.get("opponent_pointer_candidates")
    if not isinstance(pointer_report,dict):
        pointer_report={}
    pointer_candidates=[]
    for candidate in pointer_report.get("candidates",[])[:5]:
        if not isinstance(candidate,dict):continue
        pointer_candidates.append({
            "startIndex":candidate.get("startIndex"),
            "plausible":candidate.get("plausible",0),
            "distinct":candidate.get("distinct",0),
            "samples":[str(x)[:52] for x in
                       candidate.get("samples",[])[:5] if isinstance(x,str)],
            "validated":False,
        })
    flags=profile.get("supported_features") or {}
    if status.startswith("incerto") or status.startswith("erro"):
        level="estrutura_desconhecida"
    elif not flags.get("cards") or not flags.get("drops"):
        level="extração_parcial"
    else:
        level="estrutura_reconhecida"
    if boot_target and not boot_found:
        errors.append("SYSTEM.CNF aponta para "+boot_target+
                      ", mas não há entrada com esse nome no índice ISO9660.")
    if level!="estrutura_reconhecida" and not errors:
        errors.append("As validações do catálogo não reconheceram um layout completo.")
    steps=[]
    if not files:
        steps.append("Verificar setor 2048/2352, ISO9660 e índice dos arquivos do disco.")
    if files and not boot:
        steps.append("Conferir o alvo BOOT no inventário e inspecionar assinaturas dos nove arquivos indexados.")
    if boot_target and not boot_found:
        steps.append("Verificar se "+boot_target+
                     " está em outra trilha, nome de arquivo ou entrada do diretório não indexada.")
    elif boot_found:
        steps.append("Conferir a assinatura do arquivo de boot e localizar tabelas por evidências, não por nome.")
    if discovery.get("executables") or discovery.get("resources"):
        steps.append("Conferir as evidências dos candidatos por assinatura "
                     "e estrutura; uma sondagem isolada não valida o catálogo.")
    if wa_size_matches:
        steps.append("Comparar assinatura, tabelas e artes dos contêineres "
                     "com mesmo tamanho do WA conhecido; não aprovar por tamanho.")
    if not boot or not wa:
        steps.append("Verificar nomes e posições reais de SLUS/SCUS/SLES e WA_MRG no disco.")
    if not flags.get("cards"):
        steps.append("Investigar offsets, ponteiros, tabela de glifos e atributos do executável sem reaproveitar offsets X15.")
    if not flags.get("drops"):
        steps.append("Investigar blocos WA e validar pesos/grupos por oponente antes de gerar drops.")
    if not flags.get("art"):
        steps.append("Verificar geometria, paleta e localização das artes no WA_MRG.")
    if not steps:
        steps.append("Conferir dados com o jogo real antes de promover resultados.")
    return {
        "state":level,
        "status":status[:120],
        "issues":errors[:8],
        "nextSteps":steps[:6],
        "executableCandidates":list(dict.fromkeys(
            ([boot_target] if boot_found and boot_target else [])+boot))[:12],
        "waCandidates":list(dict.fromkeys(wa+wa_size_matches))[:12],
        "waSelectionMethod":wa_selection,
        "layoutCandidates":{
            "schema":discovery.get("schema"),
            "inspectedFiles":discovery.get("inspectedFiles",0),
            "resourceProbes":discovery.get("resourceProbes",0),
            "executables":safe_candidates("executables"),
            "resources":safe_candidates("resources"),
            "note":"Candidatos por evidência, NÃO arquivos ou tabelas validados.",
            "verified":False,
        },
        "waSizeCandidates":wa_size_matches,
        "suspectedWa":suspected_wa or None,
        "suspectedWaVerified":(
            bool(flags.get("drops")) if wa_selection in (
                "tamanho_identico_nao_validado","matrizes_2048_candidatas")
            else False),
        "chosenExecutable":str(report.get("executavel") or "")[:150],
        "chosenWa":str(report.get("drops_source") or "")[:150],
        "exeSize":next((x.get("tamanho") for x in files if str(x.get("nome")).upper()==str(report.get("executavel","")).upper()),None),
        "waSize":report.get("wa_total_bytes"),
        "sectorBytes":report.get("tipo_setor"),
        "indexedFiles":len(files),
        "files":inventory,
        "possibleResourceFiles":resource_candidates,
        "systemCnf":{
            "found":boot_config.get("found") is True,
            "bootTarget":boot_target or None,
            "bootTargetIndexed":boot_found if boot_target else None,
            "bootFileSignature":str(boot_signature)[:40] if boot_signature else None,
            "status":str(boot_config.get("status") or "não encontrado")[:150],
        },
        "hashExe":str(report.get("hash_executavel") or "")[:64] or None,
        "hashWa":str(report.get("hash_wa") or "")[:64] or None,
        "cardsVerified":bool(flags.get("cards")),
        "dropsVerified":bool(flags.get("drops")),
        "artVerified":bool(flags.get("art")),
        "opponentNameBoundaries":{
            "state":str(boundaries.get("state") or "não examinado")[:70],
            "examined":boundaries.get("examined",0),
            "hasFFBeforeNext":boundaries.get("hasFFBeforeNext",0),
            "noFFBeforeNext":boundaries.get("noFFBeforeNext",0),
            "commonEndByte":str(boundaries.get("commonEndByte") or "")[:6] or None,
            "commonEndByteCount":boundaries.get("commonEndByteCount",0),
            "commonFirstInvalidByte":str(
                boundaries.get("commonFirstInvalidByte") or "")[:6] or None,
            "commonFirstInvalidCount":boundaries.get("commonFirstInvalidCount",0),
            "samples":boundary_samples,
            "validated":False,
        },
        "opponentPointerProbe":{
            "state":str(pointer_report.get("state") or "não pesquisado")[:85],
            "candidates":pointer_candidates,
            "verified":False,
        },
        "nameLayoutProbe":{
            "state":str(name_probe.get("state") or "não investigado")[:60],
            "cardSamples":safe_name_samples("cardSamples",10),
            "opponentSamples":safe_name_samples("opponentSamples",7),
            "cardPlausibleSamples":name_probe.get("cardPlausibleSamples",0),
            "opponentPlausibleSamples":name_probe.get("opponentPlausibleSamples",0),
            "note":"Amostras de offsets conhecidos, não nomes/IDs de cartas validados.",
        },
        "automaticExtractionComplete":level=="estrutura_reconhecida",
        "aiRole":"Ollama pode interpretar os indícios, mas não extrai bytes nem comprova tabelas desconhecidas.",
    }
