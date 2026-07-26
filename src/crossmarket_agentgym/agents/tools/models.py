"""Strict tool definitions, policies, and normalized results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ToolPermission = Literal["read", "compute", "write", "expensive"]


class StrictToolModel(BaseModel):
    """Reject unknown tool fields and runtime mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ToolDefinition(StrictToolModel):
    """Provider-visible schema and administrator permission classification."""

    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    description: str = Field(min_length=1)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    permission: ToolPermission
    timeout_seconds: float = Field(default=30.0, gt=0.0, le=3600.0)

    @classmethod
    def from_models(
        cls,
        *,
        name: str,
        description: str,
        input_model: type[BaseModel],
        output_model: type[BaseModel],
        permission: ToolPermission,
        timeout_seconds: float = 30.0,
    ) -> ToolDefinition:
        """Create advertised JSON schemas from executable Pydantic boundaries."""
        return cls(
            name=name,
            description=description,
            input_schema=input_model.model_json_schema(),
            output_schema=output_model.model_json_schema(),
            permission=permission,
            timeout_seconds=timeout_seconds,
        )


class ToolResult(StrictToolModel):
    """Uniform result returned for successes and all safe failures."""

    success: bool
    data: dict[str, Any] | None = None
    artifact_paths: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    error_code: str | None = None
    error_message: str | None = None
    duration_seconds: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def validate_status(self) -> ToolResult:
        """Keep success and error representations unambiguous."""
        if self.success and (self.error_code is not None or self.error_message is not None):
            raise ValueError("successful tool result cannot contain an error")
        if not self.success and (self.error_code is None or self.error_message is None):
            raise ValueError("failed tool result requires code and message")
        return self


class ToolPayload(StrictToolModel):
    """Optional handler wrapper for data, artifacts, and warnings."""

    data: dict[str, Any]
    artifact_paths: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class ToolPolicy(StrictToolModel):
    """Administrator-owned allowlist and per-session resource budget."""

    allowed_permissions: frozenset[ToolPermission] = frozenset({"read", "compute"})
    allowed_tools: frozenset[str] | None = None
    max_total_calls: int = Field(default=20, ge=0)
    max_expensive_calls: int = Field(default=0, ge=0)
    max_cumulative_seconds: float = Field(default=300.0, ge=0.0)
    require_budget_before_expensive: bool = False

    @field_validator("allowed_tools")
    @classmethod
    def validate_allowed_tools(
        cls,
        names: frozenset[str] | None,
    ) -> frozenset[str] | None:
        """Reject an empty explicit allowlist, which is usually a typo."""
        if names is not None and not names:
            raise ValueError("allowed_tools cannot be empty; use max_total_calls=0")
        return names
