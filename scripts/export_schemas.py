"""Export and verify all rc1 configuration and artifact schemas."""

from __future__ import annotations

from pathlib import Path

from crossmarket_agentgym.release.freeze import (
    export_frozen_contracts,
    verify_frozen_contracts,
)

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    export_frozen_contracts(root)
    result = verify_frozen_contracts(root)
    print(result.model_dump_json(indent=2))
    if not result.is_valid:
        raise SystemExit(1)
