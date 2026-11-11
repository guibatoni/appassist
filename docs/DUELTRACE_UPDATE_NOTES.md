# DUELTRACE — Notas da atualização

## Novidades
- **ePSXe:** busca dinâmica de RAM quando o endereço antigo não funciona, com suporte a executáveis identificados por número de versão (somente Windows).
- Atualizações privadas podem ser encontradas pelo mesmo botão quando o proprietário já autenticou o GitHub CLI no Windows.
- Aba Fusões: escolha pesquisar por **resultado final**, **material da fusão** ou **ambos**, por nome ou ID da carta.
- Patch notes exibidos em uma janela dentro do aplicativo, sem abrir o navegador.

## Melhorias
- Leitura da mão com validação dupla de cinco cartas, cache temporário por processo e proteção contra endereços de memória ambíguos.
- Oponentes e projeção experimental de RANK X15 reutilizam a base de RAM detectada, sem alterar as fórmulas nem validar automaticamente uma ISO.
- Mantido o botão único **Atualizar agora**: substitui os arquivos na pasta atual, reinicia o DUELTRACE e preserva os dados locais.
- Release Preview e ZIP estável usam a mesma validação de origem, tamanho, SHA-256 e identidade do build antes da instalação.
- Pesquisa em fusões aceita IDs com `#`, ignora acentos e atualiza a paginação ao trocar de filtro.
- Painel de atualizações mais simples, com ações de atualizar e visualizar novidades.
- Pacotes ZIP verificados substituem o aplicativo na pasta existente e reiniciam o DUELTRACE.

## Correções
- ePSXe: a varredura de RAM continua de onde parou quando o primeiro bloco de 48 MB não contém a mão; busca rápida pelos deslocamentos PS1 e mensagens de estado mais claras.
- Endereço físico fixo da RAM não impede mais o reconhecimento de mãos em versões do ePSXe com disposição de memória diferente.
- Corrigida a limitação da consulta anônima que não enxerga Releases do repositório privado quando há GitHub CLI autenticado disponível.
- Atualização estável portátil tem prioridade quando também existe uma Preview.
- Testes da interface atualizados para o novo fluxo de atualização.

