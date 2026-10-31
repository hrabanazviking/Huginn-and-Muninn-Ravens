"""Typed exceptions for Muninn.

Libraries must not fake success: every failure leaves Muninn as one of
these typed errors and the caller (Bifröst, Hermes, a saga engine, …)
decides the policy.
"""

from __future__ import annotations


class MuninnError(Exception):
    """Base class for every error Muninn raises deliberately."""


class MuninnValidationError(MuninnError, ValueError):
    """Caller supplied an invalid argument (bad id, range, type, content).

    Raised *before* any write happens: a validation failure never leaves
    a partial mutation behind.
    """


class MuninnConfigurationError(MuninnError, ValueError):
    """A MuninnConfig value is out of its legal range."""


class MuninnStorageError(MuninnError):
    """The store could not be opened, read, written, or healed.

    Includes unrecoverable corruption (main store *and* every rolling
    backup failed integrity) — Muninn never silently starts empty over
    a corrupt store; data loss is always loud.
    """
