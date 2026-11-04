# Descoberta de layouts na v0.9.7 — cabeçalhos e adaptadores limitados

A descoberta continua produzindo **candidatos**, sem habilitar cartas, drops,
fusões, efeitos, RANK ou leitura RAM. Não há ISO comercial nos testes desta entrega.

## Executáveis PS-X EXE

`scanner/dueltrace_layout_discovery.py` agora verifica o mapeamento declarado no
cabeçalho: PC em `0x10`, GP em `0x14`, endereço de carga em `0x18` e tamanho do
payload em `0x1C`. O GP não é tratado como endereço de carga.

Além da assinatura, exige payload não vazio, alinhamento de palavra, bytes dentro
do tamanho indexado do arquivo, destino contido nos 2 MiB de RAM do PS1 e entrada
dentro do payload. Aceita os endereços canônicos físicos/KUSEG, KSEG0 e KSEG1.
Cabeçalhos incompletos ou incoerentes permanecem no diagnóstico, mas a assinatura
isolada deixa de acrescentar um executável renomeado à lista do decoder.
Um cabeçalho coerente ainda não identifica Forbidden Memories nem confirma nomes.
Múltiplos executáveis coerentes são preservados como candidatos independentes.

A inspeção usa os mesmos 32 bytes iniciais por arquivo; não executa MIPS nem lê
o payload completo. Os caminhos convencionais e o BOOT já tratados pelo scanner
continuam disponíveis, sujeitos aos parsers existentes.

## Adaptadores de recursos

`DropLayoutAdapter` descreve uma sonda imutável e determinística. O único formato
registrado é `fm_wa_722_v1`, com os três offsets históricos do primeiro adversário
e as codificações de pesos já existentes. Não foi inventado um layout para GOG.
Novos adaptadores exigem código revisado e fixtures independentes; os perfis e
o Ollama não fornecem código, offsets ou adaptadores executáveis.

O relatório schema 2 preserva os campos antigos e acrescenta `layoutProbes`, a
evidência do cabeçalho e o aviso de limite de sondagem. São inspecionadas no máximo
128 entradas, até quatro adaptadores registrados e 48 sondagens no total. Cada
sondagem realiza no máximo três leituras de 1.444 bytes úteis; com alinhamento de
setor cada chamada fica abaixo de 4 KiB. Não há varredura de arquivo inteiro nem
busca irrestrita de offsets deslocados.

Leituras truncadas e LBAs negativos são rejeitados. Duas matrizes encontradas
antes de uma falha de leitura ficam registradas, mas não selecionam o arquivo.
Dois adaptadores coerentes no mesmo contêiner também não são resolvidos por
pontuação. Os decoders completos ainda precisam validar cartas, nomes, matrizes
e identidade por SHA antes de qualquer associação.

## Regressões sintéticas

`python -m unittest discover -s tests -p 'test_dueltrace_layout_discovery.py' -v`
exercita os offsets independentes de PC/GP/carga/tamanho, aliases de RAM, entrada
fora do payload, alinhamento, overflow de RAM, assinatura sem mapeamento,
truncamento de setor, LBA inválido, adaptação e ambiguidade, além dos casos
anteriores de arquivos renomeados e de tamanho enganoso.

Validação de GOG e de novos layouts com ISOs reais permanece pendente.
