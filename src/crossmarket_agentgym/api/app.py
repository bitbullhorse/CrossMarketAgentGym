"""Optional FastAPI application exposing whitelisted read-only artifacts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

from crossmarket_agentgym import __version__
from crossmarket_agentgym.api.config import ServiceConfig
from crossmarket_agentgym.reporting.indexer import build_run_index
from crossmarket_agentgym.reporting.io import read_bounded_json, resolve_inside

_PORTABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_PUBLIC_SUFFIXES = frozenset({".csv", ".json", ".md", ".svg"})


def _service_dependencies() -> tuple[Any, Any, Any, Any, Any]:
    try:
        from fastapi import FastAPI, HTTPException, Query
        from fastapi.responses import FileResponse, RedirectResponse
    except ImportError as error:
        raise RuntimeError(
            "Phase 8 service requires: pip install 'crossmarket-agent-gym[service]'"
        ) from error
    return FastAPI, HTTPException, Query, FileResponse, RedirectResponse


def create_app(config: ServiceConfig) -> Any:
    """Create an app without mutating runs or exposing arbitrary files."""
    FastAPI, HTTPException, Query, FileResponse, RedirectResponse = (
        _service_dependencies()
    )
    workspace = config.workspace_root.resolve()
    runs_root = resolve_inside(config.runs_root, workspace)
    reports_root = resolve_inside(config.reports_root, workspace)
    app = FastAPI(
        title="CrossMarketAgentGym read-only browser",
        version=__version__,
        docs_url="/docs" if config.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if config.docs_enabled else None,
    )

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
        return {"status": "ok", "version": __version__, "read_only": True}

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
