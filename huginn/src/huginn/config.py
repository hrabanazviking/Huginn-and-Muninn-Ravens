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

import ipaddress
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

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


def _is_loopback_host(host: str) -> bool:
    """RM-045: is this URL hostname a loopback host?

    ``localhost`` (and any ``*.localhost`` name) plus the
    loopback IP ranges (127.0.0.0/8, ::1) as judged by
    :mod:`ipaddress`. Anything unparseable is not loopback.
    """
    name = host.rstrip(".").lower()
    if name == "localhost" or name.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def _check_qdrant_url_transport(url: str, allow_insecure_http: bool) -> None:
    """RM-045: the Qdrant URL's transport must be safe (TH-06).

    ``https`` is accepted for any host. Plain ``http`` is
    accepted only for a loopback host (the recorded local
    convenience: the default ``http://localhost:6333``), or
    for any host when the caller explicitly opted in with
    ``allow_insecure_http=True``. Every other shape — a
    non-http(s) scheme, a missing host, an unparseable URL,
    or plain http to a non-localhost host without the
    opt-in — is refused here, at construction, with the
    typed configuration error. The messages are static: the
    URL itself (which a caller could have loaded with
    credentials) and the API key never appear in them.
    """
    try:
        parts = urlsplit(url)
        scheme = parts.scheme.lower()
        host = parts.hostname
    except ValueError:
        raise HuginnConfigurationError(
            "qdrant_url must include a host"
        ) from None
    if scheme not in ("http", "https"):
        raise HuginnConfigurationError("qdrant_url must use http or https")
    if not host:
        raise HuginnConfigurationError("qdrant_url must include a host")
    if scheme == "http" and not allow_insecure_http and not _is_loopback_host(host):
        raise HuginnConfigurationError(
            "qdrant_url uses plain http for a non-localhost host; "
            "use https or set allow_insecure_http=True"
        )


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
            carries the same default). Transport safety (RM-045,
            threat TH-06): the scheme must be http or https and
            the URL must name a host; ``https`` is accepted for
            any host, while plain ``http`` is accepted only for
            a loopback host (localhost / 127.0.0.0/8 / ::1) or
            with ``allow_insecure_http=True``. Refusals are
            typed configuration errors whose messages never
            carry the URL or the API key.
        qdrant_api_key: Optional Qdrant API key. Handed only to
            the Qdrant client constructor: it is excluded from
            the config's ``repr``, never logged, and scrubbed
            out of every wrapped client error string before
            that string can reach a caller or a log (RM-045).
        allow_insecure_http: Qdrant transport opt-out (RM-045):
            when True, a plain-``http`` Qdrant URL is accepted
            for a non-localhost host. Default False: remote
            Qdrant traffic must use ``https``, so the API key
            and the memory payloads never cross the network in
            clear text (threat TH-06). Like ``auto_backup`` it
            is a plain boolean flag, used as given. See
            ``docs/QDRANT_TRANSPORT.md``.
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
        debug_log_content: Log redaction (RM-044): when True,
            the facade's store and search paths may emit memory
            content in log records at DEBUG level only — the
            sole road by which content ever reaches a log.
            Default False: no log record at any level carries
            memory content; package loggers emit only paths,
            counts, heal-count reports, the Qdrant URL and
            exception strings (threat TH-05). Like
            ``auto_backup`` it is a plain boolean flag, used as
            given. See ``docs/LOG_REDACTION.md``.
        store_encryption: Store encryption (RM-049): when True,
            the local store's content-bearing values
            (``documents.content``, ``documents.tags``,
            ``doc_vectors.vector``) are sealed with
            application-level envelope encryption before they
            reach SQL — per-store data key wrapped under
            ``encryption_passphrase`` — the term index stores
            keyed HMAC tags of its tokens, and ``content_hash``
            becomes a keyed lookup tag (threat TH-09; decision
            record ``docs/STORE_ENCRYPTION.md``). Needs the
            ``encryption`` extra (``cryptography``). Default
            False: today's behaviour byte for byte. Applies to
            the local backend only; the Qdrant server owns its
            disk. A marked (encrypted) store is encrypted for
            its whole life: opening it without the flag refuses
            typed, and enabling the flag on an existing plain
            store that already holds documents refuses typed
            rather than half-encrypting it. Like ``auto_backup``
            it is a plain boolean flag, used as given.
        encryption_passphrase: Store encryption (RM-049): the
            passphrase the local store's data key is wrapped
            under, required when ``store_encryption`` is on.
            Excluded from the config's ``repr`` (the RM-045
            key-hygiene precedent); never stored, never logged,
            never in an error string. There is no recovery: a
            lost passphrase is a lost store.
        max_search_candidates: Query cost ceiling (RM-053):
            the maximum number of candidate documents one
            local-backend search may score (threat TH-13;
            record ``docs/QUERY_COST_CAPS.md``). A candidate
            is a document the index (TF-IDF terms, or the
            vector table) offers up for a query; when more
            candidates exist than the ceiling, the lowest-id
            candidates are scored and the rest are not
            considered by that call — deterministically —
            and the bite is visible in
            ``HuginnMemory.last_search_stats`` (``capped``
            is True, ``candidates_total`` reports how many
            existed). Below the ceiling, results are exactly
            what the unbounded search would return. Applies
            to the local backend only; the Qdrant server
            owns its own query cost.
    """

    backend: str = "auto"
    qdrant_url: str = "http://localhost:6333"
    # RM-045: repr=False — the key never appears in repr(config).
    qdrant_api_key: str | None = field(default=None, repr=False)
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
    debug_log_content: bool = False
    allow_insecure_http: bool = False
    store_encryption: bool = False
    # RM-049: repr=False — the passphrase never appears in repr(config).
    encryption_passphrase: str | None = field(default=None, repr=False)
    max_search_candidates: int = 10000

    def __post_init__(self) -> None:
        if self.backend not in BACKENDS:
            raise HuginnConfigurationError(f"backend must be one of {BACKENDS}")
        if self.embedder not in EMBEDDERS:
            raise HuginnConfigurationError(f"embedder must be one of {EMBEDDERS}")
        if not isinstance(self.qdrant_url, str) or not self.qdrant_url.strip():
            raise HuginnConfigurationError("qdrant_url must be a non-empty string")
        _check_qdrant_url_transport(self.qdrant_url, self.allow_insecure_http)
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
        if self.encryption_passphrase is not None and not isinstance(
            self.encryption_passphrase, str
        ):
            raise HuginnConfigurationError("encryption_passphrase must be a string or None")
        if self.store_encryption and not self.encryption_passphrase:
            raise HuginnConfigurationError(
                "encryption_passphrase is required when store_encryption is enabled"
            )
        max_search_candidates = _coerce_int(self.max_search_candidates)
        if max_search_candidates is None or max_search_candidates < 1:
            raise HuginnConfigurationError("max_search_candidates must be >= 1")

    def resolved_local_path(self) -> Path:
        return Path(self.local_db_path).expanduser()
