"""Python-only tool registry with schema, permission, path, and timeout guards."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ValidationError

from crossmarket_agentgym.agents.tools.models import (
    ToolDefinition,
    ToolPayload,
    ToolPolicy,
    ToolResult,
)
from crossmarket_agentgym.audit.logging import redact_secrets, redact_value

ToolHandler = Callable[[BaseModel], BaseModel | ToolPayload | dict[str, Any]]


@dataclass(frozen=True)
class RegisteredTool:
    """Executable handler kept separate from provider-visible metadata."""

    definition: ToolDefinition
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: ToolHandler


class ToolRegistry:
    """Explicit registry; user text can never become a shell command."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        definition: ToolDefinition,
        *,
        input_model: type[BaseModel],
        output_model: type[BaseModel],
        handler: ToolHandler,
    ) -> None:
        """Register one typed Python callable under a unique stable name."""
        if definition.name in self._tools:
            raise ValueError(f"tool already registered: {definition.name}")
        if definition.input_schema != input_model.model_json_schema():
            raise ValueError("tool input schema does not match input model")
        if definition.output_schema != output_model.model_json_schema():
            raise ValueError("tool output schema does not match output model")
        self._tools[definition.name] = RegisteredTool(
            definition=definition,
            input_model=input_model,
            output_model=output_model,
            handler=handler,
        )

    def get(self, name: str) -> RegisteredTool:
        """Return one registered tool or fail without fuzzy matching."""
        try:
            return self._tools[name]
        except KeyError as error:
            raise KeyError(f"unknown tool: {name}") from error

    def definitions(self, names: list[str] | None = None) -> list[ToolDefinition]:
        """Return stable provider-visible definitions."""
        selected = sorted(self._tools) if names is None else names
        return [self.get(name).definition for name in selected]


def _is_path_key(key: str) -> bool:
    lowered = key.lower()
    return (
        lowered in {"path", "file", "directory", "root"}
        or lowered.endswith(
            (
                "_path",
                "_paths",
                "_file",
                "_files",
                "_dir",
                "_dirs",
                "_root",
                "_roots",
            )
        )
    )


def _validate_workspace_paths(
    value: Any,
    workspace_root: Path,
    *,
    key: str = "",
) -> None:
    if isinstance(value, dict):
        for nested_key, nested_value in value.items():
            _validate_workspace_paths(
                nested_value,
                workspace_root,
                key=str(nested_key),
            )
        return
    if isinstance(value, list | tuple):
        for item in value:
            _validate_workspace_paths(item, workspace_root, key=key)
        return
    if not _is_path_key(key) or not isinstance(value, str):
        return
    candidate = Path(value)
    resolved = (
        candidate.resolve()
        if candidate.is_absolute()
        else (workspace_root / candidate).resolve()
    )
    if not resolved.is_relative_to(workspace_root):
        raise PermissionError(f"path for {key!r} leaves the configured workspace")


class ToolExecutor:
    """Stateful per-session permission and resource enforcement."""

    def __init__(
        self,
        registry: ToolRegistry,
        policy: ToolPolicy,
        workspace_root: str | Path,
    ) -> None:
        self.registry = registry
        self.policy = policy
        self.workspace_root = Path(workspace_root).resolve()
        self.total_calls = 0
        self.expensive_calls = 0
        self.cumulative_seconds = 0.0
        self.budget_estimated = False

    def _denied(self, code: str, message: str, started: float) -> ToolResult:
        return ToolResult(
            success=False,
            error_code=code,
            error_message=redact_secrets(message),
            duration_seconds=perf_counter() - started,
        )

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Validate then execute one registered Python handler."""
        started = perf_counter()
        try:
            registered = self.registry.get(name)
        except KeyError:
            return self._denied("unknown_tool", f"unknown tool: {name}", started)
        definition = registered.definition
        if definition.permission not in self.policy.allowed_permissions:
            return self._denied(
                "permission_denied",
                f"permission {definition.permission!r} is not allowed",
                started,
            )
        if (
            self.policy.allowed_tools is not None
            and name not in self.policy.allowed_tools
        ):
            return self._denied("tool_not_allowed", f"tool {name!r} is not allowed", started)
        if self.total_calls >= self.policy.max_total_calls:
            return self._denied("call_budget_exhausted", "tool call budget exhausted", started)
        if (
            definition.permission == "expensive"
            and self.expensive_calls >= self.policy.max_expensive_calls
        ):
            return self._denied(
                "expensive_budget_exhausted",
                "expensive tool budget exhausted",
                started,
            )
        if (
            definition.permission == "expensive"
            and self.policy.require_budget_before_expensive
            and not self.budget_estimated
        ):
            return self._denied(
                "budget_estimate_required",
                "estimate_compute_budget must succeed before an expensive tool",
                started,
            )
        if self.cumulative_seconds >= self.policy.max_cumulative_seconds:
            return self._denied("time_budget_exhausted", "tool time budget exhausted", started)
        try:
            _validate_workspace_paths(arguments, self.workspace_root)
            validated_input = registered.input_model.model_validate(arguments)
        except (PermissionError, ValidationError) as error:
            return self._denied("invalid_tool_input", str(error), started)

        self.total_calls += 1
        if definition.permission == "expensive":
            self.expensive_calls += 1
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"tool-{name}")
        future = executor.submit(registered.handler, validated_input)
        try:
            raw_output = future.result(timeout=definition.timeout_seconds)
            payload = (
                raw_output
                if isinstance(raw_output, ToolPayload)
                else ToolPayload(
                    data=(
                        raw_output.model_dump(mode="json")
                        if isinstance(raw_output, BaseModel)
                        else raw_output
                    )
                )
            )
            validated_output = registered.output_model.model_validate(payload.data)
            _validate_workspace_paths(payload.artifact_paths, self.workspace_root, key="path")
            duration = perf_counter() - started
            self.cumulative_seconds += duration
            if name == "estimate_compute_budget":
                self.budget_estimated = True
            return ToolResult(
                success=True,
                data=redact_value(validated_output.model_dump(mode="json")),
                artifact_paths=payload.artifact_paths,
                warnings=tuple(redact_secrets(item) for item in payload.warnings),
                duration_seconds=duration,
            )
        except TimeoutError:
            future.cancel()
            duration = perf_counter() - started
            self.cumulative_seconds += duration
            return ToolResult(
                success=False,
                error_code="tool_timeout",
                error_message="tool execution exceeded its configured timeout",
                duration_seconds=duration,
            )
        except (ValidationError, PermissionError) as error:
            duration = perf_counter() - started
            self.cumulative_seconds += duration
            return ToolResult(
                success=False,
                error_code="invalid_tool_output",
                error_message=redact_secrets(str(error)),
                duration_seconds=duration,
            )
        except Exception as error:
            duration = perf_counter() - started
            self.cumulative_seconds += duration
            return ToolResult(
                success=False,
                error_code="tool_execution_failed",
                error_message=redact_secrets(
                    f"{error.__class__.__name__}: {error}"
                ),
                duration_seconds=duration,
            )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
