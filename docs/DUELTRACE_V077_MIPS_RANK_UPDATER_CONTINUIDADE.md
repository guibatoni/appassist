# DUELTRACE v0.7.7 — MIPS, RANK por mod e atualização confiável

## Situação

Repositório: https://github.com/guibatoni/appassist
Branch atual: `feature/dueltrace-v077-mips-rank-safe-updates`
Base preservada: `feature/dueltrace-v076-rank-autodiscovery` (PR #26)
Idioma: português do Brasil. Plataforma: Windows/ePSXe.

### RANK

- `scanner/fm_rank_mips_evidence.py` examina o formato `PS-X EXE` do SLUS:
  identifica cabeçalho 0x800, endereço de entrada, endereço de carga e
  padrões MIPS R3000 indicativos de leitura de meia-palavra, comparação,
  saltos condicionais e acumulação. Apresenta PCs/offsets e evidências
  reproduzíveis, sem extrair nem publicar o código comercial do jogo.
- A integração com o scanner guarda `rank_mips_evidence` por SHA de cada
  ISO. A Biblioteca de Mods apresenta quantidade de trechos MIPS candidatos.
- **Não equivale a execução MIPS confirmada.** Identificar instruções
  presentes no binário não prova que rodaram no cálculo do RANK em um duelo.
- `scanner/dueltrace_rank_profile_live.py` é um motor independente da
  versão X15, com regras por ISO, mapeamento próprio dos contadores da RAM
  do emulador, faixas e bônus de vitória. Exige hash exato da ROM, SLUS e
  tabela de RANK, validação externa em pelo menos dois duelos e confirmação
  de LP antes de mostrar projeções.
- `scanner/dueltrace_rank_live.py` agora lê de forma somente-leitura um
  endereço host específico do ePSXe para mods com binding válido, em duas
  amostras idênticas, sem fazer escritas de memória ou pesquisar a RAM toda.
- `scanner/dueltrace_web_bridge.py` mantém compatibilidade X15 e aceita
  bindings de novos mods quando validados. Identifica também mods com ISO
  diferente mas SLUS e tabelas RANK idênticos ao X15 (mesmo offset e stride)
  — ainda exige confirmar LP, não afirma RANK final.
- Falta coleta real de rastros MIPS e jogos no ePSXe para estabelecer novos
  bindings automaticamente e confirmar todos os modded scoring paths.
  **Não declarar suporte universal validado.**

### Atualizador online

- A última GitHub Release estável verificada é `v0.6.6`; ela distribui
  ZIP e imagens, **não** um instalador `DUELTRACE-Setup-vX.Y.Z.exe`
  assinado. Os builds v0.7.x são artefatos temporários do GitHub Actions.
- Atualizador consulta especificamente o workflow oficial do GitHub; não
  escolhe PRs, runs de terceiros, versões anteriores nem arquivos expirados.
- Verificação automática na inicialização e a cada três horas enquanto o
  aplicativo estiver aberto; o usuário pode forçar nova consulta.
- Problemas da API/limite do GitHub são apresentados claramente, e o
  botão leva à página oficial do build para avaliação manual.
- `dueltrace_signed_install.py` deixa de depender de um campo de editor
  permanentemente vazio. Em uma futura versão **instalada já assinada**,
  valida sua própria assinatura Authenticode com cadeia confiável e
  exige no novo instalador o mesmo sujeito, emissor **e thumbprint**,
  além de URL oficial e SHA-256 da release. Requer autorização do usuário.
- **Não há instalador assinado publicado. A v0.7.7 Preview NÃO se auto-instala.**
  Uma instalação atual não assinada não pode adquirir confiança através de
  ZIPs não assinados ou desativação de antivírus. A primeira versão assinada
  precisará de instalação oficial inicial.

### Verificações e requisitos

- Testes sintéticos do MIPS, pontuação genérica, leituras host-RAM,
  correspondência de certificados e manipulação de versões.
- CI Windows de Python, Next.js, ZIP, auditoria de dependências e Defender
  deve estar aprovado no commit mais recente ANTES de distribuir.
- O processamento real das ISOs X15/FM13/Original ainda depende de acesso
  aos binários e a duelos reais. A leitura estática não comprova a execução
  de MIPS em *qualquer* mod.
- Preservar perfil SHA, biblioteca de cartas, drops, fusões, molduras
  e todas as proteções de distribuição.
- Não publicar ISOs, SLUS ou WA de terceiros nem certificados privados.

## Próxima etapa técnica indispensável

1. Executar em Windows a análise dos arquivos reais de X15, FM13 e Original.
2. Registrar evidências do MIPS executado durante a classificação, e os
   pontos/resultado de pelo menos dois duelos independentes para cada mod.
3. Derivar e armazenar mapeamento de RAM+critérios+faixas confirmado por SHA,
   depois habilitar a projeção ao vivo daquele mod sem copiar parâmetros X15.
4. Adquirir e integrar assinatura Authenticode, publicar um verdadeiro
   instalador `DUELTRACE-Setup-vX.Y.Z.exe` como GitHub Release estável e
   testar uma atualização real de ponta a ponta com proteção do Windows.
5. Revalidar o Chrome SmartScreen e documentação de licenciamento.

## PROMPT DE RETOMADA

> Continue o DUELTRACE para Windows no repositório
> https://github.com/guibatoni/appassist, branch
> `feature/dueltrace-v077-mips-rank-safe-updates`, baseada em
> `feature/dueltrace-v076-rank-autodiscovery` (PR #26). A v0.7.7
> acrescentou um auditor estático dos padrões MIPS em arquivos PS-X EXE
> (candidatos, ainda NÃO execução confirmada), motor genérico de RANK
> por perfis SHA, leitura somente de RAM ePSXe por binding validado,
> proteção contra aplicar fórmulas X15 em outros mods e reconhecimento
> especial de ISOs com executáveis e tabelas de RANK idênticos ao X15,
> exigindo confirmação de LP. Atualizador consulta o workflow GitHub oficial,
> busca novas versões na inicialização e periodicamente, e só instala
> releases oficiais cujo instalador Authenticode corresponde ao mesmo
> certificado do DUELTRACE já instalado. A versão estável pública mais
> recente encontrada é 0.6.6 e não possui instalador Windows assinado;
> as prévias 0.7.x são não assinadas, portanto o auto-update para essas
> builds permanece bloqueado. Ainda precisam ser feitos testes em ISOs
> reais e logs de execução MIPS/ePSXe para confirmar RANK em outros mods,
> assinatura de código e teste de atualização de ponta a ponta.
> Preserve todas as funcionalidades e não diga que suporte universal
> está confirmado sem evidências. Consultar PR, HEAD e CI do trabalho
> atual e corrigir eventuais falhas. Ao terminar, publicar novo prompt
> de continuidade com branch, commit, CI, mudanças e pendências.
