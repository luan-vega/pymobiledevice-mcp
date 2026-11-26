# pymobiledevice-mcp

Servidor MCP para o Claude (ou outro cliente MCP) diagnosticar **memória e performance de um iPhone/iPad** conectado ao PC. Usa o [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) e funciona no **Windows, Linux e macOS**, sem precisar de Mac nem de Xcode.

As ferramentas de **diagnóstico** são somente leitura. As de **melhoria** alteram o aparelho e ficam **desligadas por padrão** (veja [Melhorias](#melhorias)).

## Ferramentas de diagnóstico

| Ferramenta | O que faz | Exige Modo Desenvolvedor |
|---|---|---|
| `list_devices` | Lista aparelhos conectados por USB e seus UDIDs | Não |
| `device_info` | Modelo, versão do iOS, capacidade etc. | Não |
| `battery_diagnostics` | Ciclos, saúde (capacidade atual vs. de projeto), temperatura | Não |
| `process_list` | Processos em execução | Não |
| `crash_reports` | Crashes, travamentos e eventos Jetsam (falta de memória) | Não |
| `syslog_snapshot` | Captura o syslog por N segundos, com filtro de texto opcional | Não |
| `process_cpu_memory` | Snapshot tipo `top`: CPU e memória por processo | Sim |
| `system_stats` | CPU e memória do sistema todo | Sim |
| `installed_apps` | Apps do usuário ordenados pelo espaço ocupado (app + dados) | Não |

Toda ferramenta aceita `udid` (opcional), caso haja mais de um aparelho conectado.

## Melhorias

| Ferramenta | O que faz | Exige Modo Desenvolvedor |
|---|---|---|
| `uninstall_app` | Desinstala um app do usuário (apaga os dados dele) | Não |
| `kill_process` | Encerra um processo travado ou pesado | Sim |
| `clear_crash_reports` | Apaga os relatórios de crash (para medir do zero depois de uma correção) | Não |
| `restart_device` | Reinicia o aparelho | Não |

Duas travas protegem essas ações:

1. Elas só funcionam com `PMD3_MCP_ALLOW_ACTIONS=1` no ambiente do servidor.
2. Cada chamada precisa de `confirm=true`. Sem isso, a ferramenta só devolve uma **prévia**, e o servidor instrui o modelo a pedir sua aprovação antes de cada ação.

Apps do sistema (`com.apple.*`) nunca são removidos.

O servidor também traz o prompt **`diagnosticar_e_melhorar`**. Ele roda o diagnóstico completo e monta um plano priorizado, separando o que o Claude faz pelas ferramentas do que você precisa ajustar em Ajustes (Atualização em 2º Plano, Reduzir Movimento, Descarregar Apps Não Usados etc.).

> No iOS, encerrar apps em segundo plano quase nunca melhora a performance. Os ganhos reais costumam vir de liberar armazenamento, remover apps que causam crashes ou Jetsam, reiniciar e atualizar o iOS. O servidor orienta o modelo nessa direção.

## Instalação

Requisitos no PC:

- Python 3.10+
- **Windows:** iTunes ou o app *Dispositivos Apple* (Microsoft Store), que instala os drivers USB

```bash
pip install git+https://github.com/luan-vega/pymobiledevice-mcp
```

Ou, a partir de um clone:

```bash
git clone https://github.com/luan-vega/pymobiledevice-mcp
cd pymobiledevice-mcp
python -m venv .venv
.venv\Scripts\activate        # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -e ".[dev]"
```

## Conectar o iPhone

1. Conecte por cabo, desbloqueie e toque em **Confiar neste computador**.
2. Confira: `python -m pymobiledevice3 usbmux list`

Isso já libera as ferramentas básicas.

### Para CPU/memória por processo

1. Ative o **Modo Desenvolvedor**: Ajustes → Privacidade e Segurança → Modo Desenvolvedor.
   Se a opção não aparecer, rode `python -m pymobiledevice3 amfi reveal-developer-mode`.
   O iPhone reinicia e pede confirmação.
2. Monte a Developer Disk Image: `python -m pymobiledevice3 mounter auto-mount`
3. **iOS 17+:** abra um terminal **como Administrador** e deixe rodando:
   ```bash
   python -m pymobiledevice3 remote tunneld
   ```

## Registrar no cliente MCP

**Claude Code:**

```bash
claude mcp add ios-diag -- pymobiledevice-mcp

# com as ferramentas de melhoria ativadas
claude mcp add ios-diag -e PMD3_MCP_ALLOW_ACTIONS=1 -- pymobiledevice-mcp
```

Se instalou num venv, use o caminho completo, por exemplo
`C:\...\pymobiledevice-mcp\.venv\Scripts\pymobiledevice-mcp.exe`.

**Configuração JSON** (Claude Desktop, Devin e outros):

```json
{
  "mcpServers": {
    "ios-diag": {
      "command": "pymobiledevice-mcp",
      "env": { "PMD3_UDID": "", "PMD3_MCP_ALLOW_ACTIONS": "1" }
    }
  }
}
```

Depois é só pedir, por exemplo:
> "Faça um diagnóstico completo de memória, bateria e performance do meu iPhone e diga o que pode estar deixando ele lento."

## Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `PMD3_UDID` | — | UDID padrão quando há vários aparelhos |
| `PMD3_MCP_ALLOW_ACTIONS` | — | `1` ativa as ferramentas de melhoria |
| `PMD3_MCP_TIMEOUT` | `45` | Timeout (s) dos comandos |
| `PMD3_MCP_MAX_OUTPUT` | `20000` | Limite de caracteres por resposta (protege o contexto do modelo) |

## Limitações do iOS

- Não há detalhe de memória por app como o `dumpsys meminfo` do Android, só o resumo por processo.
- Estatísticas de frames e dados térmicos detalhados exigem o Instruments do Xcode (macOS).
- O servidor chama o CLI do pymobiledevice3. Se uma versão futura renomear algum subcomando,
  confira com `python -m pymobiledevice3 <grupo> --help` e ajuste em `server.py`.

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest
```

Os testes simulam o subprocesso, então não precisam de aparelho conectado.
