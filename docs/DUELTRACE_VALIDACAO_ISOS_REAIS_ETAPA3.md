# DUELTRACE — Etapa 3A: validação de ISOs reais por evidências

**Escopo:** ferramenta de engenharia reversa local, não uma liberação de compatibilidade universal.

A etapa anterior (parser revisão 16) reconstrói 722 cartas e 39 oponentes
em `catalogo_candidato_nao_verificado.json`, somente com nomes e atributos
extraídos de um mesmo executável e layout único. Esses registros continuam
**em quarentena**. Os scripts desta etapa nunca alteram perfil jogável,
RANK, fusões, drops, RAM, atualizador, ISO ou Memory Card.

## Pré-requisitos

- ISO/BIN legítima armazenada localmente, não incluída no repositório.
- `catalogo_candidato_nao_verificado.json` gerado pelo scanner atual.
- Observações genuínas do jogo, obtidas sem usar `cartas.csv` ou o mesmo
  catálogo do scanner como suposta evidência independente.
- Python 3.10+ (sem dependências externas para esta etapa).

## 1. Observações independentes

Registre, no computador de desenvolvimento, um JSON como este
(**exemplo ilustrativo; não há cartas reais aqui**):

```json
{
  "schema": 1,
  "source": "epsxe_observacao_independente",
  "romSha256": "SUBSTITUIR_PELO_SHA256_REAL_DA_ISO",
  "cards": [
    {"id": 1, "nome": "NOME_OBSERVADO", "atk": 100, "def": 100,
     "evidenceRef": "captura-local-001"}
  ],
  "opponents": [
    {"id": 1, "nome": "OPONENTE_OBSERVADO",
     "evidenceRef": "captura-local-oponente-001"}
  ]
}
```

Amostras obrigatórias para resultado `amostra_coerente_pendente_prova_completa`:
12 IDs distintos, com dois ou mais em cada quarto do catálogo
(1–181, 182–361, 362–542 e 543–722). O código de tipo é opcional, pois
a correspondência numérica também precisa de fonte independente.

**Amostras corretas não demonstram todo o catálogo.** Nenhum status aqui
muda `validated`, `mayActivate` ou `inGameVerified` para verdadeiro.

## 2. Verificação individual com SHA do arquivo real

```powershell
python scanner/dueltrace_real_iso_validation.py `
  --candidate "D:\DUELTRACE\analises\catalogo_candidato_nao_verificado.json" `
  --observations "D:\DUELTRACE\observacoes_epsxe.json" `
  --iso "D:\MeusMods\mod.iso" `
  --output "D:\DUELTRACE\relatorio_validacao.json"
```

Opcionalmente, use `--exe` apontando para o EXE extraído da **mesma ISO**,
para confrontar também a SHA do executável. Os arquivos são lidos em modo
somente leitura. A ferramenta limita tamanho e verifica alterações enquanto
calcula o hash. Nenhum caminho pessoal, nome ou captura entra no relatório.

## 3. Comparação em lote sem compartilhar ROM

Crie o manifesto `meus_mods_privado.json` fora do GitHub:

```json
{
  "schema": 1,
  "mods": [
    {
      "image": "D:/MeusMods/mod.iso",
      "candidate": "D:/DUELTRACE/analise_mod/catalogo_candidato_nao_verificado.json",
      "observations": "D:/DUELTRACE/observacoes_mod.json"
    }
  ]
}
```

```powershell
python scanner/dueltrace_real_iso_batch.py `
  --manifest "D:\DUELTRACE\meus_mods_privado.json" `
  --output "D:\DUELTRACE\matriz_validacao.json"
```

O lote aceita até 128 ISOs. Quando um mod ainda não tem catálogo, retorna
`sem_catalogo_candidato` e não inventa informações. ISO cujo SHA não
corresponde ao catálogo recebe `iso_arquivo_divergente`.

O relatório contém somente SHA, contagem de observações, divergências e
estados. Os arquivos de entrada contêm caminhos particulares e **não devem
ser publicados**. O comando impede sobrescrever ISO ou evidência com a saída.

## 4. Critérios antes de habilitar dados ao jogador

1. Scanner com layout único, nomes/atributos e identidade do arquivo por SHA.
2. Comparação por múltiplos IDs com capturas reais e identificação do
   executável efetivamente aberto no emulador.
3. Evidência independente para a regra que associa ID à rotina do jogo
   (desmontagem/cross-reference + teste real quando necessário).
4. Regressão em múltiplas ISOs conhecidas e testes específicos para mod
   desconhecido, com diferenças registradas.
5. Promoção futura somente por um mecanismo explícito, com revisão de
   proveniência e rollback; **este módulo não implementa a promoção**.

Não reutilizar o RANK do X15 em outros mods por semelhança dos drops ou dos
IDs. Mantenha as classes e a fórmula pertencentes ao perfil real da imagem.

## 5. Próximas frentes técnicas

- Adicionar amostras reais de Original, Remaster X15, GOG MOD 2.2 e FM13 à
  validação local, sem disponibilizar ROMs ou conteúdo binário no repositório.
- Investigar deslocamentos e codificações que falharam por comparação
  diferencial de executáveis e referências cruzadas MIPS (Capstone/Ghidra).
- Descobrir fusões e drops em famílias adicionais sem transferir estruturas
  entre mods nem associar rótulos RANK sem prova.
- Testar modo básico de jogo, captura RAM, atualização e UI em Windows/ePSXe.
- Transformar verificações comprovadas em adaptadores de parser reutilizáveis
  e testes de regressão; manter fallback de compatibilidade básica nos outros.

## Testes

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Os testes destes módulos usam *arquivos sintéticos*. Rodar a suíte Python e
o build Windows não substitui a execução de uma ISO real no ePSXe. A
funcionalidade não requer Ollama, Ghidra ou conexão com a nuvem para operar.
