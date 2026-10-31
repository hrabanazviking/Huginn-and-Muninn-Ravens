"""Huginn — the Thought Raven.

Semantic retrieval over your memories: Qdrant when it is genuinely
available, a fully capable local TF-IDF store when it is not — and a
missing server never crashes the caller.

Importing this package constructs nothing, opens no file and touches
no network; backends are built lazily on first use, and each
:class:`HuginnMemory` opens only its own store.
"""

from .config import HuginnConfig
from .core import HuginnMemory, RetrievalResult, analyze_query, semantic_search
from .errors import (
    HuginnBackendError,
    HuginnConfigurationError,
    HuginnError,
    HuginnStorageError,
    HuginnValidationError,
)

__version__ = "1.0.0"

__all__ = [
    "HuginnMemory",
    "HuginnConfig",
    "RetrievalResult",
    "analyze_query",
    "semantic_search",
    "HuginnError",
    "HuginnValidationError",
    "HuginnConfigurationError",
    "HuginnStorageError",
    "HuginnBackendError",
    "__version__",
]
