"""Explicit dataset capabilities used to prevent partition confusion."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PartitionName = Literal["train", "validation", "test", "smoke"]


class PartitionCapability(BaseModel):
    """Immutable authority to use one closed transition interval."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str = Field(min_length=1)
    partition: PartitionName
    start_signal_index: int = Field(ge=0)
    end_execution_index: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_interval(self) -> PartitionCapability:
        """Require at least one signal-to-execution transition."""
        if self.start_signal_index >= self.end_execution_index:
            raise ValueError("partition must contain at least one transition")
        return self


class PartitionAccessError(PermissionError):
    """Raised when a workflow receives the wrong dataset capability."""


def require_partition(
    capability: PartitionCapability,
    allowed: frozenset[PartitionName],
) -> None:
    """Reject a partition unless the caller explicitly allows it."""
    if capability.partition not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise PartitionAccessError(
            f"partition {capability.partition!r} is not allowed; expected {allowed_text}"
        )
