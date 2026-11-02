"""Huginn configuration.

Bifröst constructs ``HuginnMemory(config=None)`` — defaults are
therefore a *contract*: with no config and no Qdrant server anywhere,
Huginn must come up on its local backend and work. Every field is
validated at construction.

The config is **frozen** after validation (RM-017): assigning to any
field raises ``dataclasses.FrozenInstanceError``, so a caller cannot
change a live store's behaviour by mutating the dataclass it handed
in. The road to a different configuration is
``dataclasses.replace(config, field=value)``, which builds a new,
re-validated config — the constructors' ``**overrides`` already take
that road.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import HuginnConfigurationError

DEFAULT_LOCAL_DB_PATH = "~/.hermes/memory/huginn_local.db"
BACKENDS = ("auto", "local", "qdrant")
EMBEDDERS = ("tfidf", "hashing", "sentence-transformers")


def _coerce_float(value: object) -> float | None:
    """RM-026: the value as a float, or None — never an untyped raise.

    Accepts exactly the shapes the pre-RM-026 ``float()`` checks
    accepted for sane callers (bool / int / float / numeric
    string); anything else is None, and the caller raises the
    field's typed configuration error. (Twin of muninn's RM-025
    helper.)
    """
    if isinstance(value, (bool, int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _coerce_int(value: object) -> int | None:
    """RM-026: the value as an int, or None — never an untyped raise."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        try:
            return int(value)
        except (ValueError, OverflowError):
            return None
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


@dataclass(frozen=True)
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
        max_content_bytes: Oversize policy (RM-027): the ceiling
            on one memory's content, measured in UTF-8 bytes.
            Content above the ceiling is refused with a typed
            validation error before any write, on every backend.
            (Huginn memories carry no caller metadata argument, so
            there is no metadata ceiling here; Muninn's config
            carries both.)
        strict_path_safety: Path safety (RM-041): when True,
            opening the local store refuses a symlinked store
            path (the file itself or any parent directory
            component) and a store whose parent directory is
            world-writable, with a typed storage error — for
            locked-down deployments where a planted symlink or
            a shared parent could redirect the store (or its
            restore) elsewhere (threat TH-02). Default False:
            paths keep the recorded behaviour — ``~`` expanded,
            never symlink-resolved, no parent-permission check.
            Applies to the local backend only; the Qdrant
            backend has no local file. Like ``auto_backup`` it
            is a plain boolean flag, used as given. See
            ``docs/PATH_SAFETY.md``.
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
    max_content_bytes: int = 1048576
    strict_path_safety: bool = False

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
        if not isinstance(self.st_model, str) or not self.st_model.strip():
            raise HuginnConfigurationError("st_model must be a non-empty string")
        if self.qdrant_api_key is not None and not isinstance(self.qdrant_api_key, str):
            raise HuginnConfigurationError("qdrant_api_key must be a string or None")
        vector_dim = _coerce_int(self.vector_dim)
        if vector_dim is None or vector_dim < 8:
            raise HuginnConfigurationError("vector_dim must be >= 8")
        qdrant_timeout = _coerce_float(self.qdrant_timeout)
        if qdrant_timeout is None or not qdrant_timeout > 0:
            raise HuginnConfigurationError("qdrant_timeout must be > 0")
        busy_timeout_ms = _coerce_int(self.busy_timeout_ms)
        if busy_timeout_ms is None or busy_timeout_ms < 0:
            raise HuginnConfigurationError("busy_timeout_ms must be >= 0")
        backup_keep = _coerce_int(self.backup_keep)
        if backup_keep is None or backup_keep < 0:
            raise HuginnConfigurationError("backup_keep must be >= 0")
        max_content_bytes = _coerce_int(self.max_content_bytes)
        if max_content_bytes is None or max_content_bytes < 1:
            raise HuginnConfigurationError("max_content_bytes must be >= 1")

    def resolved_local_path(self) -> Path:
        return Path(self.local_db_path).expanduser()
