"""Huginn configuration.

Bifröst constructs ``HuginnMemory(config=None)`` — defaults are
therefore a *contract*: with no config and no Qdrant server anywhere,
Huginn must come up on its local backend and work. Every field is
validated at construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import HuginnConfigurationError

DEFAULT_LOCAL_DB_PATH = "~/.hermes/memory/huginn_local.db"
BACKENDS = ("auto", "local", "qdrant")
EMBEDDERS = ("tfidf", "hashing", "sentence-transformers")


@dataclass
class HuginnConfig:
    """Configuration for :class:`huginn.HuginnMemory`.

    Attributes:
        backend: ``"auto"`` (default) probes Qdrant once, lazily, and
            falls back to the local backend permanently for that
            object if anything fails — recording why in ``health()``.
            ``"local"`` never touches the network. ``"qdrant"`` is
            explicit: failures raise :class:`HuginnBackendError`.
        qdrant_url: Qdrant server URL (Bifröst's own default is
            ``http://localhost:6333``; it never passes it, so Huginn
            carries the same default).
        qdrant_api_key: Optional Qdrant API key.
        collection_name: Qdrant collection for memories.
        local_db_path: SQLite file for the local backend.
        embedder: ``"tfidf"`` (default; local backend's native lexical
            scoring — no vectors needed), ``"hashing"`` (deterministic
            feature-hashing vectors, stdlib), or
            ``"sentence-transformers"`` (neural embeddings; needs the
            ``embeddings`` extra). Qdrant needs fixed-space vectors, so
            with a Qdrant backend ``"tfidf"`` resolves to ``"hashing"``
            (reported honestly in ``health()``).
        vector_dim: Hashing-embedder dimension (and Qdrant collection
            size for the hashing embedder).
        st_model: sentence-transformers model name.
        qdrant_timeout: Seconds for the auto-probe and Qdrant calls.
        busy_timeout_ms / backup_keep / auto_backup: same store
            discipline as Muninn's.
    """

    backend: str = "auto"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    collection_name: str = "huginn_memories"
    local_db_path: str = DEFAULT_LOCAL_DB_PATH
    embedder: str = "tfidf"
    vector_dim: int = 384
    st_model: str = "all-MiniLM-L6-v2"
    qdrant_timeout: float = 2.0
    busy_timeout_ms: int = 5000
    backup_keep: int = 3
    auto_backup: bool = True

    def __post_init__(self) -> None:
        if self.backend not in BACKENDS:
            raise HuginnConfigurationError(f"backend must be one of {BACKENDS}")
        if self.embedder not in EMBEDDERS:
            raise HuginnConfigurationError(f"embedder must be one of {EMBEDDERS}")
        if not isinstance(self.qdrant_url, str) or not self.qdrant_url.strip():
            raise HuginnConfigurationError("qdrant_url must be a non-empty string")
        if not isinstance(self.local_db_path, str) or not self.local_db_path.strip():
            raise HuginnConfigurationError("local_db_path must be a non-empty string")
        if not isinstance(self.collection_name, str) or not self.collection_name.strip():
            raise HuginnConfigurationError("collection_name must be a non-empty string")
        if int(self.vector_dim) < 8:
            raise HuginnConfigurationError("vector_dim must be >= 8")
        if float(self.qdrant_timeout) <= 0:
            raise HuginnConfigurationError("qdrant_timeout must be > 0")
        if int(self.busy_timeout_ms) < 0:
            raise HuginnConfigurationError("busy_timeout_ms must be >= 0")
        if int(self.backup_keep) < 0:
            raise HuginnConfigurationError("backup_keep must be >= 0")

    def resolved_local_path(self) -> Path:
        return Path(self.local_db_path).expanduser()
