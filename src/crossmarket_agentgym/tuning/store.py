"""SQLite-backed, strict-JSON study persistence."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from crossmarket_agentgym.tuning.models import (
    Direction,
    StudyState,
    TrialResult,
    TrialStatus,
    TrialSuggestion,
)

_TERMINAL_STATUSES: tuple[TrialStatus, ...] = ("completed", "failed", "pruned")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json_dump(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


class SQLiteStudyStore:
    """Durable study, trial, and component-checkpoint store."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._create_schema()

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS studies (
                name TEXT PRIMARY KEY,
                directions_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS trials (
                study_name TEXT NOT NULL,
                trial_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                parameters_json TEXT NOT NULL,
                generation INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                objectives_json TEXT NOT NULL DEFAULT '[]',
                metrics_json TEXT NOT NULL DEFAULT '{}',
                resource REAL NOT NULL DEFAULT 0,
                error TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (study_name, trial_id),
                FOREIGN KEY (study_name) REFERENCES studies(name)
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                study_name TEXT NOT NULL,
                component TEXT NOT NULL,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (study_name, component),
                FOREIGN KEY (study_name) REFERENCES studies(name)
            );
            """
        )
        columns = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(studies)").fetchall()
        }
        if "metadata_json" not in columns:
            self._connection.execute(
                "ALTER TABLE studies ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'"
            )
        self._connection.commit()

    def create_study(
        self,
        name: str,
        directions: tuple[Direction, ...],
        metadata: dict[str, Any] | None = None,
    ) -> StudyState:
        """Create a study or validate the immutable objective directions."""
        if not name:
            raise ValueError("study name must not be empty")
        if not directions:
            raise ValueError("study requires at least one direction")
        stored = self._connection.execute(
            "SELECT directions_json, metadata_json FROM studies WHERE name = ?",
            (name,),
        ).fetchone()
        serialized = _json_dump(directions)
        metadata_json = _json_dump(metadata or {})
        if stored is None:
            self._connection.execute(
                """
                INSERT INTO studies(name, directions_json, metadata_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (name, serialized, metadata_json, _now()),
            )
            self._connection.commit()
        elif tuple(json.loads(stored["directions_json"])) != directions:
            raise ValueError("study objective directions cannot change on resume")
        elif metadata is not None and stored["metadata_json"] != metadata_json:
            raise ValueError("study configuration cannot change on resume")
        return self.study_state(name)

    def _require_study(self, name: str) -> tuple[Direction, ...]:
        row = self._connection.execute(
            "SELECT directions_json FROM studies WHERE name = ?",
            (name,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown study: {name}")
        return cast(tuple[Direction, ...], tuple(json.loads(row["directions_json"])))

    def study_state(self, name: str) -> StudyState:
        """Load terminal trial history for searcher initialization."""
        directions = self._require_study(name)
        return StudyState(
            study_name=name,
            directions=directions,
            results=tuple(self.list_results(name, statuses=_TERMINAL_STATUSES)),
        )

    def save_suggestion(self, study_name: str, suggestion: TrialSuggestion) -> None:
        """Persist a running suggestion before objective execution."""
        self._require_study(study_name)
        existing = self._connection.execute(
            "SELECT parameters_json FROM trials WHERE study_name = ? AND trial_id = ?",
            (study_name, suggestion.trial_id),
        ).fetchone()
        parameters_json = _json_dump(suggestion.parameters)
        if existing is not None:
            if existing["parameters_json"] != parameters_json:
                raise ValueError("trial ID already belongs to different parameters")
            return
        self._connection.execute(
            """
            INSERT INTO trials(
                study_name, trial_id, status, parameters_json, generation,
                metadata_json, updated_at
            ) VALUES (?, ?, 'running', ?, ?, ?, ?)
            """,
            (
                study_name,
                suggestion.trial_id,
                parameters_json,
                suggestion.generation,
                _json_dump(suggestion.metadata),
                _now(),
            ),
        )
        self._connection.commit()

    def save_result(self, study_name: str, result: TrialResult) -> None:
        """Upsert a terminal or intermediate result with strict JSON."""
        self._require_study(study_name)
        existing = self._connection.execute(
            "SELECT parameters_json FROM trials WHERE study_name = ? AND trial_id = ?",
            (study_name, result.trial_id),
        ).fetchone()
        parameters_json = _json_dump(result.parameters)
        if existing is not None and existing["parameters_json"] != parameters_json:
            raise ValueError("result parameters differ from stored suggestion")
        self._connection.execute(
            """
            INSERT INTO trials(
                study_name, trial_id, status, parameters_json, objectives_json,
                metrics_json, resource, error, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(study_name, trial_id) DO UPDATE SET
                status = excluded.status,
                objectives_json = excluded.objectives_json,
                metrics_json = excluded.metrics_json,
                resource = excluded.resource,
                error = excluded.error,
                updated_at = excluded.updated_at
            """,
            (
                study_name,
                result.trial_id,
                result.status,
                parameters_json,
                _json_dump(result.objectives),
                _json_dump(result.metrics),
                result.resource,
                result.error,
                _now(),
            ),
        )
        self._connection.commit()

    def list_results(
        self,
        study_name: str,
        *,
        statuses: Iterable[TrialStatus] | None = None,
    ) -> list[TrialResult]:
        """Return ordered trial records, optionally filtered by status."""
        self._require_study(study_name)
        arguments: list[Any] = [study_name]
        query = (
            "SELECT trial_id, status, parameters_json, objectives_json, "
            "metrics_json, resource, error FROM trials WHERE study_name = ?"
        )
        if statuses is not None:
            selected = tuple(statuses)
            if not selected:
                return []
            query += f" AND status IN ({','.join('?' for _ in selected)})"
            arguments.extend(selected)
        query += " ORDER BY trial_id"
        rows = self._connection.execute(query, arguments).fetchall()
        return [
            TrialResult(
                trial_id=row["trial_id"],
                parameters=json.loads(row["parameters_json"]),
                status=row["status"],
                objectives=tuple(json.loads(row["objectives_json"])),
                metrics=json.loads(row["metrics_json"]),
                resource=row["resource"],
                error=row["error"],
            )
            for row in rows
        ]

    def pending_suggestions(self, study_name: str) -> list[TrialSuggestion]:
        """Recover suggestions left running by an interrupted process."""
        self._require_study(study_name)
        rows = self._connection.execute(
            """
            SELECT trial_id, parameters_json, generation, metadata_json
            FROM trials
            WHERE study_name = ? AND status IN ('pending', 'running')
            ORDER BY trial_id
            """,
            (study_name,),
        ).fetchall()
        return [
            TrialSuggestion(
                trial_id=row["trial_id"],
                parameters=json.loads(row["parameters_json"]),
                generation=row["generation"],
                metadata=json.loads(row["metadata_json"]),
            )
            for row in rows
        ]

    def save_checkpoint(
        self,
        study_name: str,
        component: str,
        state: dict[str, Any],
    ) -> None:
        """Atomically replace one JSON component checkpoint."""
        self._require_study(study_name)
        self._connection.execute(
            """
            INSERT INTO checkpoints(study_name, component, state_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(study_name, component) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
            """,
            (study_name, component, _json_dump(state), _now()),
        )
        self._connection.commit()

    def load_checkpoint(
        self,
        study_name: str,
        component: str,
    ) -> dict[str, Any] | None:
        """Load one component checkpoint if it exists."""
        self._require_study(study_name)
        row = self._connection.execute(
            "SELECT state_json FROM checkpoints WHERE study_name = ? AND component = ?",
            (study_name, component),
        ).fetchone()
        return None if row is None else dict(json.loads(row["state_json"]))

    def close(self) -> None:
        """Flush and close the SQLite connection."""
        self._connection.close()

    def __enter__(self) -> SQLiteStudyStore:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
