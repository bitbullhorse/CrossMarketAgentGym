"""Search-space, trial, result, and study contracts."""

from __future__ import annotations

import ast
import math
import operator
import re
from itertools import product
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, model_validator

ParameterKind = Literal["float", "int", "categorical", "bool"]
Direction = Literal["maximize", "minimize"]
TrialStatus = Literal["pending", "running", "completed", "failed", "pruned"]
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ALLOWED_AST = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
)


class StrictTuningModel(BaseModel):
    """Reject unknown keys and mutation in tuning contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def expression_names(expression: str) -> set[str]:
    """Validate a restricted expression and return referenced parameter names."""
    tree = ast.parse(expression, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST):
            raise ValueError(f"unsupported expression element: {node.__class__.__name__}")
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


def evaluate_expression(expression: str, values: dict[str, Any]) -> bool:
    """Interpret a validated expression without dynamic code execution."""
    tree = ast.parse(expression, mode="eval")
    expression_names(expression)
    try:
        return bool(_interpret_expression(tree.body, values))
    except (KeyError, TypeError, ZeroDivisionError):
        return False


def _interpret_expression(node: ast.expr, values: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.BoolOp):
        interpreted = [_interpret_expression(value, values) for value in node.values]
        return all(interpreted) if isinstance(node.op, ast.And) else any(interpreted)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _interpret_expression(node.operand, values)
    if isinstance(node, ast.BinOp):
        operations = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Mod: operator.mod,
        }
        operation = operations[type(node.op)]
        return operation(
            _interpret_expression(node.left, values),
            _interpret_expression(node.right, values),
        )
    if isinstance(node, ast.Compare):
        comparisons = {
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.Lt: operator.lt,
            ast.LtE: operator.le,
            ast.Gt: operator.gt,
            ast.GtE: operator.ge,
        }
        left = _interpret_expression(node.left, values)
        for operation_node, comparator in zip(
            node.ops,
            node.comparators,
            strict=True,
        ):
            right = _interpret_expression(comparator, values)
            if not comparisons[type(operation_node)](left, right):
                return False
            left = right
        return True
    raise ValueError(f"unsupported expression element: {node.__class__.__name__}")


class ParameterSpec(StrictTuningModel):
    """One scalar, categorical, or conditional search parameter."""

    name: str
    kind: ParameterKind
    low: float | int | None = None
    high: float | int | None = None
    choices: tuple[Any, ...] | None = None
    log: bool = False
    step: float | int | None = None
    condition: str | None = None

    @model_validator(mode="after")
    def validate_specification(self) -> ParameterSpec:
        """Require exactly the bounds appropriate for the parameter kind."""
        if _NAME.fullmatch(self.name) is None:
            raise ValueError("parameter name is not a safe identifier")
        if self.kind in {"float", "int"}:
            if self.low is None or self.high is None or self.low >= self.high:
                raise ValueError("numeric parameters require low < high")
            if self.choices is not None:
                raise ValueError("numeric parameters cannot define choices")
            if self.log and self.low <= 0:
                raise ValueError("log-scaled parameters require low > 0")
            if self.step is not None and self.step <= 0:
                raise ValueError("step must be positive")
        elif self.kind == "categorical":
            if not self.choices:
                raise ValueError("categorical parameters require choices")
            if self.low is not None or self.high is not None:
                raise ValueError("categorical parameters cannot define bounds")
            if self.log or self.step is not None:
                raise ValueError("categorical parameters cannot use log or step")
        elif self.log or any(
            value is not None for value in (self.low, self.high, self.choices, self.step)
        ):
            raise ValueError("bool parameters do not define bounds, choices, or step")
        if self.condition is not None:
            expression_names(self.condition)
        return self

    def is_active(self, candidate: dict[str, Any]) -> bool:
        """Return whether the conditional parameter is active."""
        return self.condition is None or evaluate_expression(self.condition, candidate)

    def from_unit(self, value: float) -> Any:
        """Decode a clipped unit coordinate into this parameter."""
        unit = float(np.clip(value, 0.0, 1.0))
        if self.kind == "bool":
            return unit >= 0.5
        if self.kind == "categorical":
            assert self.choices is not None
            index = min(int(unit * len(self.choices)), len(self.choices) - 1)
            return self.choices[index]
        assert self.low is not None and self.high is not None
        if self.log:
            raw = math.exp(math.log(float(self.low)) + unit * (
                math.log(float(self.high)) - math.log(float(self.low))
            ))
        else:
            raw = float(self.low) + unit * (float(self.high) - float(self.low))
        if self.step is not None:
            raw = float(self.low) + round(
                (raw - float(self.low)) / float(self.step)
            ) * float(self.step)
        raw = float(np.clip(raw, float(self.low), float(self.high)))
        return int(round(raw)) if self.kind == "int" else raw

    def to_unit(self, value: Any) -> float:
        """Encode one parameter value into `[0,1]`."""
        if self.kind == "bool":
            return 1.0 if bool(value) else 0.0
        if self.kind == "categorical":
            assert self.choices is not None
            try:
                index = self.choices.index(value)
            except ValueError as error:
                raise ValueError(f"{self.name} is not an allowed choice") from error
            return index / max(1, len(self.choices) - 1)
        assert self.low is not None and self.high is not None
        numeric = float(value)
        if numeric < float(self.low) or numeric > float(self.high):
            raise ValueError(f"{self.name} is outside bounds")
        if self.log:
            return (math.log(numeric) - math.log(float(self.low))) / (
                math.log(float(self.high)) - math.log(float(self.low))
            )
        return (numeric - float(self.low)) / (float(self.high) - float(self.low))

    def grid_values(self) -> tuple[Any, ...]:
        """Return a finite deterministic grid for this parameter."""
        if self.kind == "bool":
            return (False, True)
        if self.kind == "categorical":
            assert self.choices is not None
            return self.choices
        assert self.low is not None and self.high is not None
        if self.step is None:
            return (self.from_unit(0.0), self.from_unit(0.5), self.from_unit(1.0))
        count = int(math.floor(
            (float(self.high) - float(self.low)) / float(self.step)
        ))
        return tuple(
            self.from_unit(index / max(1, count))
            for index in range(count + 1)
        )


class SearchSpace(StrictTuningModel):
    """Ordered mixed search space with safe conditional constraints."""

    parameters: tuple[ParameterSpec, ...]
    constraints: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_space(self) -> SearchSpace:
        """Validate names, condition ordering, and constraint references."""
        if not self.parameters:
            raise ValueError("search space requires at least one parameter")
        names = [parameter.name for parameter in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("parameter names must be unique")
        known: set[str] = set()
        for parameter in self.parameters:
            if (
                parameter.condition is not None
                and not expression_names(parameter.condition) <= known
            ):
                raise ValueError("parameter condition must reference earlier parameters")
            known.add(parameter.name)
        for constraint in self.constraints:
            if not expression_names(constraint) <= set(names):
                raise ValueError("constraint references an unknown parameter")
        return self

    @property
    def dimension(self) -> int:
        """Return fixed optimizer dimension including conditional coordinates."""
        return len(self.parameters)

    def decode(self, vector: NDArray[np.floating[Any]]) -> dict[str, Any]:
        """Decode a unit vector and reject invalid constrained candidates."""
        values = np.asarray(vector, dtype=np.float64)
        if values.shape != (self.dimension,) or not np.isfinite(values).all():
            raise ValueError("candidate vector has invalid shape or values")
        candidate: dict[str, Any] = {}
        for index, parameter in enumerate(self.parameters):
            if parameter.is_active(candidate):
                candidate[parameter.name] = parameter.from_unit(float(values[index]))
        self.validate_candidate(candidate)
        return candidate

    def encode(self, candidate: dict[str, Any]) -> NDArray[np.float64]:
        """Encode and validate a candidate into one unit vector."""
        self.validate_candidate(candidate)
        vector = np.full(self.dimension, 0.5, dtype=np.float64)
        partial: dict[str, Any] = {}
        for index, parameter in enumerate(self.parameters):
            if parameter.is_active(partial):
                vector[index] = parameter.to_unit(candidate[parameter.name])
                partial[parameter.name] = candidate[parameter.name]
        return vector

    def validate_candidate(self, candidate: dict[str, Any]) -> None:
        """Reject missing, inactive, out-of-range, or constrained candidates."""
        partial: dict[str, Any] = {}
        for parameter in self.parameters:
            active = parameter.is_active(partial)
            present = parameter.name in candidate
            if active and not present:
                raise ValueError(f"active parameter {parameter.name} is missing")
            if not active and present:
                raise ValueError(f"inactive parameter {parameter.name} is present")
            if active:
                parameter.to_unit(candidate[parameter.name])
                partial[parameter.name] = candidate[parameter.name]
        unknown = set(candidate) - {item.name for item in self.parameters}
        if unknown:
            raise ValueError(f"candidate contains unknown parameters: {sorted(unknown)}")
        for constraint in self.constraints:
            if not evaluate_expression(constraint, candidate):
                raise ValueError(f"candidate violates constraint: {constraint}")

    def sample(self, rng: np.random.Generator) -> dict[str, Any]:
        """Draw a valid random candidate with bounded retry."""
        for _ in range(1000):
            vector = rng.random(self.dimension)
            try:
                return self.decode(vector)
            except ValueError:
                continue
        raise RuntimeError("could not sample a valid constrained candidate")

    def grid(self, max_candidates: int = 100_000) -> list[dict[str, Any]]:
        """Materialize a deterministic finite grid with constraint filtering."""
        combinations = product(*(parameter.grid_values() for parameter in self.parameters))
        candidates: list[dict[str, Any]] = []
        for values in combinations:
            candidate: dict[str, Any] = {}
            for parameter, value in zip(self.parameters, values, strict=True):
                if parameter.is_active(candidate):
                    candidate[parameter.name] = value
            try:
                self.validate_candidate(candidate)
            except ValueError:
                continue
            candidates.append(candidate)
            if len(candidates) > max_candidates:
                raise ValueError("grid exceeds configured candidate limit")
        if not candidates:
            raise ValueError("search-space grid contains no valid candidates")
        return candidates


class TrialSuggestion(StrictTuningModel):
    """One candidate emitted by a search algorithm."""

    schema_version: Literal["1.0"] = "1.0"
    trial_id: int = Field(ge=0)
    parameters: dict[str, Any]
    generation: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrialResult(StrictTuningModel):
    """Completed, failed, or pruned trial result."""

    schema_version: Literal["1.0"] = "1.0"
    trial_id: int = Field(ge=0)
    parameters: dict[str, Any]
    status: TrialStatus
    objectives: tuple[float, ...] = ()
    metrics: dict[str, float] = Field(default_factory=dict)
    resource: float = Field(default=0.0, ge=0.0)
    error: str | None = None

    @model_validator(mode="after")
    def validate_result(self) -> TrialResult:
        """Require finite objectives only for completed trials."""
        if self.status == "completed":
            if not self.objectives or not all(math.isfinite(value) for value in self.objectives):
                raise ValueError("completed trials require finite objectives")
            if self.error is not None:
                raise ValueError("completed trials cannot contain an error")
        elif self.status == "failed" and not self.error:
            raise ValueError("failed trials require an error")
        return self


class StudyState(StrictTuningModel):
    """Search history visible to initialization and reports."""

    schema_version: Literal["1.0"] = "1.0"
    study_name: str = Field(min_length=1)
    directions: tuple[Direction, ...] = ("maximize",)
    results: tuple[TrialResult, ...] = ()

    @model_validator(mode="after")
    def validate_directions(self) -> StudyState:
        """Require at least one objective direction."""
        if not self.directions:
            raise ValueError("study requires at least one objective")
        return self


def scalar_utility(result: TrialResult, directions: tuple[Direction, ...]) -> float:
    """Convert the first objective into a maximize-oriented utility."""
    if result.status != "completed":
        return -math.inf
    sign = 1.0 if directions[0] == "maximize" else -1.0
    return sign * result.objectives[0]


def dominates(
    first: TrialResult,
    second: TrialResult,
    directions: tuple[Direction, ...],
) -> bool:
    """Return Pareto dominance under mixed objective directions."""
    if first.status != "completed" or second.status != "completed":
        return False
    if len(first.objectives) != len(directions) or len(second.objectives) != len(directions):
        raise ValueError("objective count does not match directions")
    first_values = [
        value if direction == "maximize" else -value
        for value, direction in zip(first.objectives, directions, strict=True)
    ]
    second_values = [
        value if direction == "maximize" else -value
        for value, direction in zip(second.objectives, directions, strict=True)
    ]
    return all(a >= b for a, b in zip(first_values, second_values, strict=True)) and any(
        a > b for a, b in zip(first_values, second_values, strict=True)
    )
