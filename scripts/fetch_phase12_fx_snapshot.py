"""Fetch the one immutable ECB input snapshot used by Phase 12.

This script is an acquisition step, not part of an experiment run. Formal
experiments only read the local byte-for-byte snapshot recorded in the frozen
protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def fetch_snapshot(
    *,
    endpoint: str,
    start: date,
    end: date,
    output: Path,
) -> dict[str, object]:
    """Download once, validate the response shape, and refuse overwrite."""
    if output.exists():
        raise FileExistsError(f"FX snapshot already exists and is immutable: {output}")
    query = urlencode(
        {
            "startPeriod": start.isoformat(),
            "endPeriod": end.isoformat(),
            "format": "csvdata",
            "detail": "dataonly",
        }
    )
    request = Request(
        f"{endpoint}?{query}",
        headers={"User-Agent": "CrossMarketAgentGym/1.0 Phase12 protocol acquisition"},
    )
    with urlopen(request, timeout=60) as response:  # noqa: S310 - frozen HTTPS endpoint
        payload = response.read()
        content_type = response.headers.get("Content-Type", "")
    header = payload.splitlines()[0].decode("utf-8-sig", errors="strict")
    required = {"CURRENCY", "CURRENCY_DENOM", "TIME_PERIOD", "OBS_VALUE"}
    if not required.issubset(set(header.split(","))):
        raise ValueError("ECB response is not the expected EXR csvdata schema")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    result: dict[str, object] = {
        "source_url": f"{endpoint}?{query}",
        "snapshot": output.as_posix(),
        "sha256": _sha256(payload),
        "bytes": len(payload),
        "content_type": content_type,
        "first_date": start.isoformat(),
        "last_date": end.isoformat(),
    }
    output.with_suffix(output.suffix + ".metadata.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--endpoint",
        default=(
            "https://data-api.ecb.europa.eu/service/data/"
            "EXR/D.CNY%2BHKD%2BJPY%2BUSD.EUR.SP00.A"
        ),
    )
    parser.add_argument("--start", type=date.fromisoformat, default=date(2020, 12, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2025, 9, 30))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("experiments/data/ecb_exr_20201201_20250930.csv"),
    )
    args = parser.parse_args()
    result = fetch_snapshot(
        endpoint=args.endpoint,
        start=args.start,
        end=args.end,
        output=args.output,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
