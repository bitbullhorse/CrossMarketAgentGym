from __future__ import annotations

import time
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field

from crossmarket_agentgym.agents.tools import (
    ToolDefinition,
    ToolExecutor,
    ToolPayload,
    ToolPolicy,
    ToolRegistry,
)


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: int = Field(ge=0)
    output_path: str | None = None


class ToolOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    doubled: int = Field(ge=0)


def _registry(
    handler: object,
    *,
    permission: str = "compute",
    timeout: float = 1.0,
) -> ToolRegistry:
    registry = ToolRegistry()
    definition = ToolDefinition.from_models(
        name="double",
        description="Double one non-negative integer.",
        input_model=ToolInput,
        output_model=ToolOutput,
        permission=permission,  # type: ignore[arg-type]
        timeout_seconds=timeout,
    )
    registry.register(
        definition,
        input_model=ToolInput,
        output_model=ToolOutput,
        handler=handler,  # type: ignore[arg-type]
    )
    return registry


def test_tool_executes_typed_python_handler() -> None:
    def handler(arguments: BaseModel) -> ToolOutput:
        typed = ToolInput.model_validate(arguments)
        return ToolOutput(doubled=typed.value * 2)

    executor = ToolExecutor(
        _registry(handler),
        ToolPolicy(allowed_permissions=frozenset({"compute"})),
        Path.cwd(),
    )
    result = executor.execute("double", {"value": 4})
    assert result.success is True
    assert result.data == {"doubled": 8}
    assert executor.total_calls == 1


def test_permissions_allowlist_and_budgets_fail_closed() -> None:
    called = False

    def handler(_arguments: BaseModel) -> ToolOutput:
        nonlocal called
        called = True
        return ToolOutput(doubled=2)

    denied = ToolExecutor(
        _registry(handler, permission="expensive"),
        ToolPolicy(
            allowed_permissions=frozenset({"read", "compute"}),
            max_expensive_calls=0,
        ),
        Path.cwd(),
    ).execute("double", {"value": 1})
    assert denied.error_code == "permission_denied"
    assert called is False

    executor = ToolExecutor(
        _registry(handler),
        ToolPolicy(
            allowed_permissions=frozenset({"compute"}),
            allowed_tools=frozenset({"double"}),
            max_total_calls=1,
        ),
        Path.cwd(),
    )
    assert executor.execute("double", {"value": 1}).success
    assert executor.execute("double", {"value": 1}).error_code == "call_budget_exhausted"
    assert executor.execute("missing", {}).error_code == "unknown_tool"


def test_tool_rejects_workspace_escape_and_invalid_schema(tmp_path: Path) -> None:
    def handler(arguments: BaseModel) -> ToolOutput:
        typed = ToolInput.model_validate(arguments)
        return ToolOutput(doubled=typed.value * 2)

    executor = ToolExecutor(
        _registry(handler),
        ToolPolicy(allowed_permissions=frozenset({"compute"})),
        tmp_path,
    )
    escaped = executor.execute(
        "double",
        {"value": 1, "output_path": "../outside.json"},
    )
    invalid = executor.execute("double", {"value": -1})
    assert escaped.error_code == "invalid_tool_input"
    assert invalid.error_code == "invalid_tool_input"


def test_tool_timeout_output_validation_and_error_redaction(tmp_path: Path) -> None:
    def slow(_arguments: BaseModel) -> ToolOutput:
        time.sleep(0.05)
        return ToolOutput(doubled=2)

    timed_out = ToolExecutor(
        _registry(slow, timeout=0.005),
        ToolPolicy(allowed_permissions=frozenset({"compute"})),
        tmp_path,
    ).execute("double", {"value": 1})
    assert timed_out.error_code == "tool_timeout"

    def invalid_output(_arguments: BaseModel) -> dict[str, int]:
        return {"doubled": -1}

    invalid = ToolExecutor(
        _registry(invalid_output),
        ToolPolicy(allowed_permissions=frozenset({"compute"})),
        tmp_path,
    ).execute("double", {"value": 1})
    assert invalid.error_code == "invalid_tool_output"

    def secret_error(_arguments: BaseModel) -> ToolOutput:
        raise RuntimeError("api_key=handler-secret")

    failed = ToolExecutor(
        _registry(secret_error),
        ToolPolicy(allowed_permissions=frozenset({"compute"})),
        tmp_path,
    ).execute("double", {"value": 1})
    assert failed.error_code == "tool_execution_failed"
    assert "handler-secret" not in (failed.error_message or "")


def test_tool_artifact_paths_must_stay_in_workspace(tmp_path: Path) -> None:
    def handler(_arguments: BaseModel) -> ToolPayload:
        return ToolPayload(
            data={"doubled": 2},
            artifact_paths=("../outside.json",),
        )

    result = ToolExecutor(
        _registry(handler),
        ToolPolicy(allowed_permissions=frozenset({"compute"})),
        tmp_path,
    ).execute("double", {"value": 1})
    assert result.error_code == "invalid_tool_output"


def test_duplicate_or_mismatched_registration_is_rejected() -> None:
    registry = _registry(lambda _arguments: {"doubled": 2})
    registered = registry.get("double")
    with pytest.raises(ValueError, match="already registered"):
        registry.register(
            registered.definition,
            input_model=ToolInput,
            output_model=ToolOutput,
            handler=lambda _arguments: {"doubled": 2},
        )
