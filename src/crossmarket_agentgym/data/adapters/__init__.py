"""Source-specific data adapters."""

from crossmarket_agentgym.data.adapters.base import AdapterResult, SourceAdapter
from crossmarket_agentgym.data.adapters.legacy import (
    LegacyCNExcelAdapter,
    LegacyYahooCSVAdapter,
    adapter_for,
    discover_legacy_files,
)

__all__ = [
    "AdapterResult",
    "LegacyCNExcelAdapter",
    "LegacyYahooCSVAdapter",
    "SourceAdapter",
    "adapter_for",
    "discover_legacy_files",
]
