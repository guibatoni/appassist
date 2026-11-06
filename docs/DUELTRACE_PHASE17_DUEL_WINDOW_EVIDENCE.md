# DUELTRACE — Etapa 17: correlação de janelas com duelos reais

**Estado:** ferramenta experimental, somente leitura. Base: Etapa 16 / PR #63.

## Problema identificado
O GOG MOD 2.2 mantém 722 cartas e 39 nomes de adversários, porém foram encontrados 40 blocos estruturais de dados (`0x1800` bytes cada, quatro matrizes por bloco). Existem duas sequências distintas e sobrepostas de 39 blocos. A sequência iniciada em `0xE9B000` coincide com o endereço usado pelo leitor clássico, mas essa coincidência **não comprova a ordem dos IDs no jogo**.

## Nova implementação
- `scanner/dueltrace_window_observation.py`: compara janelas com as cartas observadas no baralho adversário e com a carta obtida após o duelo; o RANK observado é usado apenas para testar a interseção dos grupos ainda não identificados.
- `scanner/dueltrace_mod_probe_cli.py`: aceita `--duel-observations` e vincula o manifesto ao SHA-256 da ISO local; não cruza dados de ISOs diferentes.
- `tests/test_dueltrace_window_observation.py`: regressões de duas janelas, contradições, validação de entradas e bloqueio permanente de promoção.

## Manifesto privado de observações

Crie um JSON local contendo somente evidências de um mod. **O valor opponent_slot abaixo é a posição do nome na lista estrutural e ainda precisa ser confirmado no ePSXe.** O exemplo não representa uma observação real:

```json
{
  "schema": 1,
  "rom_sha256": "COLOQUE_AQUI_O_SHA256_COMPLETO_DA_SUA_ISO",
  "observations": [
    {
      "source": "manual_game_observation",
      "opponent_slot": 1,
      "observed_rank": "S-POW",
      "reward_card_id": 38,
      "played_card_ids": [1, 17, 42]
    }
  ]
}
```

`reward_card_id` é o ID de carta recebida ao final do duelo, não qualquer carta presente na mão. `played_card_ids` é opcional e pode ser `[]` quando não houver captura confiável das cartas usadas pelo oponente. Cada observação deve resultar de um duelo real.

## Execução no Windows (com Python e o projeto)

```powershell
python scanner/dueltrace_mod_probe_cli.py --iso "C:\\Jogos\\GOG MOD 2.2.iso" --duel-observations "C:\\Jogos\\observacoes.json" --output "C:\\Jogos\\auditoria.json"
```

A saída informa apenas número de janelas, contagens de conflitos e grupos ainda possíveis para cada RANK. Nenhuma tabela de drops, nome, ID ou resultado é automaticamente ativado ou importado para o perfil do usuário.

## Critérios para a próxima etapa
1. Confirmar a associação entre nome e identificador real de adversário durante a execução, preferencialmente pelo emulador ou por rastreamento MIPS.
2. Registrar mais de um duelo real e recompensas independentes para reduzir falsos positivos.
3. Comparar com outro mod real; não transferir regras apenas por semelhança de tamanho.
4. Construir a coleta na interface sem exigir JSON manual após validar o motor de evidência.

**Atenção:** uma janela permanecer compatível com algumas observações é apenas uma hipótese; não demonstra que o jogo usa aquela janela ou aqueles grupos de RANK.
