"""Execução do CLI do pymobiledevice3 em subprocesso, sem shell."""
from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Sequence

MAX_OUTPUT_CHARS = int(os.environ.get("PMD3_MCP_MAX_OUTPUT", "20000"))
DEFAULT_TIMEOUT = int(os.environ.get("PMD3_MCP_TIMEOUT", "45"))


def _to_text(data: str | bytes | None) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data


def truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    """Corta saídas grandes para não estourar o contexto do modelo."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncado: {len(text) - limit} caracteres omitidos]"


def build_command(args: Sequence[str]) -> list[str]:
    """Usa o mesmo interpretador do servidor, garantindo o pymobiledevice3 do mesmo venv."""
    return [sys.executable, "-m", "pymobiledevice3", *args]


def run_pmd3(args: Sequence[str], timeout: int | None = None) -> str:
    """Executa `pymobiledevice3 <args>` e devolve stdout + stderr como texto."""
    timeout = timeout or DEFAULT_TIMEOUT
    try:
        result = subprocess.run(
            build_command(args),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return "ERRO: interpretador Python não encontrado."
    except subprocess.TimeoutExpired:
        return f"ERRO: timeout após {timeout}s executando: pymobiledevice3 {' '.join(args)}"

    output = result.stdout or ""
    if result.stderr:
        output += "\n[stderr]\n" + result.stderr
    if result.returncode != 0:
        output = f"[exit code {result.returncode}]\n" + output
        if "No module named pymobiledevice3" in (result.stderr or ""):
            output += "\nDica: instale com `pip install -U pymobiledevice3`."
    return truncate(output.strip() or "(sem saída)")


def capture_stream(args: Sequence[str], seconds: int) -> str:
    """Executa um comando contínuo (ex.: syslog live) por N segundos e devolve o que saiu."""
    try:
        result = subprocess.run(
            build_command(args),
            capture_output=True,
            text=True,
            timeout=seconds,
        )
        return (result.stdout or "") + _to_text(result.stderr)
    except subprocess.TimeoutExpired as exc:
        # Timeout é o caminho esperado: o processo é encerrado e ficamos com a saída parcial.
        return _to_text(exc.stdout) + _to_text(exc.stderr)
