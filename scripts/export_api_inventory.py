"""Export the reviewed Phase 10 API inventory and schema snapshots."""

from __future__ import annotations

from pathlib import Path

from crossmarket_agentgym.release.freeze import export_frozen_contracts

if __name__ == "__main__":
    result = export_frozen_contracts(Path(__file__).resolve().parents[1])
    print(result.model_dump_json(indent=2))
