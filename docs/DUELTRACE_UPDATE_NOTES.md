# DUELTRACE v0.13.0 — Preview

## Novidades
- **Visual clássico do anime:** Biblioteca, Fusões e Drops agora exibem cartas completas com barra de nome, atributo, estrelas, arte central, tipo, descrição e quadros de ATK/DEF dentro da moldura.
- **Imagem HD da carta inteira:** renderização local em 360×520 pixels, combinando a arte melhorada da ISO com moldura e textos em alta resolução.
- **Carta ampliada ao clicar:** a janela de detalhes abre a versão clássica completa, mantendo os atalhos para receitas de fusão, Voltar e informações de drops.

## Melhorias
- **Grade mais limpa:** ATK e DEF deixam de ficar repetidos abaixo das miniaturas; os valores aparecem no quadro inferior da carta.
- **Identidade única:** mesma apresentação em Biblioteca de Cartas, Fusões, Drops e na janela ampliada; se a carta HD não existir, o aplicativo usa a arte original.
- **Cache por mod:** cada carta é renderizada uma vez e regenerada somente quando a arte ou os dados extraídos mudarem, sem tocar nos arquivos originais.
- **Qualidade visual conservadora:** ampliação da arte do PS1 sem IA generativa, com texto e contornos da carta desenhados diretamente em alta resolução.

## Correções
- **Informação fiel ao mod:** nome, tipo, nível, atributo, descrição, ataque e defesa são lidos da ISO ativa; campos ausentes não são inventados.
- **Segurança:** as cartas HD só são servidas localmente e quando pertencem à ISO ativa, com verificação do caminho autorizado.
- **Atualização em um clique:** versão oficial avançou para v0.13.0, com Patch Notes incluídos e aviso automático após instalar.
