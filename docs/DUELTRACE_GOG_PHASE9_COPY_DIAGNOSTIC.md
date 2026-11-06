# DUELTRACE — Etapa 9: exportação segura do diagnóstico real de adversários

## Evidência e motivo da mudança

No GOG MOD 2.2 - Drop 15 (NDC).iso, o DUELTRACE continua mostrando **722 cartas**
e até **39 nomes candidatos**. A revisão 23 mostra:
**"Mais de dois índices compartilham endereços; a tabela permanece sem confirmação."**

Essa frase não comprova que os aliases sejam legítimos. Pode haver um bloco de
ponteiros interpretado incorretamente, placeholders repetidos, índices vazios,
ou registros fisicamente compartilhados. A quantidade de aliases e a
distribuição real não aparecem na captura da interface.

Depois de várias revisões sintéticas de detecção, não é correto aumentar
novamente o número permitido sem **evidências numéricas reais**.

## O que foi implementado

- Botão **Copiar diagnóstico técnico** na Biblioteca de Mods, visível quando
  um mod possui adversários candidatos não confirmados.
- Consulta a API **já existente** `get_mod_scan_diagnostic(sha,false)`,
  sem rodar Ollama, sem nova leitura de ROM e sem alteração do perfil.
- Copia ao clipboard um JSON com **até cinco janelas** de métricas forenses:
  revisão, número de cartas, adversários disponíveis/candidatos,
  `pointerAliasCount`, `pointerAliasGroups`,
  `maxAliasMultiplicity`, `pointerCountDistinct`,
  `pointerNonIncreasingPairs`, `pointerSpanMin`, `pointerSpanMax`,
  condições dos limites e histogramas de bytes/status.
- Uma whitelist adicional de campos numéricos/códigos garante que não sejam
  copiados nomes de oponentes, texto da ISO, caminhos, SHA completo, bytes de
  executáveis, cartas ou arquivos privados.
- Fallback para clipboard antigo em WebView2, com mensagem clara em caso
  de falha. Nenhum relatório técnico bruto é exibido na UI do jogador.
- Documentação e testes de contrato para evitar exportação acidental.

### Como fornecer os dados necessários

1. No DUELTRACE atualizado, abra Biblioteca de Mods.
2. Expanda o **GOG MOD 2.2 - Drop 15 (NDC).iso**.
3. Clique **Copiar diagnóstico técnico** (não precisa ativar o mod).
4. Cole o texto diretamente na conversa com ChatGPT.

O JSON é estruturado, restrito aos dados agregados e não contém a ISO.
Pode ser revisado antes do envio. Para uma investigação binária mais profunda,
continua existindo `relatorio.json` no diretório de análises, mas o primeiro
diagnóstico é suficiente para distinguir se temos ponteiros vazios, aliases
agrupados, registros intercalados ou outra situação.

## Critérios de continuidade

- Se `pointerAliasCount` for alto, **não promover nomes por aumentar limites**.
- Verificar se `pointerCountDistinct` e `maxAliasMultiplicity` indicam
  sentinelas/ponteiros vazios ou uma tabela de outra estrutura.
- Investigar o layout com referências MIPS/Ghidra/Capstone quando necessário,
  sempre vinculado à ISO SHA específica.
- Somente IDs confirmados em jogo podem lastrear drops, fusões e RANK.

A revisão do parser permanece **23**: esta etapa muda apenas a coleta de
evidências e a experiência de diagnóstico, não a interpretação da ISO.
A versão Windows precisa passar em CI antes de ser indicada para instalação.
