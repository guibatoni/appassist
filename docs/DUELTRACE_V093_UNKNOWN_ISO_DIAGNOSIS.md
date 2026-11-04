# DUELTRACE v0.9.3 — Diagnóstico de SLUS/WA desconhecidos e investigação Ollama

Origem: v0.9.2, PR #42, commit `b88fc5a179008412ac78a7d115533f59aacf29f9`.
Branch: `feature/dueltrace-v093-unknown-iso-diagnostics`.

## Problema observado

No Windows, o usuário importou **GOG MOD 2.2 – Drop 15 (NDC).iso** e recebeu 0 cartas/0 oponentes/0 drops/0 fusões/0 artes, enquanto FM13/Original e Remaster X15 exibiam recursos extraídos. **Zero significa ausência de dados extraídos/verificados, não ausência de conteúdo na ISO.**

## Causa encontrada no código

- `scanner_multiiso.decode_names()` utiliza offsets fixos de glifos, ponteiros, nomes e atributos de uma versão conhecida do executável. Mods podem realocar estruturas ou usar codificação diferente; um conjunto parcial não passa no limite de plausibilidade e é rejeitado.
- `decode_drops()` assume offsets e 117 tabelas de pesos com soma 2048 por tabela. Novos layouts no WA podem não seguir essa organização.
- A extração gráfica requer catálogo de cartas reconhecido e layout gráfico compatível. Se os nomes falham, a arte não é extraída como catálogo válido.
- Antes, a ação `scan_sources` chamava explicitamente `MultiModIntelligence.inspect(use_ollama=False)`, deixando o modelo fora da reanálise.
- O resumo da interface transformava essa falha em uma mensagem genérica com contagem zero, sem o motivo. Nenhuma dessas observações comprova como o GOG MOD armazena internamente seus dados; não possuímos o arquivo binário para examinar nesta sessão.

## Entrega v0.9.3

- `scanner/dueltrace_mod_diagnostic.py`: relatório compacto com setor, candidatos de executáveis/WA, nomes escolhidos, tamanho e SHA dos arquivos, falhas em nomes/drops/artes e próximos procedimentos sugeridos. Não publica bytes do jogo.
- `scanner/scanner_multiiso.py`: reconhecimento ampliado de famílias de executáveis PS1 (`SLUS`, `SCUS`, `SLES`, `SCES`, `SLPS`, etc.). Registrar candidatos WA alternativos sem usá-los como tabelas validadas quando não são `WA_MRG.MRG`.
- `scanner/dueltrace_intelligence.py` e `ia_local.py`: incorporar o diagnóstico na evidência enviada **somente ao Ollama instalado em localhost**, mantendo a ISO, SLUS, WA e artes fora do prompt. A versão do cache de relatório foi elevada para refletir os novos campos.
- `scanner/dueltrace_web_bridge.py`: novo `get_mod_scan_diagnostic(sha,with_ollama)` protegido, sem permitir leitura de perfil fora da pasta autorizada. A rotina `scan_sources` agora consulta automaticamente o Ollama **caso disponível**, mas sua indisponibilidade não impede a extração convencional. Status diferencia layout desconhecido de dados realmente identificados.
- `web/components/desktop/desktop-page.tsx`: botões **Diagnosticar estrutura** e **Investigar com Ollama** por ISO, motivo exato da falha, candidatos de arquivo e próximos passos. Reanálise não mostra mais “ISO analisada: 0 ...” como sucesso sem ressalvas.
- `tests/test_dueltrace_mod_diagnostic.py`: casos de índices alternativos, executáveis SCUS, falhas de nomes/drops, imagem inválida, metadados limitados para o LLM, credencial de sessão, consentimento para consulta e sem acesso ao arquivo binário.

## Limites importantes

- **O Ollama não extrai sozinho todas as tabelas de qualquer SLUS/WA.** Ele interpreta evidências de parsers determinísticos; para um novo layout é necessário desenvolver um decoder orientado pelos offsets/formatos encontrados e validar amostras reais do jogo.
- Não inventar nomes, probabilidades, fusões ou efeitos; não fazer fallback automático para os dados do Original/X15 com base em semelhança.
- Não enviar binários para APIs externas; localhost deve ser o único endpoint opcional. Não assumir que o modelo textual `qwen2.5:3b` sabe analisar imagens.
- Nenhum arquivo de ISO está no repositório; o arquivo GOG MOD não foi anexado nesta conversa. **Sem sua ISO ou relatório estruturado não se pode confirmar a causa exata da falha.**
- Não mudar motor de RANK v0.9.1 validado em duelos (76 B-POW e 29 B-TEC), dez classes clássicas fora do SHA exato Remaster X15, três classes apenas no X15.
- Preservar mão, fusões, drops, comparador de cartas v0.9.2, atualização autenticada por origem/SHA-256, backups e isolamento por SHA.

## Atualização do diagnóstico após identificar somente 9 arquivos (4/11/2026)

Uma captura real do GOG MOD 2.2 confirmou 9 entradas indexadas em setores de 2352 bytes, mas **nenhum nome de SLUS/SCUS/SLES e nenhum WA_MRG.MRG compatível**; Ollama local também não respondeu. Não se pode concluir que os dados do jogo não existam, que o arquivo seja inválido ou que o modelo consiga extrair bytes sem uma etapa de decodificação.

Para tornar essa evidência acionável, o diagnóstico passa a apresentar os nomes, tamanhos e LBAs dos arquivos ISO9660 indexados (até 80 itens na interface). O scanner consulta `SYSTEM.CNF` em leitura limitada para verificar uma referência `BOOT` não padrão e, se apontar para um arquivo de disco real, usa-o como candidato à validação do mesmo parser estrutural. Uma referência BOOT não valida automaticamente o layout. Caminhos inseguros ou inexistentes não são seguidos.

A próxima evidência essencial é a lista desses nove arquivos no painel **Evidências e próximas investigações**, ou o `relatorio.json` local. Sem identificar qual arquivo contém o executável/recursos, não é possível mapear nomes, artes ou drops do GOG MOD.

## Resultado real do novo diagnóstico — GOG MOD 2.2

O usuário confirmou que o Ollama está ativo com `qwen2.5:3b`. O painel mostrou:

- 9 arquivos ISO9660 indexados, setores de 2352 bytes.
- `SYSTEM.CNF` identificou `BOOT: GOG_VNT.223`, arquivo fora das famílias convencionais SLUS/SCUS. Ainda não havia indicação visual de que o arquivo BOOT **constava no índice**.
- O scanner registrou `executáveis=[]` e `WA=[]`, portanto NÃO analisou as tabelas de nomes/drops/artes.
- Ollama retornou **hipóteses em cache**, com conclusão **incorreta** de que a ISO havia sido verificada como sem cartas. Isso foi uma alucinação: falha do extrator não prova ausência de conteúdo.

**Correções adicionais no PR #43:**

1. Inspecionar até 32 bytes do cabeçalho de até 48 arquivos no índice, com assinaturas classificadas como `psx_executavel`, `riff`, `tim2` ou desconhecido, sem transmitir binários e sem tentar executá-los.
2. Distinguir `BOOT: GOG_VNT.223` **indexado** de **BOOT apontando para arquivo ausente** do ISO9660. Só quando indexado pode ser testado como arquivo candidato. Assinatura PS-X EXE não comprova layout de cartas.
3. Mostrar lista dos arquivos do disco com assinaturas e arquivos maiores como **candidatos de recursos apenas por tamanho**, sem declarar que sejam WA.
4. Ocultar o resumo conclusivo do Ollama quando a estrutura não é reconhecida, inclusive nos relatórios antigos em cache. Mostrar aviso e sugestões como hipóteses; não atribuir ausência de cartas, fusões, drops ou oponentes.
5. Melhorar as instruções do modelo local para priorizar evidências do SYSTEM.CNF e dos nomes de arquivos em vez de inventar conclusões.
6. Testar o caso real `GOG_VNT.223` presente/ausente, os limites de leitura, o cache do Ollama com falsa afirmação de ISO vazia e o inventário de recursos desconhecidos.

**Limitação:** o GOG MOD 2.2 ainda NÃO foi decodificado. Para localizar as tabelas, é necessário examinar os nomes reais dos 9 arquivos (expanda **Evidências e próximas investigações**) e, se possível, o `relatorio.json`. Nenhum parser novo do conteúdo do GOG foi validado.

## Novo caso real: RISING OF WICKED GODS 1.3.5 ver 2 — Drop 15 (NDC)

A captura enviada mais recentemente apresenta um layout **diferente do GOG MOD**. O executável `SLUS_014.11` e o arquivo `DATA/WA_MRG.MRG` aparecem no índice de 9 arquivos. O `SYSTEM.CNF` aponta para `SLUS_014.11` e a ISO tem setor de 2352 bytes.

- A leitura por offsets conhecidos retornou **0/39 nomes plausíveis de oponentes**, mas **722/722 nomes de cartas superficialmente plausíveis**. O método de plausibilidade é só um filtro de caracteres; NÃO prova que os nomes, seus IDs ou as estatísticas estejam corretos.
- O leitor de drops rejeitou já na primeira tabela: encontrou apenas um formato candidato para o ID 1 / grupo inicial, mas com pesos que NÃO satisfazem validações estruturais exigidas para o catálogo completo.
- A extração de artes depende de dados do catálogo validados e permanece indisponível; o modelo local NÃO pode contornar isso inventando correspondências.
- O Ollama exibiu uma hipótese em cache mencionando **5555 fusões candidatas**. Candidatas de varredura não significam receitas comprovadas e o texto do Ollama não certifica o layout.
- A nova função `inspect_known_name_layout` coleta dez amostras de nomes/ponteiros de cartas e sete de oponentes usando apenas offsets antigos. `diagnose_layout` exibe essas amostras como **NÃO VALIDADAS** e as torna acessíveis no painel, para investigar divergência de tabelas antes de criar qualquer parser alternativo.
- A próxima evidência útil é o `relatorio.json` dessa ISO após nova leitura, especialmente `amostras_layout_nomes`, `nomes_status` e `drops_status`. **Não confundir os perfis** da ISO Rising com os do GOG MOD.

## Próximos passos

1. Reanalisar GOG MOD 2.2 no Windows e abrir **Diagnosticar estrutura**. Conferir nomes presentes, setor, tamanho do SLUS/WA, `nomes_status`, `drops_status`, mensagens de erro. Caso Ollama local esteja disponível, clique **Investigar com Ollama** para hipóteses.
2. Fornecer `relatorio.json` e, se necessário, os dois arquivos originais (`SLUS` e `WA_MRG`) **de forma autorizada e privada** ao responsável pelo desenvolvimento para inspecionar os offsets reais; evitar disponibilizar cópias protegidas publicamente.
3. Construir parsers verificados por layout específico, não inferir listas de 722 cartas por texto parecido; comparar o jogo real e testar pesos de drop, índices de arte, descrições e fusões antes de habilitar o perfil.
4. Para evolução futura, automatizar busca estrutural por candidatas de offset com limites de custo/memória, provas de cardinalidade e confronto de múltiplos registros independentes.
5. Confirmar CI, número de testes e publicação Windows antes de declarar release pronta. Registrar versão, branch, commit, PR, CI, testes, pendências.

## Prompt de continuidade

> CONTINUAR DUELTRACE v0.9.3. Repo https://github.com/guibatoni/appassist, branch `feature/dueltrace-v093-unknown-iso-diagnostics`. O GOG MOD 2.2 – Drop 15 retornou zeros no catálogo: o código atual assume offsets e padrões do Forbidden Memories conhecido, então o parser pode rejeitar layouts novos. A v0.9.3 adiciona diagnóstico com executáveis/WA, falhas reais do parser e sugestões, consulta opcional local ao Ollama e mensagem explícita de layout desconhecido. NÃO alegar que o Ollama decodifica bytes crus ou que o GOG já foi mapeado. Próxima etapa é estudar evidências do relatório/arquivos dessa ISO, implementar um adaptador de layout comprovado, extrair dados de SLUS e WA com validação e testes. Preserve RANK ao vivo, dez ranks clássicos fora do SHA X15, três exclusivos X15, perfis separados, Biblioteca, Fusões, Drops, comparador de cartas v0.9.2, atualizador e segurança. Após alterações, rodar CI e registrar commit, PR e pendências.
