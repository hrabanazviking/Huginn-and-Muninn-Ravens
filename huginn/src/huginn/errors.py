"""Typed exceptions for Huginn.

Libraries must not fake success: failures leave Huginn as one of
these typed errors and the caller decides the policy. The single
designed exception is ``backend="auto"``: a missing Qdrant there is a
*configuration fact*, answered by the local backend and reported in
``health()`` — never by raising into the caller.
"""

from __future__ import annotations


class HuginnError(Exception):
    """Base class for every error Huginn raises deliberately."""


class HuginnValidationError(HuginnError, ValueError):
    """Caller supplied an invalid argument. Raised before any write."""


class HuginnConfigurationError(HuginnError, ValueError):
    """A HuginnConfig value is illegal, or a configured optional
    dependency (qdrant-client, sentence-transformers) is missing."""


class HuginnStorageError(HuginnError):
    """The local store could not be opened, read, written, or healed,
    including unrecoverable corruption (main store and every rolling
    backup failed integrity). Data loss is always loud."""


class HuginnBackendError(HuginnError):
    """The selected backend failed at operation time (e.g. an explicit
    Qdrant backend whose server is unreachable)."""
