from __future__ import annotations


class PipelineError(Exception):
    """Base exception for all pipeline errors."""


class CollectorError(PipelineError):
    """Base exception for collector failures."""


class FetchError(CollectorError):
    """Raised when an API fetch fails."""


class ParseError(CollectorError):
    """Raised when API response parsing fails."""


class ValidationError(CollectorError):
    """Raised when API response fails validation."""


class StorageError(PipelineError):
    """Base exception for storage layer errors."""


class AnalyticsError(PipelineError):
    """Base exception for analytics computation errors."""


class ExportError(PipelineError):
    """Base exception for export errors."""
