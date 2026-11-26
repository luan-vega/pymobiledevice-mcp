"""MCP server para diagnóstico de memória e performance de iPhone via pymobiledevice3.

Todas as ferramentas são somente leitura: nada é instalado, apagado ou alterado no aparelho.
"""
from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from . import __version__
from .runner import capture_stream, run_pmd3, truncate

mcp = MCPServer(
    name="pymobiledevice-mcp",
    version=__version__,
    instructions=(
        "Diagnóstico somente leitura de iPhone/iPad conectado via USB. "
        "Comece por list_devices e device_info. Para CPU/memória por processo use "
        "process_cpu_memory e system_stats, que exigem Modo Desenvolvedor e, no iOS 17+, "
        "`pymobiledevice3 remote tunneld` rodando como Administrador. "
        "Relatórios de crash com 'JetsamEvent' indicam apps encerrados por falta de memória."
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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
