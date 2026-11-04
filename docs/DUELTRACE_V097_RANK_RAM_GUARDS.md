# RANK: autorização de RAM por ISO

## Correção entregue

A consulta automática de RANK deixa de sondar o endereço legado `0xB41990`
para qualquer perfil importado. A ponte só chama um leitor quando:

- o SHA-256 selecionado corresponde ao perfil da ISO Remaster X15 conhecida; ou
- o perfil da ISO ativa possui `rank_runtime_binding` válido, ligado aos mesmos
  hashes de ISO/executável/tabela e a pelo menos dois duelos independentes.

Um perfil de outra ISO, uma tabela indisponível, um binding incompleto ou
inválido e a mera igualdade de executável/tabela com X15 mantêm a RAM
bloqueada. Confirmar LP não contorna esse bloqueio. Calibração, contadores e
captura anteriores são descartados quando a autorização deixa de existir.

O diagnóstico estático continua mostrando a semelhança de executável/tabela,
mas não oferece a sonda legada para mods sem mapeamento validado. Os módulos
de investigação isolados permanecem disponíveis no código; observações
plausíveis e duas alterações de contadores não comprovam um layout RAM.

## Comportamentos preservados

A fórmula de Spoils e suas dez métricas não foram modificadas. Permanecem
cobertos por regressões: projeção de vitória por LP em 101, classificação
original de 76 como B-POW e de 29 como B-TEC e as três classificações do X15
exclusivamente para seu SHA conhecido. A calculadora manual permanece
disponível para outras ISOs sem fazer leituras RAM.

O caminho autorizado ainda exige conferência dos LP da sessão e mantém as
verificações existentes de processo, troca de duelo, lacuna de leitura e
captura para comparação posterior. Projeções continuam identificadas como
provisórias; elas não são o resultado oficial observado no jogo.

## Cabeçalho PS-X EXE

A análise estática MIPS passa a ler os campos corretos: PC em `0x10`, GP em
`0x14`, endereço de carga em `0x18` e tamanho do texto em `0x1C`. GP não é
interpretado como endereço de carga. A região declarada precisa caber no
arquivo e nos 2 MiB de RAM, com alinhamento das instruções e do PC.
Encontrar um padrão MIPS continua sem provar execução ou rotina de RANK.

## Validação e limitações

As regressões usam perfis, cabeçalhos PS-X EXE e leitores de memória
sintéticos. Elas conferem explicitamente que nenhum leitor é chamado nos
caminhos bloqueados e que a confirmação de LP/captura não altera isso.
Nenhuma ISO comercial, sessão Windows/ePSXe ou duelo real estava disponível.
Portanto, novos endereços, contadores ou modos de vitória não foram calibrados
nem declarados compatíveis nesta entrega.
