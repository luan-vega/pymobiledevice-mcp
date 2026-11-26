"""MCP server para diagnóstico e melhoria de memória/performance de iPhone via pymobiledevice3.

As ferramentas de diagnóstico são somente leitura. As de melhoria (actions.py) só rodam com
PMD3_MCP_ALLOW_ACTIONS=1 e confirm=True.
"""
from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from . import __version__, actions
from .runner import capture_stream, run_pmd3, truncate

mcp = MCPServer(
    name="pymobiledevice-mcp",
    version=__version__,
    instructions=(
        "Diagnóstico e melhoria de iPhone/iPad conectado via USB. "
        "Comece por list_devices e device_info. Para CPU/memória por processo use "
        "process_cpu_memory e system_stats, que exigem Modo Desenvolvedor e, no iOS 17+, "
        "`pymobiledevice3 remote tunneld` rodando como Administrador. "
        "Relatórios de crash com 'JetsamEvent' indicam apps encerrados por falta de memória. "
        "Ferramentas de melhoria (uninstall_app, kill_process, clear_crash_reports, "
        "restart_device) alteram o aparelho: primeiro chame sem confirm para ver a prévia, "
        "explique ao usuário o que será feito e só use confirm=true após ele aprovar "
        "explicitamente cada ação. No iOS, encerrar apps em segundo plano raramente melhora "
        "a performance; os ganhos reais costumam vir de liberar armazenamento (iOS fica lento "
        "com menos de ~10% livre), remover apps que causam crashes/Jetsam, reiniciar e "
        "atualizar o iOS. Recomende ajustes que só o usuário pode fazer em Ajustes "
        "(Atualização em 2º Plano, Reduzir Movimento, Descarregar Apps Não Usados)."
    ),
)

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True)

# UDID padrão, útil quando há mais de um aparelho conectado.
DEFAULT_UDID = os.environ.get("PMD3_UDID") or None


def _udid_args(udid: str | None) -> list[str]:
    udid = udid or DEFAULT_UDID
    return ["--udid", udid] if udid else []


def _tunnel_args(udid: str | None) -> list[str]:
    # `--tunnel ''` usa o tunneld com o primeiro aparelho disponível;
    # `--tunnel <UDID>` escolhe um aparelho específico.
    return ["--tunnel", udid or DEFAULT_UDID or ""]


# --- Ferramentas básicas (não exigem Modo Desenvolvedor) ---------------------


@mcp.tool(annotations=READ_ONLY)
def list_devices() -> str:
    """Lista os iPhones/iPads conectados via USB (e seus UDIDs)."""
    return run_pmd3(["usbmux", "list"])


@mcp.tool(annotations=READ_ONLY)
def device_info(udid: str | None = None) -> str:
    """Modelo, versão do iOS, número de série, capacidade e demais dados do lockdown."""
    return run_pmd3(["lockdown", "info", *_udid_args(udid)])


@mcp.tool(annotations=READ_ONLY)
def battery_diagnostics(udid: str | None = None) -> str:
    """Bateria: ciclos, capacidade atual vs. de projeto (saúde), temperatura e voltagem."""
    return run_pmd3(["diagnostics", "battery", "single", *_udid_args(udid)])


@mcp.tool(annotations=READ_ONLY)
def process_list(udid: str | None = None) -> str:
    """Processos em execução no aparelho (API diagnosticsd)."""
    return run_pmd3(["processes", "ps", *_udid_args(udid)])


@mcp.tool(annotations=READ_ONLY)
def crash_reports(udid: str | None = None) -> str:
    """Lista os relatórios de crash, travamento (hang) e Jetsam (falta de memória)."""
    return run_pmd3(["crash", "ls", *_udid_args(udid)])


@mcp.tool(annotations=READ_ONLY)
def syslog_snapshot(
    seconds: int = 10, contains: str | None = None, udid: str | None = None
) -> str:
    """Captura o syslog por alguns segundos (máx. 60).

    `contains` filtra linhas que contenham o texto (ex.: "jetsam", "memory", nome do app).
    """
    seconds = max(1, min(seconds, 60))
    raw = capture_stream(["syslog", "live", *_udid_args(udid)], seconds)
    lines = raw.splitlines()
    if contains:
        needle = contains.lower()
        lines = [line for line in lines if needle in line.lower()]
    if not lines:
        return "(nenhuma linha capturada)"
    return truncate("\n".join(lines))


# --- Ferramentas de performance (Modo Desenvolvedor + DDI + tunneld no iOS 17+) ---


@mcp.tool(annotations=READ_ONLY)
def process_cpu_memory(udid: str | None = None) -> str:
    """Snapshot estilo `top`: CPU e memória por processo.

    Requer Modo Desenvolvedor ativo, Developer Disk Image montada e, no iOS 17+,
    `pymobiledevice3 remote tunneld` rodando em um terminal de Administrador.
    """
    return run_pmd3(
        ["developer", "dvt", "sysmon", "process", "single", *_tunnel_args(udid)],
        timeout=60,
    )


@mcp.tool(annotations=READ_ONLY)
def system_stats(udid: str | None = None) -> str:
    """Estatísticas gerais do sistema (CPU e memória). Mesmos requisitos de process_cpu_memory."""
    return run_pmd3(
        ["developer", "dvt", "sysmon", "system", *_tunnel_args(udid)],
        timeout=60,
    )


@mcp.tool(annotations=READ_ONLY)
def installed_apps(udid: str | None = None) -> str:
    """Apps instalados pelo usuário, ordenados pelo espaço ocupado (app + dados)."""
    return actions.installed_apps(_udid_args(udid))


# --- Ferramentas de melhoria (alteram o aparelho) ----------------------------

DESTRUCTIVE = ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=False)


@mcp.tool(annotations=DESTRUCTIVE)
def uninstall_app(bundle_id: str, confirm: bool = False, udid: str | None = None) -> str:
    """Desinstala um app do usuário (apaga os dados dele). Sem confirm=true, só mostra a prévia."""
    return actions.uninstall_app(bundle_id, confirm, _udid_args(udid))


@mcp.tool(annotations=DESTRUCTIVE)
def kill_process(pid: int, confirm: bool = False, udid: str | None = None) -> str:
    """Encerra um processo travado ou que consome muita CPU/memória (requer Modo Desenvolvedor).

    Sem confirm=true, só mostra a prévia.
    """
    return actions.kill_process(pid, confirm, _tunnel_args(udid))


@mcp.tool(annotations=DESTRUCTIVE)
def clear_crash_reports(confirm: bool = False, udid: str | None = None) -> str:
    """Apaga os relatórios de crash do aparelho (útil para medir do zero após uma correção).

    Sem confirm=true, só mostra a prévia.
    """
    return actions.clear_crash_reports(confirm, _udid_args(udid))


@mcp.tool(annotations=DESTRUCTIVE)
def restart_device(confirm: bool = False, udid: str | None = None) -> str:
    """Reinicia o aparelho (libera memória e encerra processos presos). Sem confirm=true, só prévia."""
    return actions.restart_device(confirm, _udid_args(udid))


@mcp.prompt()
def diagnosticar_e_melhorar() -> str:
    """Roteiro completo: diagnóstico, plano de melhorias e execução com aprovação."""
    return (
        "Faça um diagnóstico do meu iPhone: device_info, battery_diagnostics, installed_apps, "
        "crash_reports e, se disponível, process_cpu_memory e system_stats. "
        "Depois apresente um plano priorizado de melhorias, separando (a) o que você pode fazer "
        "pelas ferramentas e (b) o que eu preciso fazer em Ajustes. "
        "Não execute nenhuma ação que altere o aparelho antes de eu aprovar cada uma."
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
