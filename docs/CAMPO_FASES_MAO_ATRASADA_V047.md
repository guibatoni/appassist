# Forbidden Memories MultiMod v0.4.7 — mão atrasada e etapas do campo

## Descoberta confirmada pelo usuário
A carta #291 e o Time Wizard #016 foram invocados **no mesmo slot da mesa**.
No ePSXe desta sessão, a jogada ocorre em fases:

1. Selecionar carta.
2. Definir **FaceUp/FaceDown**.
3. Selecionar **Guardian Star**.
4. Posicionar (setar) a carta no slot. **A carta está visível no campo**.
5. **Somente depois de passar o turno e o controle voltar**, o leitor atual da mão reflete a remoção da carta.

Por isso, a v0.4.6 recusava incorretamente a captura 2 com "carta ainda está na mão". Os relatórios antigos (incluindo a sequência 613→291→016 no endereço 0xBFF510) foram obtidos depois do turno e **não comprovam que aquele endereço seja slot de campo**. O endereço 0xBFF510 é imediatamente após os 140 bytes conhecidos da mão e pode ser buffer ou seleção.

## Fluxo da v0.4.7

Abra Biblioteca > Campo de duelo, selecione a ISO ativada e indique o ID conhecido, FaceUp ou FaceDown, e o número do slot observado (1–5). Slot e face são **informações visuais declaradas**, não dados validados da RAM.

1. **ANTES**: monstro na mão, ausente da mesa.
2. **PREPARADA (opcional)**: carta selecionada, FaceUp/FaceDown e Guardian Star escolhidas, ainda não posicionada no slot.
3. **NA MESA**: carta colocada no slot e visível. **Capture imediatamente, ANTES de passar o turno**. O sistema **NÃO rejeita** captura se o ID ainda aparecer na mão.
4. **MÃO ATUALIZADA (opcional)**: após o turno, quando a RAM da mão for atualizada. Registra se o ID deixou de aparecer na mão. Não infere presença na mesa.
5. **REMOVIDA (opcional)**: quando a carta realmente sair da mesa. Permite correlacionar ocorrências de ID que desapareceram.

As etapas 2, 4 e 5 são opcionais; não são precondições da etapa 3.

## Relatório JSON
É mantida a exportação em
`%LOCALAPPDATA%\ForbiddenMemoriesMultiMod\diagnosticos_campo\<SHA>\`.

Schema 2 adiciona:
- `after_preparation`, `after_summon` (instante de carta SETADA), `after_hand_refresh`, `after_removal`.
- `hand_state_at_set` descreve o atraso de leitura da mão e **não prova slot**.
- `observed_by_user` separa FaceUp/FaceDown e slot observado das evidências RAM.
- `phase_differences` inclui contagens de bytes e até 96 endereços alterados por transição, **sem dump bruto de memória**.
- `analysis` continua buscando apenas padrões candidatos uint16 LE dentro de 96 KiB próximos da mão. A ausência de padrões novos **não significa** que não haja carta na mesa.
- Nenhuma aprovação automática, nem sugestão mão + campo habilitada.

## Próximo experimento
Repetir com uma carta conhecida (pode ser #291 ou #016) no **mesmo slot**, mas desta vez **NA MESA antes da passagem do turno**. Enviar o JSON após concluir as etapas possíveis. Registrar se face visível e Guardian Star foram escolhidas e em qual slot.

Depois comparar duas cartas no mesmo slot e a mesma carta em dois slots diferentes; procurar alterações em estado/ocupação da estrutura de campo, sem confundir dados de seleção e buffer da mão.

## Segurança
Todos os acessos são apenas `reader.read`. Não modifica ROM, ePSXe, saves, Memory Cards ou fusões. Os testes CI são com leitores simulados; requer validação prática no Windows.
