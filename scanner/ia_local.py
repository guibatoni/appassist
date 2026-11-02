"""Assistente de investigação opcional com LLM local (Ollama).

ATENÇÃO:
- Não envia ISO, executável ou Memory Card à rede.
- Envia APENAS um relatório compacto a http://127.0.0.1:11434.
- Sem Ollama instalado, o scanner determinístico continua funcionando.
- Respostas da IA são HIPÓTESES, não tabelas confirmadas.
- A IA não executa código nem altera o banco de dados do jogo.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

LOCAL_ENDPOINT="http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL="qwen2.5:3b"
SYSTEM=(
    "Você é um auxiliar de engenharia reversa de imagens locais de "
    "Yu-Gi-Oh! Forbidden Memories. Use SOMENTE as evidências fornecidas. "
    "Não invente nomes, endereços, ranks, fórmulas, fusões ou probabilidades. "
    "Não afirme que uma hipótese é comprovada. "
    "Responda em JSON estrito com campos: resumo (string), "
    "prioridades (array de strings), "
    "indices_candidatos_fusao (array de índices inteiros das candidatas disponíveis), "
    "alertas (array de strings). "
    "Não forneça comandos para modificar a ISO nem executar programas."
)


def minimal_evidence(report: dict) -> dict:
    """Descarta qualquer binário e limita o que o modelo local recebe."""
    candidates=report.get("candidates",{}).get("fusion_tables_u16",[])
    return {
        "file":str(report.get("file",""))[:200],
        "fingerprint":str(report.get("hash_rom",""))[:64],
        "verified":report.get("features",{}),
        "uncertainties":report.get("uncertainties",[])[:15],
        "evidence":report.get("evidence",[])[:20],
        "fusion_hypotheses":[{
            "index":i, "source":str(x.get("source_file",""))[:120],
            "offset":x.get("offset"),"entries":x.get("entries"),
        } for i,x in enumerate(candidates[:12])],
    }


def validate_suggestion(raw: dict, evidence: dict) -> dict:
    """IA jamais eleva candidato a verificado; índices precisam existir."""
    if not isinstance(raw,dict):
        raise ValueError("O modelo não retornou um objeto JSON")
    def clean_strings(key,limit):
        value=raw.get(key,[])
        if not isinstance(value,list):return []
        return [str(s)[:300] for s in value[:limit] if isinstance(s,str) and s.strip()]
    existing={x["index"] for x in evidence.get("fusion_hypotheses",[])}
    idx=raw.get("indices_candidatos_fusao",[])
    if not isinstance(idx,list):idx=[]
    selected=[int(i) for i in idx if type(i) is int and i in existing][:8]
    return {
        "status":"SOMENTE HIPÓTESES — NÃO VALIDADO",
        "source":"LLM LOCAL — Ollama",
        "resumo":str(raw.get("resumo",""))[:1200],
        "prioridades":clean_strings("prioridades",8),
        "indices_candidatos_fusao":selected,
        "alertas":clean_strings("alertas",8),
        "verified_data_changed":False,
    }


def analyse_with_local_ai(report: dict, *, model: str = DEFAULT_MODEL,
                          timeout: int = 120) -> dict:
    model=model.strip()
    if not model or len(model)>96 or any(c in model for c in "\n\r\0"):
        raise ValueError("Nome de modelo inválido")
    evidence=minimal_evidence(report)
    data={
        "model":model,
        "system":SYSTEM,
        "prompt":"Interprete somente este relatório em JSON:\n"+
                 json.dumps(evidence,ensure_ascii=False)[:24000],
        "stream":False,
        "format":"json",
        "options":{"temperature":0},
    }
    request=Request(LOCAL_ENDPOINT,data=json.dumps(data).encode("utf-8"),
                    headers={"Content-Type":"application/json"},method="POST")
    try:
        with urlopen(request,timeout=max(10,min(timeout,300))) as res:
            if res.status!=200:
                raise ConnectionError("Modelo local não respondeu normalmente")
            payload=json.loads(res.read(200_000).decode("utf-8"))
        response=payload.get("response","")
        suggestion=json.loads(response)
    except (URLError,HTTPError,TimeoutError) as exc:
        raise ConnectionError("Ollama não disponível localmente; instale/inicie o Ollama e baixe o modelo. "+str(exc)) from exc
    except (ValueError,UnicodeError) as exc:
        raise ValueError("IA local retornou JSON inválido; nenhuma informação foi alterada.") from exc
    return validate_suggestion(suggestion,evidence)


def save_suggestion(path: Path,suggestion:dict):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(suggestion,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)
