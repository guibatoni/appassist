"""Escolha segura entre contêineres de recursos de ISOs/BINs desconhecidas.

Analisa até seis arquivos (no máximo 96 MiB cada). As matrizes de pesos são
evidência estrutural e NÃO demonstram identidade de cartas, oponentes ou
labels de RANK. Só um conjunto de tabelas único autoriza usar o contêiner.
Se ninguém passar, o nome convencional ou a única alternativa serve como
material de pesquisa, mas continua sem validação de drops.

A seleção nunca escreve na imagem nem herda conteúdo de outro SHA.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable

MAX_RESOURCE_BYTES=96*1024*1024
MAX_CANDIDATES=6
MAX_DETAILS=8


def inspect_resource_candidates(disc, candidate_names, *,
                                decode_tables:Callable,
                                preferred_names=()) -> dict:
    """Retorna bytes exclusivamente em `selected_bytes` para o scanner.

    Relatórios armazenáveis devem omitir `selected_bytes`. Permite escolher
    uma entre alternativas renomeadas usando 117 matrizes completas. Duas
    alternativas estruturalmente válidas mas diferentes são ambíguas.
    """
    clean=[]
    files=getattr(disc,"files",{})
    for name in candidate_names:
        if (type(name) is str and len(name)<=255 and name in files
                and name not in clean):
            clean.append(name)
    result={"schema":1,"state":"sem_recurso","source":None,
            "selected_bytes":b"","method":"nenhum_candidato",
            "candidates":[],"validatedIdentity":False,
            "dropsVerified":False,"limitReached":False}
    if not clean:
        return result
    if len(clean)>MAX_CANDIDATES:
        result.update(state="candidatos_excedem_limite",
                      limitReached=True,method="multiplos_candidatos")
        return result
    preferred=[x for x in preferred_names if x in clean]
    choices=[]
    for name in clean:
        row={"name":name,"size":None,"digest":None,
             "fullMatrixLayout":False,"state":"nao_analisado"}
        result["candidates"].append(row)
        entry=files[name]
        size=entry[1] if isinstance(entry,tuple) and len(entry)==2 else None
        row["size"]=size
        if (type(size) is not int or not 0<size<=MAX_RESOURCE_BYTES):
            row["state"]="tamanho_invalido"
            continue
        try:
            raw=disc.get(name)
            if len(raw)!=size:
                row["state"]="leitura_incompleta"
                continue
            digest=hashlib.sha256(raw).hexdigest()
            row["digest"]=digest
            tables,status=decode_tables(raw)
            row["fullMatrixLayout"]=bool(
                isinstance(tables,dict) and
                len(tables.get("verificacao",[]))==117 and
                len(tables.get("drops",[]))>0)
            row["state"]=("matrizes_117_plausiveis"
                          if row["fullMatrixLayout"] else
                          "layout_nao_identificado")
            # Guardar somente digest/metadados: não reter 6 WA de 96 MiB.
            choices.append((name,digest,row["fullMatrixLayout"]))
        except (OSError,ValueError,KeyError,MemoryError,OverflowError):
            row["state"]="leitura_ou_decodificacao_invalida"
    validated=[x for x in choices if x[2]]
    unique={x[1] for x in validated}
    selected=None
    if len(unique)>1:
        result.update(state="matrizes_ambiguas",
                      method="matrizes_ambiguas")
        return result
    if validated:
        # Cópias com o mesmo SHA são equivalentes, não uma ambiguidade.
        selected=next((x for name in preferred for x in validated
                       if x[0]==name),validated[0])
        result["method"]="117_matrizes_compativeis"
        result["state"]="recurso_candidato_estrutural"
    elif len(choices)==1:
        selected=choices[0]
        result["method"]="unico_recurso_nao_validado"
        result["state"]="recurso_candidato_nao_validado"
    elif len(preferred)==1:
        selected=next((x for x in choices if x[0]==preferred[0]),None)
        if selected is not None:
            result["method"]="nome_convencional_sem_matrizes"
            result["state"]="recurso_candidato_nao_validado"
    # Sem dados completos, duas alternativas sem evidência são inseguras.
    if selected is None:
        result.update(state="recursos_ambiguos_ou_incompativeis",
                      method="multiplos_candidatos")
        return result
    # Releitura intencional: verifica que o contêiner não mudou desde
    # o probe e mantém consumo de memória limitado a uma imagem.
    name,digest,_valid=selected
    try:
        data=disc.get(name)
        if len(data)!=files[name][1] or hashlib.sha256(data).hexdigest()!=digest:
            result.update(state="recurso_alterado_durante_leitura",
                          method="sem_selecao")
            return result
    except (OSError,ValueError,KeyError,MemoryError):
        result.update(state="falha_releitura_recurso",method="sem_selecao")
        return result
    result["source"]=name
    result["selected_bytes"]=data
    result["sourceSha256"]=digest
    return result
