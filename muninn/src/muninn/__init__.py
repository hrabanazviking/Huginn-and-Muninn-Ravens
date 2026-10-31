"""Muninn — the Memory Raven.

Hebbian associative memory in one crash-proof SQLite store:
memory nodes, activation logging, co-activation wiring, decay and
consolidation — with self-healing structure and pure-read queries.

Importing this package constructs nothing and opens no file; a store
opens only when a :class:`HebbianMemory` (or :class:`Muninn`) object
is created, and it opens only its own file.
"""

from .config import MuninnConfig
from .core import HebbianMemory, MemoryNode, Muninn
from .errors import (
    MuninnConfigurationError,
    MuninnError,
    MuninnStorageError,
    MuninnValidationError,
)

__version__ = "1.0.0"

__all__ = [
    "HebbianMemory",
    "Muninn",
    "MemoryNode",
    "MuninnConfig",
    "MuninnError",
    "MuninnValidationError",
    "MuninnConfigurationError",
    "MuninnStorageError",
    "__version__",
]
