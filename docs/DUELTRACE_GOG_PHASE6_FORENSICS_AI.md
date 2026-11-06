# DUELTRACE — Fase 6: perícia binária e IA local opcional

## Evidência real que motivou a etapa

Na ISO `GOG MOD 2.2 - Drop 15 (NDC).iso`, o DUELTRACE continuou
exibindo **722 cartas**, mas nenhum adversário, fusão ou drop.
A análise anterior relatou **até 39 nomes candidatos** e
`terminador padrão 0xFF não comprovado`.

Esse alerta **não demonstra** que outro byte é o terminador,
nem identifica a ordem de IDs executada em jogo.

## Mudança no scanner, revisão 21

Além das hipóteses anteriores, o novo `dueltrace_opponent_forensics.py`
analisa **até cinco janelas candidatas de 39 registros** e registra:

- Quantos prefixos são legíveis e quantos registros possuem `0xFF`.
- Histogramas dos códigos de interrupção e dos primeiros bytes inválidos.
- Frequência de registros com cabeçalho.
- Quantidade de ponteiros distintos, inversões e espaçamento mínimo/máximo.
- Quantidade de fronteiras físicas conhecidas ou alcançadas.
- **Regra exata que rejeitou** a melhor janela de nomes: por exemplo,
  dados extras após marcador, ponteiros desordenados, espaço excessivo
  entre registros, marcadores mistos ou limite inseguro do último registro.

Tudo é obtido em memória durante **Atualizar dados**. A informação fica em
`relatorio.json` dentro de
`independent_opponent_discovery.forensicEvidence` e no perfil da ISO.
A interface pode apresentar um motivo de rejeição mais específico.
Não são publicados nomes candidatos, conteúdo dos bytes nem caminhos
privados nessa seção do relatório.

O novo scanner ainda **não altera ou inventa IDs, drops, fusões e RANK**.
A revisão 21 invalida o cache da análise para refazer a descoberta na
mesma ISO.

## IA opcional: Ollama com Qwen2.5-Coder 7B

O projeto já possuía `scanner/ia_local.py` e scripts para Ghidra/Capstone.
Esta etapa adiciona `scanner/dueltrace_forensic_ai.py`, um revisor
especializado para os novos dados forenses.

O modelo padrão é `qwen2.5-coder:7b` (cerca de 4,7 GB no Ollama), visando
uma máquina com 8 GB de VRAM e 16 GB de RAM. O processamento local pode
usar memória adicional e ser mais lento se a GPU estiver ocupada.
Não é necessário para importar mods ou executar o jogo.

### Instalação facultativa, no Windows

1. Instale o Ollama de sua fonte oficial (https://ollama.com).
2. No terminal, rode `ollama pull qwen2.5-coder:7b`.
3. Com o Ollama disponível em `127.0.0.1:11434`, abra um terminal
   na pasta de desenvolvimento DUELTRACE (com Python 3.10+).
4. Execute:

```powershell
python scanner/dueltrace_forensic_ai.py `
  --report "C:\CAMINHO\GOG\relatorio.json" `
  --out "C:\CAMINHO\GOG\revisao_ia_local.json"
```

**Limites e segurança:**

- O script chama **apenas** `http://127.0.0.1:11434/api/generate`.
- Envia só contagens, histogramas e códigos de decisão permitidos.
- Não transmite ROM, SLUS, WA, nomes, arquivos, SHA, capturas,
  endereços MIPS ou caminhos locais.
- Usa respostas JSON, vocabulário permitido e limite de geração.
- Se Ollama não estiver instalado, a importação determinística
  continua operando; a revisão retorna status indisponível.
- **Não é serviço em nuvem, não faz promoção automática,
  não gera patches e nunca permite ativar dados por decisão da IA.**

O uso da IA é uma ferramenta **opcional para desenvolvedores**, sem
travar a UI do jogador. Não há instalação automática de ferramentas
externas nem modelo incluído no ZIP.

## Ferramentas gratuitas de engenharia reversa já previstas

- **Capstone** (disassembly MIPS): integração opcional de leitura estática
  em `scanner/dueltrace_mips_reference_probe.py`.
- **Ghidra** (engenharia reversa, análise headless): existe um script
  restrito `tools/reverse_engineering/DueltraceXrefs.java`. Usá-lo
  somente para conferir referências do executável legítimo, sem
  presumir que uma referência tenha sido executada em jogo.
- **Rizin**: alternativa gratuita para inspeção binária manual.
  Não é dependência do DUELTRACE nem foi instalada por esta etapa.

Combinar disassembly/dados observados no ePSXe é mais confiável do que
pedir a um LLM para adivinhar nomes ou ponteiros.

## Critério da próxima prova real

No Windows com a Preview revisada:

1. Selecionar GOG MOD 2.2 e clicar **Atualizar dados**.
2. Conferir na interface o novo motivo específico, se houver.
3. Verificar `relatorio.json`, campo
   `independent_opponent_discovery.forensicEvidence.windows`.
4. Se os 39 adversários ainda não forem encontrados, analisar o
   relatório real, sem assumir que o modelo local possa confirmar IDs.
5. Só associar drops de 117 matrizes após validar a ordem de IDs,
   grupos físicos de drops e a rotina MIPS correspondente ao mod.

### Qualidade e publicação

Os testes usam executáveis sintéticos e simulam o Ollama sem rede.
Um build Windows bem-sucedido **não comprova** compatibilidade
do GOG MOD 2.2, nem autoriza anunciar suporte universal.
Esta branch permanece separada de `main`.
