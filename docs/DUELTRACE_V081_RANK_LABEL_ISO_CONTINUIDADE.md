# DUELTRACE v0.8.1 — Mesma pontuação, RANK exibido conforme a ISO

Data: 03/11/2026.  
Repo: https://github.com/guibatoni/appassist  
Branch: `feature/dueltrace-v081-rank-label-by-iso`  
Base de desenvolvimento: `feature/dueltrace-v080-classic-ranks-and-drop-pools` (PR #30).

## Solicitação

"Agora vamos focar no calculo de rank, mantem o mesmo calculo de antes.
Porem agora é só alterar qual letra mostrar conforme a iso selecionada."

## Mudança pontual

Foi preservado o cálculo do RANK existente em:
- `scanner/dueltrace_rank_live.py` — modelo X15, base 50, vitória por LP +2 e critérios pontuados, sem alteração.
- `scanner/dueltrace_rank_profile_live.py` — modelo por mod com binding previamente verificado, sem alteração das regras, contadores, bônus e leitura da RAM.

**Somente após obter um `score` autorizado e os LP confirmados**, a ponte
desktop escolhe a etiqueta que exibirá na UI usando
`rank_label_for_existing_score(sha,score)` do módulo
`scanner/dueltrace_rank_system.py`. A pontuação, as regras, os
contadores e as checagens não são modificados.

### Remaster X15 (SHA reconhecido)

- 95 ou mais: **Z-POW**.
- 50 a 94: **S-POW**.
- 49 ou menos: **S-TEC**.

### Padrão original e demais mods (quando cálculo autorizado)

- ≥ 90: S-POW
- 80–89: A-POW
- 70–79: B-POW
- 60–69: C-POW
- 50–59: D-POW
- 40–49: D-TEC
- 30–39: C-TEC
- 20–29: B-TEC
- 10–19: A-TEC
- ≤ 9: S-TEC

Valores fora de 0–99 são mantidos **numericamente** no score exibido;
apenas a classe de apresentação usa o limite extremo do intervalo.
Não reescreve nem satura o score computado.

Exemplo: **85 pontos** mostram A-POW na ISO clássica e S-POW
no Remaster X15. O mesmo cálculo existente alimenta ambos.

A classificação guardada no snapshot de auditoria e comparação do
RANK previsto com o observado é a mesma que a UI mostra; evita
salvar "Z-POW" nos duelos do sistema clássico.

## Proteções que permanecem

- Para SHA X15 conhecido, continua exigida a confirmação de LP do ePSXe.
- Para outros mods, o contador ao vivo só funciona se já houver
  binding por SHA/SLUS/tabela de RANK validado com duelos independentes,
  ou compatibilidade binária exata com o modelo X15 já suportada.
- A atualização **não** remove a validação de leitura RAM, não
  atribui endereço host arbitrário e não afirma que todas as ISOs
  tenham fórmulas MIPS idênticas.
- Calcular um score provisório não significa resultado final do duelo.
- Não publicar ISO/BIN, SLUS, WA ou dados brutos de RAM.
- Não contornar bloqueios de antivírus/Chrome/Defender para instalar
  uma Preview não assinada digitalmente.

## Arquivos de código

1. `scanner/dueltrace_rank_system.py`: helper de etiqueta RANK
   após cálculo autorizado, para os dois sistemas.
2. `scanner/dueltrace_web_bridge.py`: aplica o helper ao resultado e
   ao snapshot da previsão, mantendo score e breakdown originais.
3. `web/components/desktop/desktop-page.tsx`: esclarece na UI
   que se alterou apenas a etiqueta e identifica o sistema.
4. `web/lib/desktop.ts`: adiciona campo opcional `rankSystem`.
5. `tests/test_dueltrace_rank_system.py`: casos 85, 95, 68, 50, 49,
   0, 101, -12 e rejeição de entradas malformadas.
6. `tests/test_dueltrace_web_bridge.py`: testes de RANK por ISO,
   score numérico intacto, calibração LP e snapshot consistente.
7. Atualização do número da versão no checker e workflow Windows.

## Testes necessários

Executar o último CI Windows na branch e conferir o HEAD.
Em Windows, usar a ISO X15 conhecida e uma ISO clássica COM
binding de RAM de RANK validado; comparar scores calculados
com o rank exibido pelo jogo após um duelo. Trocar de mod e
confirmar ausência de classificações antigas e preservação
do score. Mod sem binding validado deve continuar exibindo
RANK indisponível em vez de produzir pontos inventados.

## Prompt de continuidade

> Continue o desenvolvimento do DUELTRACE Windows no repositório
> https://github.com/guibatoni/appassist, branch
> `feature/dueltrace-v081-rank-label-by-iso`, baseada na v0.8.0
> (PR #30). A v0.8.1 mantém a fórmula de pontuação e leitura
> anteriores SEM ALTERAÇÃO. Após obter um score autorizado por
> SHA e confirmar LP, muda SOMENTE a classificação exibida:
> Remaster X15 conhecido: Z-POW ≥95, S-POW 50–94, S-TEC <50;
> sistema original: S-POW ≥90, A-POW 80–89, B-POW 70–79,
> C-POW 60–69, D-POW 50–59, D-TEC 40–49, C-TEC 30–39,
> B-TEC 20–29, A-TEC 10–19 e S-TEC <10.
> O score numérico permanece intacto, mesmo acima de 99
> ou abaixo de zero. Snapshots de auditoria passam a guardar
> a etiqueta exibida pela ISO. A UI indica X15 ou original.
> Mods sem binding de RAM validado permanecem bloqueados para
> evitar estimativas incorretas: não confundir classificação
> com autorização para ler a RAM. Conferir HEAD, PR e CI
> antes de declarar sucesso; não distribuir ROM/WA/SLUS
> nem contornar proteções em builds Windows não assinados.
> Preservar todas as funções do aplicativo (drops, biblioteca,
> fusões, scanner, artes, score ao vivo quando validado,
> atualizador seguro). Ao fechar a próxima etapa, registrar
> novo prompt com versão, branch, PR, commits, testes,
> limites e pendências.
