"""Static guards for leakage and execution-boundary decisions."""

from __future__ import annotations

import ast
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def test_core_source_never_calls_eval() -> None:
    """Executable string evaluation is forbidden in core source."""
    offenders: list[str] = []
    for path in (PROJECT_ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "eval":
                    offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert offenders == []


def test_repository_artifacts_do_not_contain_api_key_values() -> None:
    """Configuration and source contain references, never credential values."""
    secret_pattern = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
    roots = [
        PROJECT_ROOT / "src",
        PROJECT_ROOT / "configs",
        PROJECT_ROOT / "docs",
    ]
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".md", ".yaml", ".yml", ".toml"}:
                if secret_pattern.search(path.read_text(encoding="utf-8")) is not None:
                    offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert offenders == []


def test_agent_tools_never_import_shell_execution_modules() -> None:
    """Registered tools must be Python callables, never user-text shell bridges."""
    offenders: list[str] = []
    root = PROJECT_ROOT / "src" / "crossmarket_agentgym" / "agents" / "tools"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name in {"subprocess", "shlex"} for alias in node.names):
                    offenders.append(str(path.relative_to(PROJECT_ROOT)))
            if isinstance(node, ast.ImportFrom) and node.module in {"subprocess", "shlex"}:
                offenders.append(str(path.relative_to(PROJECT_ROOT)))
    assert offenders == []


def test_agent_runtime_cannot_import_account_or_execution_state() -> None:
    """LLM orchestration may advise but cannot own deterministic account mutation."""
    offenders: list[str] = []
    root = PROJECT_ROOT / "src" / "crossmarket_agentgym" / "agents"
    forbidden_prefixes = (
        "crossmarket_agentgym.environments.account",
        "crossmarket_agentgym.environments.execution",
    )
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(
                    alias.name.startswith(forbidden_prefixes)
                    for alias in node.names
                ):
                    offenders.append(str(path.relative_to(PROJECT_ROOT)))
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                if node.module.startswith(forbidden_prefixes):
                    offenders.append(str(path.relative_to(PROJECT_ROOT)))
    assert offenders == []
