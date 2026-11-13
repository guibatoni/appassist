# DUELTRACE v0.19.1 — Preview

## Novidades
- Seleção de instância PCSX-Redux no DUELTRACE quando mais de um processo do emulador é detectado.
- Diagnóstico separa API HTTP acessível da confirmação do processo Windows; não mostra "servidor ausente" quando somente o PID é ambíguo.

## Melhorias
- A escolha de PID fica apenas na sessão atual; ao reiniciar o PCSX-Redux, será necessária nova seleção.
- RAM pelo processo Windows selecionado explicitamente quando houver múltiplas instâncias, sem atribuir a API HTTP ao processo errado.
- Memory Card, decks, biblioteca de mods, configurações, backups, ePSXe e recursos anteriores são preservados.
- Validação automatizada de todos os filtros de diálogo do pywebview.

## Correções
- Corrigido o erro "Executável PCSX-Redux (*.exe) is not a valid file filter" ao selecionar o executável instalado.
- Corrigido o diagnóstico de múltiplas instâncias para oferecer escolha explícita, em vez de exigir fechar os processos.
- Corrigida a preferência da instância selecionada quando outro PCSX-Redux havia sido iniciado pelo DUELTRACE.
- A leitura somente consulta a RAM; não escreve no emulador e não reaproveita dados antigos se a sessão mudar.

## Limitações
- Compatibilidade real da RAM entre builds de PCSX-Redux deve ser verificada durante um duelo; nenhuma versão é aprovada sem evidência.
- Sem API HTTP compatível, a leitura direta depende das permissões de memória do Windows e da identificação de uma mão válida.
- O servidor HTTP do PCSX-Redux pode permitir conexões externas e escrita; restrinja-o no firewall caso seja habilitado.
- RANK e oponentes por mod ainda exigem comprovação independente, e o DUELTRACE não identifica automaticamente a ISO executada.

## Créditos e direitos
- Desenvolvido por Batoni Dev - Guilherme Batoni.
- Não permitida a distribuição do aplicativo sem autorização expressa do desenvolvedor.
