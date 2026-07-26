"""Market data ingestion, validation, calendars, and manifests."""

from crossmarket_agentgym.data.dataset import (
    DatasetValidationSummary,
    validate_configured_dataset,
    validate_legacy_dataset,
    validate_manifest_dataset,
)
from crossmarket_agentgym.data.io import (
    CanonicalLoadResult,
    load_canonical,
    write_canonical,
)
from crossmarket_agentgym.data.partitions import (
    PartitionAccessError,
    PartitionCapability,
    PartitionName,
    require_partition,
)

__all__ = [
    "CanonicalLoadResult",
    "DatasetValidationSummary",
    "PartitionAccessError",
    "PartitionCapability",
    "PartitionName",
    "load_canonical",
    "require_partition",
    "validate_configured_dataset",
    "validate_legacy_dataset",
    "validate_manifest_dataset",
    "write_canonical",
]
