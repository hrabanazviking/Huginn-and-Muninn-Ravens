"""Muninn configuration.

Bifröst constructs this as ``MuninnConfig(db_path=...)`` and nothing
more; every other field carries the default the ancestors' semantics
imply. All values are validated at construction — a bad configuration
fails loudly here, never mid-write.

The config is **frozen** after validation (RM-017): assigning to any
field raises ``dataclasses.FrozenInstanceError``, so a caller cannot
change a live store's behaviour by mutating the dataclass it handed
in. The road to a different configuration is
``dataclasses.replace(config, field=value)``, which builds a new,
re-validated config — the constructors' ``**overrides`` already take
that road.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .errors import MuninnConfigurationError

DEFAULT_DB_PATH = "~/.hermes/memory/muninn_hebbian.db"


def _coerce_float(value: object) -> float | None:
    """RM-025: the value as a float, or None — never an untyped raise.

    Accepts exactly the shapes the pre-RM-025 ``float()`` checks
    accepted for sane callers (bool / int / float / numeric
    string); anything else is None, and the caller raises the
    field's typed configuration error.
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
    """RM-025: the value as an int, or None — never an untyped raise."""
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
        max_content_bytes: Oversize policy (RM-027): the ceiling on
            one node's stored content, measured in UTF-8 bytes of
            the stored text (the raw string, or its JSON
            serialization for non-string content). Content above
            the ceiling is refused with a typed validation error
            before any write.
        max_metadata_bytes: Oversize policy (RM-027): the ceiling
            on one node's metadata, measured in UTF-8 bytes of its
            serialized JSON form. Metadata above the ceiling is
            refused the same way.
        strict_path_safety: Path safety (RM-041): when True,
            opening the store refuses a symlinked store path (the
            file itself or any parent directory component) and a
            store whose parent directory is world-writable, with
            a typed storage error — for locked-down deployments
            where a planted symlink or a shared parent could
            redirect the store (or its restore) elsewhere
            (threat TH-02). Default False: paths keep the
            recorded behaviour — ``~`` expanded, never
            symlink-resolved, no parent-permission check. Like
            ``auto_backup`` it is a plain boolean flag, used as
            given. See ``docs/PATH_SAFETY.md``.
        debug_log_content: Log redaction (RM-044): when True,
            the store and retrieve paths may emit memory content
            in log records at DEBUG level only — the sole road
            by which content ever reaches a log. Default False:
            no log record at any level carries memory content;
            package loggers emit only paths, counts, heal-count
            reports and exception strings (threat TH-05). Like
            ``auto_backup`` it is a plain boolean flag, used as
            given. See ``docs/LOG_REDACTION.md``.
        store_encryption: Store encryption (RM-049): when True,
            the store's content-bearing values (``nodes.content``,
            ``nodes.metadata``, ``nodes.tags``) are sealed with
            application-level envelope encryption before they
            reach SQL — per-store data key wrapped under
            ``encryption_passphrase`` — and ``content_hash``
            becomes a keyed lookup tag (threat TH-09; decision
            record ``docs/STORE_ENCRYPTION.md``). Needs the
            ``encryption`` extra (``cryptography``). Default
            False: today's behaviour byte for byte. A marked
            (encrypted) store is encrypted for its whole life:
            opening it without the flag refuses typed, and
            enabling the flag on an existing plain store that
            already holds memories refuses typed rather than
            half-encrypting it. Like ``auto_backup`` it is a
            plain boolean flag, used as given.
        encryption_passphrase: Store encryption (RM-049): the
            passphrase the store's data key is wrapped under,
            required when ``store_encryption`` is on. Excluded
            from the config's ``repr`` (the RM-045 key-hygiene
            precedent); never stored, never logged, never in an
            error string. There is no recovery: a lost
            passphrase is a lost store.
        integrity_attestation: Integrity attestation (RM-050):
            when True, every ``activation_log`` row Muninn
            appends extends an HMAC-SHA256 chain whose key is
            derived from ``integrity_passphrase`` (stdlib
            PBKDF2; the key itself is never stored — the store
            carries only the salt, the chain head and the
            chained row count as ``meta`` rows, so the schema
            is untouched), and each open verifies the chain
            over the log as it stands: the verdict rides in
            ``health()``'s ``integrity_attestation`` field and
            in ``HebbianMemory.integrity_attestation_status``
            (threat TH-10; record
            ``docs/INTEGRITY_ATTESTATION.md``). Default False:
            today's behaviour byte for byte. Enabling it on an
            existing store bootstraps the chain over the rows
            already there — attested as found, so tampering
            from before enablement is out of scope by
            definition. A marked store opened without the flag
            refuses typed: an unattested open must never
            silently serve a store whose owner asked for
            attestation. Like ``auto_backup`` it is a plain
            boolean flag, used as given.
        integrity_passphrase: Integrity attestation (RM-050):
            the passphrase the chain key is derived from,
            required when ``integrity_attestation`` is on.
            Excluded from the config's ``repr``; never stored,
            never logged, never in an error string. A wrong
            passphrase cannot be distinguished from tampering
            — both recompute to a different head and both are
            reported as ``tamper_detected``.
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
    max_content_bytes: int = 1048576
    max_metadata_bytes: int = 65536
    strict_path_safety: bool = False
    debug_log_content: bool = False
    store_encryption: bool = False
    # RM-049: repr=False — the passphrase never appears in repr(config).
    encryption_passphrase: str | None = field(default=None, repr=False)
    integrity_attestation: bool = False
    # RM-050: repr=False — the passphrase never appears in repr(config).
    integrity_passphrase: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.db_path, str) or not self.db_path.strip():
            raise MuninnConfigurationError("db_path must be a non-empty string")
        learning_rate = _coerce_float(self.learning_rate)
        if learning_rate is None or not (0.0 < learning_rate <= 1.0):
            raise MuninnConfigurationError("learning_rate must be in (0, 1]")
        decay_half_life = _coerce_float(self.decay_half_life_days)
        if decay_half_life is None or not decay_half_life > 0:
            raise MuninnConfigurationError("decay_half_life_days must be > 0")
        confidence_half_life = _coerce_float(self.confidence_half_life_days)
        if confidence_half_life is None or not confidence_half_life > 0:
            raise MuninnConfigurationError("confidence_half_life_days must be > 0")
        prune_threshold = _coerce_float(self.prune_threshold)
        if prune_threshold is None or not (0.0 <= prune_threshold < 1.0):
            raise MuninnConfigurationError("prune_threshold must be in [0, 1)")
        consolidation_threshold = _coerce_float(self.consolidation_threshold)
        if consolidation_threshold is None or not (0.0 < consolidation_threshold <= 1.0):
            raise MuninnConfigurationError("consolidation_threshold must be in (0, 1]")
        busy_timeout = _coerce_int(self.busy_timeout_ms)
        if busy_timeout is None or busy_timeout < 0:
            raise MuninnConfigurationError("busy_timeout_ms must be >= 0")
        backup_keep = _coerce_int(self.backup_keep)
        if backup_keep is None or backup_keep < 0:
            raise MuninnConfigurationError("backup_keep must be >= 0")
        max_nodes = _coerce_int(self.max_nodes)
        if max_nodes is None or max_nodes < 1:
            raise MuninnConfigurationError("max_nodes must be >= 1")
        max_content_bytes = _coerce_int(self.max_content_bytes)
        if max_content_bytes is None or max_content_bytes < 1:
            raise MuninnConfigurationError("max_content_bytes must be >= 1")
        max_metadata_bytes = _coerce_int(self.max_metadata_bytes)
        if max_metadata_bytes is None or max_metadata_bytes < 1:
            raise MuninnConfigurationError("max_metadata_bytes must be >= 1")
        if self.encryption_passphrase is not None and not isinstance(
            self.encryption_passphrase, str
        ):
            raise MuninnConfigurationError("encryption_passphrase must be a string or None")
        if self.store_encryption and not self.encryption_passphrase:
            raise MuninnConfigurationError(
                "encryption_passphrase is required when store_encryption is enabled"
            )
        if self.integrity_passphrase is not None and not isinstance(
            self.integrity_passphrase, str
        ):
            raise MuninnConfigurationError("integrity_passphrase must be a string or None")
        if self.integrity_attestation and not self.integrity_passphrase:
            raise MuninnConfigurationError(
                "integrity_passphrase is required when integrity_attestation is enabled"
            )

    def resolved_path(self) -> Path:
        """The store path with ``~`` expanded (not symlink-resolved)."""
        return Path(self.db_path).expanduser()
