"""Deterministic Phase 10 public-API and Schema freeze artifacts."""

from __future__ import annotations

import ast
import csv
import hashlib
import importlib
import inspect
import io
import json
import re
from pathlib import Path
from typing import Any, Literal

import click
from pydantic import BaseModel
from typer.main import get_command

from crossmarket_agentgym import __version__
from crossmarket_agentgym.cli.app import app
from crossmarket_agentgym.release.models import (
    ContractFreezeResult,
    VerificationCheck,
)
from crossmarket_agentgym.release.versioning import release_label

Stability = Literal["stable", "provisional", "experimental", "internal"]
_SINCE = "1.0.0rc1"
_UNORDERED_LITERAL = re.compile(r"(frozenset|set)\(\{([^{}]*)\}\)")

_CONFIG_SCHEMAS: dict[str, str] = {
    "project": "crossmarket_agentgym.config.models:RootConfig",
    "data_validation": "crossmarket_agentgym.data.config:DataValidationConfig",
    "environment_check": (
        "crossmarket_agentgym.environments.checks:EnvironmentCheckConfig"
    ),
    "environment": "crossmarket_agentgym.environments.config:EnvironmentConfig",
    "training": "crossmarket_agentgym.rl.config:TrainRunConfig",
    "provider_check": "crossmarket_agentgym.agents.config:ProviderCheckConfig",
    "agent_runtime": "crossmarket_agentgym.agents.models:AgentRuntimeConfig",
    "three_layer_agent": "crossmarket_agentgym.agents.layer_config:Phase7RunConfig",
    "tuning": "crossmarket_agentgym.tuning.config:TuningRunConfig",
    "softwarex_reporting": (
        "crossmarket_agentgym.reporting.models:SoftwareXReportConfig"
    ),
    "report_service": "crossmarket_agentgym.api.config:ServiceConfig",
}

_ARTIFACT_SCHEMAS: dict[str, str] = {
    "dataset_manifest": (
        "crossmarket_agentgym.data.manifests.models:DatasetManifest"
    ),
    "ohlcv_record": "crossmarket_agentgym.data.schemas.ohlcv:OHLCVRecord",
    "training_metadata": "crossmarket_agentgym.rl.artifacts:TrainingMetadata",
    "training_summary": "crossmarket_agentgym.rl.workflow:TrainingRunSummary",
    "evaluation_result": "crossmarket_agentgym.evaluation.results:EvaluationResult",
    "provider_message": (
        "crossmarket_agentgym.agents.providers.models:Message"
    ),
    "provider_response": (
        "crossmarket_agentgym.agents.providers.models:LLMResponse"
    ),
    "provider_replay": "crossmarket_agentgym.agents.providers.replay:ReplayRecord",
    "team_result": "crossmarket_agentgym.agents.models:TeamRunResult",
    "directive_record": "crossmarket_agentgym.audit.directives:DirectiveRecord",
    "phase7_summary": "crossmarket_agentgym.agents.layer_stack:Phase7RunSummary",
    "trial_suggestion": "crossmarket_agentgym.tuning.models:TrialSuggestion",
    "trial_result": "crossmarket_agentgym.tuning.models:TrialResult",
    "study_state": "crossmarket_agentgym.tuning.models:StudyState",
    "tuning_summary": "crossmarket_agentgym.tuning.workflow:TuningRunSummary",
    "run_manifest": "crossmarket_agentgym.audit.run_manifest:RunManifest",
    "run_index": "crossmarket_agentgym.reporting.models:RunIndex",
    "report_manifest": "crossmarket_agentgym.reporting.models:ReportManifest",
    "release_manifest": (
        "crossmarket_agentgym.release.models:DistributionManifest"
    ),
    "reproduction_result": (
        "crossmarket_agentgym.release.models:ReproductionResult"
    ),
}


def _check(name: str, passed: bool, detail: str) -> VerificationCheck:
    return VerificationCheck(name=name, passed=passed, detail=detail)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _module_name(path: Path, source_root: Path) -> str:
    relative = path.relative_to(source_root.parent).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _stability(module: str, name: str) -> Stability:
    if (
        module == "crossmarket_agentgym.api"
        or name in {"IRMoEPolicyAdapter", "RayTrialExecutor"}
    ):
        return "experimental"
    provisional_fragments = (
        ".adapters",
        ".aggregation",
        ".calendars",
        ".callbacks",
        ".executors",
        ".fx",
        ".policies",
        ".providers",
        ".quality",
        ".reports",
        ".roles",
        ".schedulers",
        ".searchers",
        ".tools",
        ".trainers",
    )
    if module in {"crossmarket_agentgym.audit", "crossmarket_agentgym.reporting"}:
        return "provisional"
    if any(fragment in module for fragment in provisional_fragments):
        return "provisional"
    return "stable"


def _kind(value: Any) -> str:
    if inspect.isclass(value):
        return "class"
    if inspect.isfunction(value):
        return "function"
    if callable(value):
        return "callable"
    return "constant_or_type_alias"


def _annotation_text(annotation: Any) -> str:
    if inspect.isclass(annotation):
        module = getattr(annotation, "__module__", "")
        name = getattr(annotation, "__qualname__", str(annotation))
        return name if module == "builtins" else f"{module}.{name}"
    return str(annotation).replace("typing.", "")


def _default_text(value: Any) -> str:
    if isinstance(value, set | frozenset):
        name = "frozenset" if isinstance(value, frozenset) else "set"
        content = ", ".join(sorted(repr(item) for item in value))
        return f"{name}({{{content}}})"
    if isinstance(value, dict):
        content = ", ".join(
            f"{key!r}: {_default_text(item)}"
            for key, item in sorted(value.items(), key=lambda pair: repr(pair[0]))
        )
        return f"{{{content}}}"
    return repr(value)


def _pydantic_signature(model: type[BaseModel]) -> str:
    parts: list[str] = []
    for name, field in model.model_fields.items():
        item = f"{name}: {_annotation_text(field.annotation)}"
        if not field.is_required():
            if field.default_factory is not None:
                item += " = <factory>"
            else:
                item += f" = {_default_text(field.default)}"
        parts.append(item)
    return f"(*, {', '.join(parts)})"


def _summary(value: Any) -> str:
    documentation = inspect.getdoc(value)
    return documentation.splitlines()[0] if documentation else ""


def _signature(value: Any) -> str:
    if inspect.isclass(value) and issubclass(value, BaseModel):
        return _pydantic_signature(value)
    try:
        signature = str(inspect.signature(value))
    except (TypeError, ValueError):
        return ""
    return _UNORDERED_LITERAL.sub(_sort_unordered_literal, signature)


def _sort_unordered_literal(match: re.Match[str]) -> str:
    items = [item.strip() for item in match.group(2).split(",") if item.strip()]
    return f"{match.group(1)}({{{', '.join(sorted(items))}}})"


def _api_rows(workspace: Path) -> list[dict[str, str]]:
    source_root = workspace / "src" / "crossmarket_agentgym"
    rows: list[dict[str, str]] = []
    for path in sorted(source_root.rglob("__init__.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        exports: list[str] | None = None
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "__all__"
                    for target in node.targets
                )
            ):
                exports = ast.literal_eval(node.value)
        if not exports:
            continue
        module = _module_name(path, source_root)
        imported = importlib.import_module(module)
        for name in exports:
            value = getattr(imported, name)
            stability = _stability(module, name)
            rows.append(
                {
                    "qualified_name": f"{module}.{name}",
                    "module": module,
                    "name": name,
                    "kind": _kind(value),
                    "stability": stability,
                    "since": _SINCE,
                    "signature": _signature(value),
                    "deprecated": "false",
                    "summary": _summary(value),
                    "notes": (
                        "not a supported public import"
                        if stability == "internal"
                        else ""
                    ),
                }
            )
    return sorted(rows, key=lambda row: row["qualified_name"])


def _render_csv(rows: list[dict[str, str]], fieldnames: tuple[str, ...]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def _api_csv(workspace: Path) -> str:
    return _render_csv(
        _api_rows(workspace),
        (
            "qualified_name",
            "module",
            "name",
            "kind",
            "stability",
            "since",
            "signature",
            "deprecated",
            "summary",
            "notes",
        ),
    )


def _json_default(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _parameter_type_text(value: Any) -> str:
    name = f"{value.__class__.__module__}.{value.__class__.__qualname__}"
    attributes: list[str] = []
    for field in (
        "min",
        "max",
        "clamp",
        "case_sensitive",
        "exists",
        "file_okay",
        "dir_okay",
        "readable",
        "writable",
        "resolve_path",
        "allow_dash",
    ):
        if hasattr(value, field):
            attributes.append(f"{field}={_json_default(getattr(value, field))!r}")
    return f"{name}({', '.join(attributes)})" if attributes else name


def _cli_inventory_text() -> str:
    records: list[dict[str, Any]] = []

    def visit(command: click.Command, path: tuple[str, ...]) -> None:
        parameters: list[dict[str, Any]] = []
        for parameter in command.params:
            parameters.append(
                {
                    "name": parameter.name,
                    "kind": (
                        "option"
                        if isinstance(parameter, click.Option)
                        else "argument"
                    ),
                    "options": list(getattr(parameter, "opts", ())),
                    "secondary_options": list(
                        getattr(parameter, "secondary_opts", ())
                    ),
                    "required": bool(parameter.required),
                    "default": _json_default(parameter.default),
                    "type": _parameter_type_text(parameter.type),
                    "nargs": parameter.nargs,
                }
            )
        records.append(
            {
                "command": " ".join(path),
                "help": command.help or "",
                "hidden": bool(command.hidden),
                "parameters": parameters,
            }
        )
        if isinstance(command, click.Group):
            for name, child in sorted(command.commands.items()):
                visit(child, (*path, name))

    visit(get_command(app), ("cmag",))
    payload = {
        "schema_version": "1.0",
        "release": release_label(__version__),
        "commands": records,
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _stable_api_markdown(rows: list[dict[str, str]]) -> str:
    lines = [
        "# Stable Python API catalog",
        "",
        "Generated from reviewed `__all__` exports for v1.0.0-rc1. "
        "Schemas carry field-level constraints.",
        "",
    ]
    for row in rows:
        if row["stability"] != "stable":
            continue
        lines.extend(
            [
                f"## `{row['qualified_name']}`",
                "",
                row["summary"] or "Stable exported integration symbol.",
                "",
                f"```text\n{row['signature'] or row['kind']}\n```",
                "",
            ]
        )
    return "\n".join(lines)


def _load_model(qualified: str) -> type[BaseModel]:
    module_name, class_name = qualified.split(":", maxsplit=1)
    value = getattr(importlib.import_module(module_name), class_name)
    if not isinstance(value, type) or not issubclass(value, BaseModel):
        raise TypeError(f"{qualified} is not a Pydantic model")
    return value


def _canonicalize_schema(value: Any) -> Any:
    if isinstance(value, dict):
        normalized = {
            key: _canonicalize_schema(item)
            for key, item in value.items()
        }
        default = normalized.get("default")
        if normalized.get("uniqueItems") is True and isinstance(default, list):
            normalized["default"] = sorted(
                default,
                key=lambda item: json.dumps(item, sort_keys=True),
            )
        return normalized
    if isinstance(value, list):
        return [_canonicalize_schema(item) for item in value]
    return value


def _schema_text(model: type[BaseModel]) -> str:
    return (
        json.dumps(
            _canonicalize_schema(model.model_json_schema()),
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _schema_documents() -> dict[str, str]:
    documents: dict[str, str] = {}
    for category, registry in (
        ("configs", _CONFIG_SCHEMAS),
        ("artifacts", _ARTIFACT_SCHEMAS),
    ):
        for name, qualified in registry.items():
            documents[f"{category}/{name}.schema.json"] = _schema_text(
                _load_model(qualified)
            )
    return documents


def _schema_inventory(documents: dict[str, str]) -> str:
    rows: list[dict[str, str]] = []
    for category, registry in (
        ("config", _CONFIG_SCHEMAS),
        ("artifact", _ARTIFACT_SCHEMAS),
    ):
        directory = f"{category}s"
        for name, qualified in registry.items():
            relative = f"{directory}/{name}.schema.json"
            rows.append(
                {
                    "category": category,
                    "name": name,
                    "qualified_name": qualified.replace(":", "."),
                    "contract_version": "1.0",
                    "schema_path": f"schemas/rc1/{relative}",
                    "sha256": _sha256_text(documents[relative]),
                }
            )
    return _render_csv(
        rows,
        (
            "category",
            "name",
            "qualified_name",
            "contract_version",
            "schema_path",
            "sha256",
        ),
    )


def _checksums_text(documents: dict[str, str]) -> str:
    payload = {
        "schema_version": "1.0",
        "release": release_label(__version__),
        "files": {
            path: _sha256_text(text)
            for path, text in sorted(documents.items())
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _format_registry_text(documents: dict[str, str]) -> str:
    formats: list[dict[str, object]] = [
        {
            "name": name,
            "version": "1.0",
            "storage": "json_or_jsonl",
            "schema_path": f"schemas/rc1/artifacts/{name}.schema.json",
            "schema_sha256": _sha256_text(documents[f"artifacts/{name}.schema.json"]),
        }
        for name in sorted(_ARTIFACT_SCHEMAS)
    ]
    formats.append(
        {
            "name": "hpo_sqlite",
            "version": "1",
            "storage": "sqlite",
            "schema_path": None,
            "schema_sha256": None,
        }
    )
    payload = {
        "schema_version": "1.0",
        "release": release_label(__version__),
        "unlisted_interfaces": "internal",
        "formats": formats,
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def export_frozen_contracts(workspace_root: str | Path = ".") -> ContractFreezeResult:
    """Write the reviewed rc1 API inventory and canonical Schema snapshots."""
    workspace = Path(workspace_root).resolve()
    documents = _schema_documents()
    api_rows = _api_rows(workspace)
    api_text = _render_csv(
        api_rows,
        (
            "qualified_name",
            "module",
            "name",
            "kind",
            "stability",
            "since",
            "signature",
            "deprecated",
            "summary",
            "notes",
        ),
    )
    targets = {
        workspace / "release" / "api_inventory.csv": api_text,
        workspace / "release" / "cli_inventory.json": _cli_inventory_text(),
        workspace / "docs" / "stable-api.md": _stable_api_markdown(api_rows),
        workspace / "release" / "config_schema_inventory.csv": (
            _schema_inventory(documents)
        ),
        workspace / "release" / "format_registry.json": (
            _format_registry_text(documents)
        ),
        workspace / "schemas" / "rc1" / "checksums.json": (
            _checksums_text(documents)
        ),
    }
    for relative, text in documents.items():
        targets[workspace / "schemas" / "rc1" / relative] = text
    for path, text in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return ContractFreezeResult(
        release=release_label(__version__),
        api_records=len(api_rows),
        config_schemas=len(_CONFIG_SCHEMAS),
        artifact_schemas=len(_ARTIFACT_SCHEMAS),
        is_valid=True,
        wrote_files=True,
        checks=(
            _check("api_inventory", True, "public exports classified and written"),
            _check("cli_inventory", True, "command and parameter tree written"),
            _check("schema_snapshots", True, "canonical JSON Schemas written"),
            _check("format_registry", True, "persisted formats versioned"),
        ),
    )


def verify_frozen_contracts(workspace_root: str | Path = ".") -> ContractFreezeResult:
    """Fail when code exports or Schemas drift from the reviewed rc1 files."""
    workspace = Path(workspace_root).resolve()
    documents = _schema_documents()
    api_rows = _api_rows(workspace)
    expected: dict[Path, str] = {
        workspace / "release" / "api_inventory.csv": _render_csv(
            api_rows,
            (
                "qualified_name",
                "module",
                "name",
                "kind",
                "stability",
                "since",
                "signature",
                "deprecated",
                "summary",
                "notes",
            ),
        ),
        workspace / "release" / "cli_inventory.json": _cli_inventory_text(),
        workspace / "docs" / "stable-api.md": _stable_api_markdown(api_rows),
        workspace / "release" / "config_schema_inventory.csv": (
            _schema_inventory(documents)
        ),
        workspace / "release" / "format_registry.json": (
            _format_registry_text(documents)
        ),
        workspace / "schemas" / "rc1" / "checksums.json": (
            _checksums_text(documents)
        ),
    }
    for relative, text in documents.items():
        expected[workspace / "schemas" / "rc1" / relative] = text
    missing: list[str] = []
    changed: list[str] = []
    for path, text in expected.items():
        relative = path.relative_to(workspace).as_posix()
        if not path.is_file():
            missing.append(relative)
        elif path.read_text(encoding="utf-8") != text:
            changed.append(relative)
    schema_root = workspace / "schemas" / "rc1"
    actual_schema_files = (
        {
            path.relative_to(workspace).as_posix()
            for path in schema_root.rglob("*.json")
        }
        if schema_root.is_dir()
        else set()
    )
    expected_schema_files = {
        path.relative_to(workspace).as_posix()
        for path in expected
        if path.is_relative_to(schema_root)
    }
    extras = sorted(actual_schema_files - expected_schema_files)
    checks = (
        _check(
            "frozen_files_present",
            not missing,
            "all freeze files present" if not missing else f"missing: {missing}",
        ),
        _check(
            "frozen_files_unchanged",
            not changed,
            "API and Schema content matches code"
            if not changed
            else f"changed: {changed}",
        ),
        _check(
            "frozen_schema_set",
            not extras,
            "no unregistered Schema snapshot"
            if not extras
            else f"extra: {extras}",
        ),
    )
    return ContractFreezeResult(
        release=release_label(__version__),
        api_records=len(api_rows),
        config_schemas=len(_CONFIG_SCHEMAS),
        artifact_schemas=len(_ARTIFACT_SCHEMAS),
        is_valid=all(check.passed for check in checks),
        wrote_files=False,
        checks=checks,
    )
