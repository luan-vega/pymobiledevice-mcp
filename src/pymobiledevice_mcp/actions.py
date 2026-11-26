"""Ações de melhoria (alteram o aparelho).

Duas travas protegem cada ação:
  1. A variável de ambiente PMD3_MCP_ALLOW_ACTIONS=1 precisa estar definida no servidor.
  2. Cada chamada precisa de confirm=True; sem isso a ferramenta só mostra uma prévia.
"""
from __future__ import annotations

import json
import os
import re

from .runner import run_pmd3, truncate

BUNDLE_RE = re.compile(r"^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")
PROTECTED_PREFIXES = ("com.apple.",)


def actions_enabled() -> bool:
    return os.environ.get("PMD3_MCP_ALLOW_ACTIONS", "").strip() == "1"


DISABLED_MSG = (
    "Ações de melhoria estão desativadas. Para ativar, defina PMD3_MCP_ALLOW_ACTIONS=1 "
    "no ambiente do servidor MCP e reinicie o cliente."
)


def guard(description: str, confirm: bool) -> str | None:
    """Devolve uma mensagem de bloqueio/prévia, ou None se a ação pode seguir."""
    if not actions_enabled():
        return DISABLED_MSG
    if not confirm:
        return (
            f"PRÉVIA (nada foi executado): {description}\n"
            "Peça a confirmação explícita do usuário e chame de novo com confirm=true."
        )
    return None


def validate_bundle_id(bundle_id: str) -> str | None:
    if not BUNDLE_RE.match(bundle_id):
        return "ERRO: bundle id inválido."
    if bundle_id.startswith(PROTECTED_PREFIXES):
        return "ERRO: apps do sistema (com.apple.*) não podem ser removidos por esta ferramenta."
    return None


def summarize_apps(raw: str) -> str:
    """Resume a saída JSON de `apps list` em uma lista de apps do usuário, por tamanho."""
    start = raw.find("{")
    try:
        data = json.loads(raw[start:]) if start >= 0 else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        return truncate(raw)

    rows = []
    for bundle_id, info in data.items():
        if not isinstance(info, dict) or info.get("ApplicationType", "User") != "User":
            continue
        static = info.get("StaticDiskUsage") or 0
        dynamic = info.get("DynamicDiskUsage") or 0
        name = info.get("CFBundleDisplayName") or info.get("CFBundleName") or ""
        version = info.get("CFBundleShortVersionString") or ""
        rows.append((static + dynamic, bundle_id, name, version, static, dynamic))

    if not rows:
        return "(nenhum app do usuário encontrado)"
    rows.sort(reverse=True)

    def mb(n: int) -> str:
        return f"{n / 1_048_576:,.0f} MB" if n else "?"

    lines = ["total | app | dados | bundle id | versão"]
    for total, bundle_id, name, version, _static, dynamic in rows:
        lines.append(f"{mb(total)} | {name} | {mb(dynamic)} | {bundle_id} | {version}")
    return truncate("\n".join(lines))


def installed_apps(udid_args: list[str]) -> str:
    return summarize_apps(run_pmd3(["apps", "list", *udid_args], timeout=90))


def uninstall_app(bundle_id: str, confirm: bool, udid_args: list[str]) -> str:
    if err := validate_bundle_id(bundle_id):
        return err
    if msg := guard(f"desinstalar o app {bundle_id} e APAGAR os dados dele no aparelho.", confirm):
        return msg
    return run_pmd3(["apps", "uninstall", bundle_id, *udid_args], timeout=120)


def kill_process(pid: int, confirm: bool, tunnel_args: list[str]) -> str:
    if pid <= 1:
        return "ERRO: PID inválido."
    if msg := guard(f"encerrar o processo PID {pid}.", confirm):
        return msg
    return run_pmd3(["developer", "dvt", "kill", str(pid), *tunnel_args])


def clear_crash_reports(confirm: bool, udid_args: list[str]) -> str:
    if msg := guard("apagar todos os relatórios de crash do aparelho.", confirm):
        return msg
    return run_pmd3(["crash", "clear", *udid_args], timeout=90)


def restart_device(confirm: bool, udid_args: list[str]) -> str:
    if msg := guard("reiniciar o aparelho (a conexão cai até ele voltar).", confirm):
        return msg
    return run_pmd3(["diagnostics", "restart", *udid_args])
