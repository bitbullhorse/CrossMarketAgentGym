"""Serializable data-quality findings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["info", "warning", "error"]


class QualityIssue(BaseModel):
    """One aggregated, non-destructive quality finding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    severity: Severity
    message: str
    count: int = Field(ge=1)
    rows: list[int] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    file: str | None = None


class DataQualityReport(BaseModel):
    """All findings for a frame without dropping or repairing its rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    row_count: int = Field(ge=0)
    issues: list[QualityIssue] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return true when the report contains no error-severity finding."""
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def codes(self) -> set[str]:
        """Return issue codes for concise programmatic assertions."""
        return {issue.code for issue in self.issues}

    @property
    def error_count(self) -> int:
        """Return the number of affected rows/items across error findings."""
        return sum(issue.count for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        """Return the number of affected rows/items across warning findings."""
        return sum(issue.count for issue in self.issues if issue.severity == "warning")


class DataQualityError(ValueError):
    """Raised when callers explicitly require a valid frame."""

    def __init__(self, report: DataQualityReport) -> None:
        """Retain the complete report for audit and error handling."""
        self.report = report
        super().__init__(
            f"data quality validation failed with {report.error_count} affected items"
        )
