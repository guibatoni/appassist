# DUELTRACE v0.9.4 — Descoberta de layout pelo conteúdo (fase 1)

## Motivação

Uma biblioteca comercial de mods precisa reconhecer variações de SLUS/SCUS/BOOT e WA_MRG mesmo quando as extensões e os tamanhos mudarem. Exemplos reais: GOG MOD 2.2 com `GOG_VNT.223` e `GOSD/GOG_SD1.23`; Rising of Wicked Gods com `SLUS_014.11` e `DATA/WA_MRG.MRG` mas layout rejeitado. **Não são a mesma ISO**. Perfis permanecem separados por SHA-256.

A solução não pode afirmar que 100% dos mods são compatíveis apenas pelo nome, tamanho ou por uma resposta do Ollama. Compatibilidade depende de parsers binários que verifiquem offsets, quantidades, ponteiros e coerência interna.

## Implementado nesta fase

**Módulo novo `scanner/dueltrace_layout_discovery.py`:**

1. Varre até 128 entradas do índice ISO9660 e lê apenas 32 bytes de cada cabeçalho para detectar a assinatura `PS-X EXE`, independentemente do nome ou extensão.
2. Encontra candidatos a contêiner de dados em arquivos grandes; compara extensão `WA_MRG.MRG`, tamanho conhecido e **conteúdo**. Para até 48 arquivos, testa três matrizes de 722 pesos de um adversário nos offsets antigos. Conta quantas têm soma 2048 nos formatos bruto/máscara conhecidos. Cada leitura é limitada a aproximadamente 1,5 KB.
3. Se não houver arquivo WA com nome esperado nem candidato único pelo tamanho, pode sondar um **único** arquivo com pelo menos duas matrizes plausíveis. Isso NÃO comprova as demais 117 tabelas nem suas probabilidades. O decoder original precisa validar todo o catálogo para criar dados verificáveis.
4. Um executável com `PS-X EXE` pode ser testado mesmo que não tenha nome SLUS/SCUS; o reconhecimento das tabelas de cartas e oponentes continua com o decoder. BOOT do `SYSTEM.CNF` permanece outra pista.
5. Prioriza evidências, mas não seleciona automaticamente entre múltiplos candidatos com força estrutural equivalente, nem executa arquivos de dentro das ISOs.
6. Salva no relatório local `layout_discovery`, com candidatos, sinais, contador de matrizes, quantidade de sondagens e status `validated: false`. O novo diagnóstico também expõe esses dados na interface, sem caminhos do Windows, conteúdo binário ou tokens.
7. O Ollama local `qwen2.5:3b` recebe somente dados limitados dos candidatos, não arquivos. Ele pode sugerir prioridades de investigação, **nunca** alterar offsets ou criar dados de cartas, arte, drops, efeitos, fusões e oponentes. Cache de análise invalidado (schema 5).

**Correção adicional:** ajustado erro TypeScript na interface de diagnóstico herdado da v0.9.3 que impedia o build Windows (quatro referências a arrays opcionais). Preservado todo o RANK automático: dez classificações tradicionais para ISOs não-X15 e três exclusivas ao hash X15.

## Diferença essencial entre detecção e extração

- **Candidato:** nome/tamanho/hashes ou algumas matrizes plausíveis. Indica o próximo arquivo a investigar.
- **Estrutura comprovada:** parser reconhece todas as tabelas relacionadas, valida cardinalidade/pesos/endereço e verifica que os dados se referem àquela ISO.
- **Verificação no jogo:** resultados de duelos, drops, atributos e fusões conferidos com ePSXe real.
- **Nenhum estágio é substituído por Ollama.**

O modelo textual **não lê binários diretamente** e não identifica sozinho offsets em qualquer versão. São necessárias ferramentas locais determinísticas e decodificadores de vários formatos.

## Limitações da fase 1

- A sondagem de tabelas usa offsets históricos: mods com tabela relocada, comprimida, criptografada, outro stride ou outra contagem de cartas ainda podem continuar sem dados. Isso é normal, não significa ISO vazia.
- Não existem neste PR novos decoders comprovados para estruturas inéditas de efeitos, arte, fusão, textos ou drops. A extração destas áreas permanece pelos parsers já existentes, com preservação dos dados isolados por SHA.
- Um arquivo renomeado com cabeçalho PS-X pode ser identificado sem mudar seu nome. Um arquivo de recursos com comprimento diferente pode ser indicado por duas ou três matrizes conhecidas, mas requer validação do decoder completo.
- É preciso testar as ISOs reais no Windows para confirmar melhoria no GOG e nos demais mods.

## Próximos módulos de engenharia reversa

1. **Descoberta de offsets desconhecidos:** pesquisa por assinaturas estruturais, ponteiros e matrizes de distribuição, com limites de memória/tempo e validação multi-registro (39 adversários e pools por RANK).
2. **Perfil de formatadores por SHA:** plugins locais de parsers que descrevam offsets e formatos verificados; nenhum LLM poderá executar código gerado ou modificar o formato automaticamente.
3. **Catálogo de cartas universal:** correspondência por nome, atributos e imagens entre dois SHA somente com aprovação do usuário e evidência.
4. **Artes e efeitos:** localização de paleta, TIMs e blocos gráficos por assinatura; localização de textos e rotinas MIPS com análise estática; não afirmar efeitos executados sem teste.
5. **Fusões:** validar todos os bancos de receitas sem conflitos; separar candidatas de receitas realmente comprovadas.

## Testes

`tests/test_dueltrace_layout_discovery.py`: arquivo GOG com nome renomeado e tamanho distinto, executável PS-X fora do padrão, matrizes internas, ausência de falsos positivos, empate de contêineres, limites de leitura.

Antes de liberar v0.9.4: rodar toda a suíte Python, Next.js, auditoria de dependências e build Windows na CI. Publicar link somente após confirmação.

## Continuidade

> CONTINUAR DUELTRACE v0.9.4, repositório https://github.com/guibatoni/appassist, branch `feature/dueltrace-v094-universal-layout-discovery`. Implementamos sondagem segura de até 128 arquivos da ISO, busca por assinatura PS-X EXE, matrizes de 722 pesos e detecção experimental de arquivos de recursos com outro nome/tamanho. Ollama recebe apenas pistas compactas e não valida/corrige offsets nem altera o catálogo. A UI exibe candidatos como NÃO VALIDADOS. Corrigidos erros TS anteriores. Não prometa suporte universal antes de testes reais. Próxima etapa: detector de offsets de tabelas relocadas e adaptadores binários validados para cartas/oponentes, drops, arte, fusões e efeitos, preservando perfis por SHA, 10 RANKs originais nos mods comuns e 3 exclusivos X15. Registrar PR, commit, CI, testes e limitações.
