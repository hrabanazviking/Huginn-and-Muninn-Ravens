"""Muninn configuration.

Bifröst constructs this as ``MuninnConfig(db_path=...)`` and nothing
more; every other field carries the default the ancestors' semantics
imply. All values are validated at construction — a bad configuration
fails loudly here, never mid-write.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import MuninnConfigurationError

DEFAULT_DB_PATH = "~/.hermes/memory/muninn_hebbian.db"


@dataclass
class MuninnConfig:
    """Configuration for :class:`muninn.HebbianMemory`.

    Attributes:
        db_path: SQLite store file. ``~`` is expanded. The parent
            directory is created on open. Default matches Bifröst's
            own default Muninn path.
        learning_rate: Hebbian bounded-learning rate in (0, 1]. On each
            co-activation, ``strength ← 1 − (1 − strength)(1 − rate)``;
            a first wiring starts at exactly ``learning_rate``.
        decay_half_life_days: Edge-strength half-life for ``decay()``.
        confidence_half_life_days: Node-confidence half-life (TDD:
            low-use memories decay multiplicatively).
        prune_threshold: Edges whose decayed strength falls below this
            are deleted by ``decay()``.
        consolidation_threshold: Edges at or above this strength are
            marked consolidated by ``consolidate()`` (Bifröst's config
            declares 0.8 for the same concept).
        busy_timeout_ms: SQLite busy timeout — how long a locked store
            is awaited before an error is raised.
        backup_keep: Rolling backup generations kept beside the store.
        auto_backup: Take/refresh a rolling backup on open (when the
            store changed since the last backup) and before decay /
            consolidate maintenance.
        max_nodes: Backpressure ceiling inherited from the ancestor:
            storing beyond it prunes the lowest-value nodes.
    """

    db_path: str = DEFAULT_DB_PATH
    learning_rate: float = 0.1
    decay_half_life_days: float = 30.0
    confidence_half_life_days: float = 90.0
    prune_threshold: float = 0.01
    consolidation_threshold: float = 0.8
    busy_timeout_ms: int = 5000
    backup_keep: int = 3
    auto_backup: bool = True
    max_nodes: int = 20000

    def __post_init__(self) -> None:
        if not isinstance(self.db_path, str) or not self.db_path.strip():
            raise MuninnConfigurationError("db_path must be a non-empty string")
        if not (0.0 < float(self.learning_rate) <= 1.0):
            raise MuninnConfigurationError("learning_rate must be in (0, 1]")
        if float(self.decay_half_life_days) <= 0:
            raise MuninnConfigurationError("decay_half_life_days must be > 0")
        if float(self.confidence_half_life_days) <= 0:
            raise MuninnConfigurationError("confidence_half_life_days must be > 0")
        if not (0.0 <= float(self.prune_threshold) < 1.0):
            raise MuninnConfigurationError("prune_threshold must be in [0, 1)")
        if not (0.0 < float(self.consolidation_threshold) <= 1.0):
            raise MuninnConfigurationError("consolidation_threshold must be in (0, 1]")
        if int(self.busy_timeout_ms) < 0:
            raise MuninnConfigurationError("busy_timeout_ms must be >= 0")
        if int(self.backup_keep) < 0:
            raise MuninnConfigurationError("backup_keep must be >= 0")
        if int(self.max_nodes) < 1:
            raise MuninnConfigurationError("max_nodes must be >= 1")

    def resolved_path(self) -> Path:
        """The store path with ``~`` expanded (not symlink-resolved)."""
        return Path(self.db_path).expanduser()
