# DUELTRACE — Filtros de RANK agrupados em Drops

Mudança limitada à lista de filtros da **Biblioteca de Drops**.

Para ISOs que utilizam a estrutura original, o menu passa a mostrar:

- S-POW
- A-POW
- **BCD-POW**
- **BCD-TEC**
- A-TEC
- S-TEC

B-POW, C-POW e D-POW deixam de aparecer como três filtros separados.
O mesmo ocorre com B-TEC, C-TEC e D-TEC.

## Fiel ao jogo

No Forbidden Memories original, **BCD-POW e BCD-TEC usam o mesmo banco
físico de drops** do WA_MRG. Assim, escolher qualquer uma das duas opções
retorna a mesma tabela e as mesmas probabilidades — não se inventa um
banco separado por POW e TEC.

A lista de dez RANKs **individuais dos duelos** e o cálculo de pontuação
permanecem totalmente inalterados. Consultas antigas por B-POW, C-POW,
D-POW, B-TEC, C-TEC e D-TEC continuam aceitas internamente, para
compatibilidade com versões existentes.

O Remaster X15 continua com **Z-POW, S-POW e S-TEC**.

## Escopo e distribuição

Implementação isolada a partir do commit
`327673a300a491ad28d824b1dedff2aa279ff499` da Preview Windows
publicada v0.9.7, sem incorporar os scripts experimentais das etapas
v57/v58 que foram canceladas.

O código continua privado. A distribuição do executável Windows não é
feita automaticamente por este commit.
