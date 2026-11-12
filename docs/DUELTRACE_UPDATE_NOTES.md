# DUELTRACE v0.13.0 — Preview

## Novidades
- **Visual clássico do anime:** nome, atributo, estrelas, arte, descrição e ATK/DEF aparecem dentro da própria carta.
- **Cartas completas em HD:** cada imagem é renderizada em 360×520 pixels com a arte extraída da ISO ativa.
- **Detalhes ampliados:** ao clicar, a janela mostra a carta completa e mantém dicas de fusões e drops.

## Melhorias
- **Bibliotecas harmonizadas:** Cartas, Fusões e Drops agora compartilham o mesmo visual clássico.
- **Grade mais limpa:** ATK e DEF não aparecem duplicados abaixo das miniaturas.
- **Cache automático:** só regeneramos a carta quando seus dados ou a arte original mudarem.
- **Fallback seguro:** se faltar a carta HD, a interface exibe a arte anterior sem bloquear o usuário.

## Correções
- **Dados reais:** o render usa nome, nível, tipo, atributo, ATK e DEF da ISO, sem inventar valores ausentes.
- **Segurança local:** só a ISO ativa pode fornecer imagens de cartas pelo servidor do aplicativo.
- **Atualização v0.13.0:** o aviso de atualização e os Patch Notes continuam disponíveis após instalar.
