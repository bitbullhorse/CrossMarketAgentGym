"""Optional FastAPI application for reports and guarded local GUI jobs."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

from crossmarket_agentgym import __version__
from crossmarket_agentgym.api.config import GUIServiceConfig, ServiceConfig
from crossmarket_agentgym.api.jobs import (
    ConfigKind,
    ConfigValidationRequest,
    JobManager,
    JobRequest,
    job_record_json,
    list_configurations,
    read_configuration,
    validate_configuration,
)
from crossmarket_agentgym.reporting.indexer import build_run_index
from crossmarket_agentgym.reporting.io import read_bounded_json, resolve_inside

_PORTABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_PUBLIC_SUFFIXES = frozenset({".csv", ".json", ".md", ".svg"})


def _service_dependencies() -> tuple[Any, Any, Any, Any, Any, Any]:
    try:
        from fastapi import FastAPI, HTTPException, Query
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import FileResponse, RedirectResponse
    except ImportError as error:
        raise RuntimeError(
            "Phase 8 service requires: pip install 'crossmarket-agent-gym[service]'"
        ) from error
    return (
        FastAPI,
        HTTPException,
        Query,
        FileResponse,
        RedirectResponse,
        CORSMiddleware,
    )


def create_app(config: ServiceConfig) -> Any:
    """Create an app without mutating runs or exposing arbitrary files."""
    (
        FastAPI,
        HTTPException,
        Query,
        FileResponse,
        RedirectResponse,
        CORSMiddleware,
    ) = _service_dependencies()
    workspace = config.workspace_root.resolve()
    runs_root = resolve_inside(config.runs_root, workspace)
    reports_root = resolve_inside(config.reports_root, workspace)
    gui_config = config if isinstance(config, GUIServiceConfig) else None
    execution_enabled = gui_config is not None
    job_manager = (
        JobManager(
            workspace,
            max_concurrent_jobs=gui_config.max_concurrent_jobs,
            max_log_bytes=gui_config.max_job_log_bytes,
        )
        if gui_config is not None
        else None
    )

    @asynccontextmanager
    async def lifespan(_: Any) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if job_manager is not None:
                job_manager.shutdown()

    app = FastAPI(
        title="CrossMarketAgentGym local research service",
        version=__version__,
        docs_url="/docs" if config.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if config.docs_enabled else None,
        lifespan=lifespan,
    )
    if gui_config is not None and gui_config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(gui_config.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Content-Type"],
        )
    app.state.job_manager = job_manager

    @app.middleware("http")  # type: ignore[misc]
    async def security_headers(request: Any, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def index_payload() -> Any:
        return build_run_index(
            workspace,
            runs_root,
            max_runs=config.max_runs,
            max_json_bytes=config.max_json_bytes,
        )

    @app.get("/health")  # type: ignore[misc]
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "version": __version__,
            "read_only": not execution_enabled,
            "execution_enabled": execution_enabled,
            "workspace": workspace.name,
        }

    @app.get("/api/capabilities")  # type: ignore[misc]
    def capabilities() -> dict[str, object]:
        current_commit = ""
        try:
            completed = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=workspace,
                check=True,
                capture_output=True,
                text=True,
                timeout=3,
            )
            current_commit = completed.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
        expected_commit = ""
        matrix_path = workspace / "experiments" / "run_matrix_v6.json"
        if matrix_path.is_file() and matrix_path.stat().st_size <= config.max_json_bytes:
            try:
                matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
                if isinstance(matrix, dict):
                    expected_commit = str(matrix.get("code_commit", ""))
            except (OSError, ValueError):
                pass
        return {
            "execution_enabled": execution_enabled,
            "algorithms": ["PPO", "SAC", "TD3", "A2C"],
            "searchers": [
                "random",
                "grid",
                "tpe",
                "cma_es",
                "nsga_ii",
                "pso",
                "genetic",
                "differential_evolution",
                "simulated_annealing",
            ],
            "schedulers": ["fifo", "median", "asha", "hyperband", "pbt"],
            "agent_topologies": [
                "single",
                "pipeline",
                "supervisor_worker",
                "committee_vote",
                "debate_then_judge",
                "map_reduce",
            ],
            "conflict_policies": [
                "weighted_vote",
                "majority_vote",
                "judge",
                "most_conservative",
                "reject",
            ],
            "agent_model": "deepseek-v4-pro",
            "agent_layers": ["research", "risk", "hierarchical"],
            "dependencies": {
                "torch": importlib.util.find_spec("torch") is not None,
                "stable_baselines3": (
                    importlib.util.find_spec("stable_baselines3") is not None
                ),
                "ray": importlib.util.find_spec("ray") is not None,
                "deepseek_api_key_configured": bool(os.getenv("DEEPSEEK_API_KEY")),
            },
            "formal_experiment_gate": {
                "protocol": "protocol-v4",
                "matrix": "matrix-v6",
                "expected_commit": expected_commit,
                "current_commit": current_commit,
                "ready": bool(expected_commit and current_commit == expected_commit),
            },
        }

    @app.get("/api/configs")  # type: ignore[misc]
    def list_configs(
        kind: ConfigKind | None = None,
    ) -> dict[str, object]:
        entries = list_configurations(workspace, kind=kind)
        return {
            "total": len(entries),
            "configs": [entry.model_dump(mode="json") for entry in entries],
        }

    @app.get("/api/configs/content")  # type: ignore[misc]
    def get_config_content(kind: ConfigKind, path: str) -> dict[str, object]:
        try:
            content = read_configuration(workspace, kind=kind, config_path=path)
        except (OSError, ValueError):
            raise HTTPException(status_code=404, detail="configuration not found") from None
        return cast(dict[str, object], content.model_dump(mode="json"))

    @app.post("/api/configs/validate")  # type: ignore[misc]
    def validate_config(
        request: ConfigValidationRequest,
    ) -> dict[str, object]:
        result = validate_configuration(workspace, request)
        return cast(dict[str, object], result.model_dump(mode="json"))

    if job_manager is not None:

        @app.get("/api/jobs")  # type: ignore[misc]
        def list_jobs(
            limit: int = Query(default=100, ge=1, le=500),
        ) -> dict[str, object]:
            jobs = job_manager.list(limit=limit)
            return {
                "total": len(jobs),
                "jobs": [job_record_json(record) for record in jobs],
            }

        @app.post("/api/jobs", status_code=202)  # type: ignore[misc]
        def create_job(request: JobRequest) -> dict[str, object]:
            try:
                record = job_manager.submit(request)
            except (OSError, TypeError, ValueError) as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            return job_record_json(record)

        @app.get("/api/jobs/{job_id}")  # type: ignore[misc]
        def get_job(job_id: str) -> dict[str, object]:
            try:
                return job_record_json(job_manager.get(job_id))
            except KeyError:
                raise HTTPException(status_code=404, detail="job not found") from None

        @app.get("/api/jobs/{job_id}/log")  # type: ignore[misc]
        def get_job_log(job_id: str) -> dict[str, object]:
            try:
                record = job_manager.get(job_id)
                output = job_manager.log_tail(job_id)
            except KeyError:
                raise HTTPException(status_code=404, detail="job not found") from None
            return {
                "job_id": job_id,
                "status": record.status,
                "output": output,
                "truncated_to_bytes": job_manager.max_log_bytes,
            }

        @app.delete("/api/jobs/{job_id}")  # type: ignore[misc]
        def cancel_job(job_id: str) -> dict[str, object]:
            try:
                return job_record_json(job_manager.cancel(job_id))
            except KeyError:
                raise HTTPException(status_code=404, detail="job not found") from None
            except RuntimeError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/runs")  # type: ignore[misc]
    def list_runs(
        kind: str | None = None,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, object]:
        index = index_payload()
        records = [
            record
            for record in index.runs
            if kind is None or record.kind == kind
        ]
        return {
            "total": len(records),
            "offset": offset,
            "limit": limit,
            "runs": [
                record.model_dump(mode="json")
                for record in records[offset : offset + limit]
            ],
            "fingerprint": index.fingerprint,
        }

    @app.get("/api/runs/{run_id}")  # type: ignore[misc]
    def get_run(run_id: str) -> dict[str, object]:
        if _PORTABLE_ID.fullmatch(run_id) is None:
            raise HTTPException(status_code=404, detail="run not found")
        for record in index_payload().runs:
            if record.run_id == run_id:
                return cast(dict[str, object], record.model_dump(mode="json"))
        raise HTTPException(status_code=404, detail="run not found")

    @app.get("/api/reports")  # type: ignore[misc]
    def list_reports() -> dict[str, object]:
        reports: list[dict[str, object]] = []
        if reports_root.is_dir():
            for directory in sorted(reports_root.iterdir(), key=lambda item: item.name):
                manifest_path = directory / "manifest.json"
                if (
                    not directory.is_dir()
                    or _PORTABLE_ID.fullmatch(directory.name) is None
                    or not manifest_path.is_file()
                ):
                    continue
                raw = read_bounded_json(
                    manifest_path,
                    max_bytes=config.max_json_bytes,
                )
                if not isinstance(raw, dict):
                    continue
                artifacts = raw.get("artifacts")
                reports.append(
                    {
                        "report_id": str(raw.get("report_id", directory.name)),
                        "source_index_sha256": str(raw.get("source_index_sha256", "")),
                        "artifact_count": len(artifacts) if isinstance(artifacts, list) else 0,
                        "url": f"/reports/{directory.name}/",
                    }
                )
        return {"reports": reports}

    def report_directory(report_id: str) -> Path:
        if _PORTABLE_ID.fullmatch(report_id) is None:
            raise HTTPException(status_code=404, detail="report not found")
        directory = resolve_inside(report_id, reports_root)
        if not directory.is_dir():
            raise HTTPException(status_code=404, detail="report not found")
        return directory

    @app.get("/reports/{report_id}")  # type: ignore[misc]
    def canonical_report_url(report_id: str) -> Any:
        report_directory(report_id)
        return RedirectResponse(
            url=f"/reports/{report_id}/",
            status_code=307,
        )

    @app.get("/reports/{report_id}/")  # type: ignore[misc]
    def report_html(report_id: str) -> Any:
        path = report_directory(report_id) / "report.html"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="report not found")
        return FileResponse(path, media_type="text/html")

    @app.get("/reports/{report_id}/{asset_path:path}")  # type: ignore[misc]
    def report_asset(report_id: str, asset_path: str) -> Any:
        directory = report_directory(report_id)
        path = resolve_inside(asset_path, directory)
        if not path.is_file() or path.suffix.lower() not in _PUBLIC_SUFFIXES:
            raise HTTPException(status_code=404, detail="report asset not found")
        media = {
            ".csv": "text/csv",
            ".json": "application/json",
            ".md": "text/markdown",
            ".svg": "image/svg+xml",
        }[path.suffix.lower()]
        return FileResponse(path, media_type=media)

    return app


def run_service(config: ServiceConfig) -> None:
    """Start the optional server only after explicit CLI invocation."""
    try:
        import uvicorn
    except ImportError as error:
        raise RuntimeError(
            "Phase 8 service requires: pip install 'crossmarket-agent-gym[service]'"
        ) from error
    uvicorn.run(
        create_app(config),
        host=config.host,
        port=config.port,
        log_level="info",
    )
