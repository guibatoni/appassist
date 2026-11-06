# DUELTRACE — Etapa 29: comparação diferencial automática de ISOs

Data: 06/11/2026. Base: Etapa 28, PR #76. Nova branch de desenvolvimento: `feature/dueltrace-v097-iso-differential-v29`.

## Motivo

O jogador confirmou que **uma ISO personalizada diferente** foi reconhecida corretamente pelo DUELTRACE, incluindo cartas, adversários, fusões e drops, e conferiu a experiência em jogo. Essa observação é uma referência positiva, mas o binário, SHA e relatório detalhado dessa ISO ainda **não** foram disponibilizados neste contexto para análise independente.

Há falhas de reconhecimento em **GOG MOD 2.2, Rising of Wicked Gods e Enhance Edition**. Não atribuir uma causa comum sem a análise dos três arquivos. O êxito em um mod com dados personalizados pode indicar que ele **preserva um layout decodificável**, mesmo alterando o conteúdo; isso é uma hipótese técnica, não uma prova sobre o empacotamento de cada mod.

## Evidência GOG já documentada

`docs/DUELTRACE_REAL_GOG_ISO_PHASE14.md`: GOG com boot `GOG_VNT.223`, último setor PS-X EXE preenchido com 560 bytes nulos verificáveis; 39 nomes estruturais usando `FD u16 FF` e campo associado ao comprimento; recurso `G0SD/GOG_SD1.23` contendo 39 decks e 117 matrizes com soma de pesos 2048. Outras etapas observaram famílias com **40 blocos físicos**, produzindo várias janelas candidatas de 39, sem associação validada. Nenhuma dessas pistas confirma ID de adversário, grupo RANK ou drop da vitória. Evitar inferir comportamento das outras duas ISOs a partir do GOG.

## Código entregue — comparador read-only

- `scanner/dueltrace_iso_differential.py`: recebe os relatórios locais `relatorio.json` do scanner, cria impressão digital estrutural com campos autorizados e compara uma ISO-base contra até 12 outras, sem ler binários de jogo.
- Inclui: presença de executável coerente, referência de BOOT, resultado de cartas 722, nomes de 39 adversários, variante estrutural `FD u16 FF`, escolha do recurso, limite da busca, quantidade de matrizes, maior sequência de blocos (como 40), quantidade possível de janelas de 39, rotulagem de RANK e estágio das fusões.
- `scanner/scanner_multiiso.py`: acrescenta `comparative_family_fingerprint` a cada novo `relatorio.json` sem modificar o contrato das cartas, CSVs, fusões, perfis ou ativação de drops.
- `scanner/dueltrace_web_bridge.py`: `compare_mod_layouts(sha)` somente sobre ISOs registradas e relatórios locais sob a pasta autorizada `analises/`; cruza também contagem/proveniência de receitas no **perfil local separado**, sem expor os IDs das receitas.
- `scanner/dueltrace_web_security.py`: exige autenticação do token de janela local.
- `web/lib/desktop.ts` e `web/components/desktop/desktop-page.tsx`: botão **Comparar ISOs** em cada mod quando houver mais de uma ISO cadastrada. A ISO clicada vira a referência; a tela mostra diferenças por estágio entre a referência e os demais mods, sempre provisórias.
- `tests/test_dueltrace_iso_differential.py` + regressão na bridge: exemplos sintéticos de mod compatível, GOG com FD e janela ambígua, rejeição de SHA inconsistente, privacidade, autenticidade e não promoção de hipóteses.

## Atividade do usuário após CI/Preview

1. Manter a ISO personalizada que já funciona **cadastrada** e cadastrados GOG/Rising/Enhance na mesma Biblioteca de Mods.
2. Para perfis muito antigos, usar **Atualizar dados** uma vez, sem apagar o perfil ou abandonar os arquivos de arte.
3. Expandir a ISO que funciona e clicar **Comparar ISOs**. O comparador lê relatórios existentes e extrai diferenças estruturais, sem enviar ROM/ISO à nuvem.
4. Não confundir semelhança estrutural com drops/RANK/fusões provados. Para verificar o motivo exato de falhas, continuar com investigação MIPS e adaptadores validados, cada qual por fonte real.

## Próxima implementação

- Para os três mods problemáticos, priorizar códigos de bloqueio por estágio com contraste da ISO positiva, e em seguida abrir formatos específicos apenas quando confirmados pelo executável e seus recursos.
- Para GOG, investigar relação entre rotina MIPS e a escolha de um dos 40 blocos, e distinguir a origem do `candidateId=5` do retail.
- Para Rising e Enhance, a causa exata está **indeterminada** até ler relatório ou binário de cada um.
- Para fusões, diferenciar existência de catálogo de receitas no perfil de evidência de execução da rotina em mod.

## Regras de proteção

Não alterar `main`, Biblioteca 722 cartas, artes, leitura de mão, sincronização privada Etapa 27, graus de comprovação dos drops, nem marcas de RANK. Os relatórios da ISO contêm caminhos e dados locais e não devem ser commitados em repositório; o comparador retorna apenas quantidades e etiquetas enum. Não criar adaptadores por nome de mod ou adivinhar offsets.

**Validação:** testes e build Windows da Etapa 29 devem ser verificados no GitHub antes de anunciar Preview aprovada. Não afirmar análise direta de ISO cuja mídia não está disponível no ambiente.

## Subetapa 29B — localizar bancos de fusões em recurso renomeado

A revisão revelou um bloqueio real em `scanner/extrator_fusoes.py`: `analyze_fusion_banks` exigia exclusivamente um nome final `WA_MRG.MRG`. Isso impede até a sondagem de recursos como `G0SD/GOG_SD1.23`, mesmo que o formato seja compatível. A rotina de nomes convencionais foi mantida **sem alterações de escolha**.

O extrator agora pode examinar **até oito contêineres** com tamanho suficiente (no máximo 96 MiB cada), sem depender da extensão, mas só seleciona um recurso renomeado quando detecta **sete bancos válidos, com receitas decodificadas de maneira idêntica e sem conflitos** nas mesmas posições históricas. Nenhuma semelhança de tamanho ou de um único banco seleciona o recurso. Dois contêineres igualmente compatíveis resultam em ambiguidade e bloqueiam a escolha. Testes sintéticos cobrem o novo formato, seis bancos válidos/um inválido, ambiguidade e manutenção da seleção canônica.

Isto é **somente um adaptador para localizar a mesma estrutura em um contêiner renomeado**. Não prova que o GOG, Rising ou Enhance tenham fusões nessas posições; não resolve bancos realocados, formatos de 10-bit modificados ou novas contagens de cartas. E **não ativa automaticamente todas as receitas**: as verificações existentes de sete bancos, revisão explícita e eventual execução em jogo permanecem necessárias.
