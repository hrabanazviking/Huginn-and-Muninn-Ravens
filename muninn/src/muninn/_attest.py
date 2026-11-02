"""Integrity attestation for Muninn (RM-050): an optional
HMAC chain over ``activation_log``, per threat TH-10 in
``docs/THREAT_MODEL.md`` (record: ``docs/INTEGRITY_ATTESTATION.md``).

The activation log is the store's audit trail — what was
activated, when, with what valence and source — and before
this slice nothing detected a hand that edited it by raw SQL:
``quick_check`` proves SQLite's structure, not the caller's
truth. With ``integrity_attestation`` on, every appended log
row extends an HMAC-SHA256 chain:

    head₀   = HMAC(key, genesis ‖ salt)
    headₙ₊₁ = HMAC(key, headₙ ‖ memory_id ‖ activated_at ‖
                        repr(emotional_valence) ‖ source)

The chain key is derived from the caller's passphrase with
PBKDF2-HMAC-SHA256 (stdlib — the whole slice is stdlib, no
extra) over a per-store random salt, and is **never stored**:
the store carries only the salt, the iteration count, the
current head and the chained row count, all as ``meta`` rows,
so the schema — the contracted ``activation_log`` table
included — is untouched (the RM-049 precedent). A tamperer
with the file but without the passphrase can edit, insert or
delete log rows, but cannot recompute a valid head; the next
attested open recomputes the chain over the rows as they stand
and reports the mismatch in ``health()``.

The log is append-only through the API (no method deletes or
rewrites a log row), which is what makes a single head + count
sufficient evidence: any divergence between the recomputed
chain and the stored head/count is tampering, a torn chain
write, or a bug — all three are reported the same way, loudly,
and none is silently repaired.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path

from .errors import MuninnStorageError

PBKDF2_ITERATIONS = 600_000

_META_MARKER = "attestation_version"
_META_SALT = "attestation_salt"
_META_ITERATIONS = "attestation_iterations"
_META_HEAD = "attestation_head"
_META_COUNT = "attestation_count"
_GENESIS = b"muninn activation attestation genesis v1"

# The one row shape the chain is computed over, in id order —
# the log's append order (spelled out at each call site so the
# RM-040 audit sees only constant SQL).


def _derive_key(passphrase: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, iterations, dklen=32
    )


def _row_bytes(memory_id: int, activated_at: str, emotional_valence: float, source: str) -> bytes:
    return (
        f"{memory_id}\x1f{activated_at}\x1f{emotional_valence!r}\x1f{source}"
    ).encode()


class AttestationChain:
    """The running chain state for one open store."""

    def __init__(self, key: bytes, salt: bytes, head: str, count: int):
        self._key = key
        self._salt = salt
        self.head = head
        self.count = count

    def _genesis_head(self) -> str:
        return hmac.new(self._key, _GENESIS + self._salt, hashlib.sha256).hexdigest()

    def advance(
        self, memory_id: int, activated_at: str, emotional_valence: float, source: str
    ) -> None:
        """Extend the chain over one appended log row."""
        self.head = hmac.new(
            self._key,
            bytes.fromhex(self.head)
            + _row_bytes(memory_id, activated_at, emotional_valence, source),
            hashlib.sha256,
        ).hexdigest()
        self.count += 1

    def recompute(self, conn: sqlite3.Connection) -> tuple[str, int]:
        """The chain over the log rows as they stand in ``conn``."""
        head = self._genesis_head()
        count = 0
        for memory_id, activated_at, valence, source in conn.execute(
            "SELECT memory_id, activated_at, emotional_valence, source"
            " FROM activation_log ORDER BY id"
        ):
            head = hmac.new(
                self._key,
                bytes.fromhex(head)
                + _row_bytes(int(memory_id), str(activated_at), float(valence), str(source)),
                hashlib.sha256,
            ).hexdigest()
            count += 1
        return head, count


def new_attestation_chain(passphrase: str) -> tuple[AttestationChain, dict[str, str]]:
    """A fresh chain for a new (or newly attested) store + its meta.

    The returned meta carries the marker, salt and iteration
    count; head and count are written by the establish step,
    after the chain has been bootstrapped over any rows the
    store already holds.
    """
    salt = secrets.token_bytes(16)
    key = _derive_key(passphrase, salt, PBKDF2_ITERATIONS)
    chain = AttestationChain(key, salt, "", 0)
    chain.head = chain._genesis_head()
    meta = {
        _META_MARKER: "1",
        _META_SALT: base64.b64encode(salt).decode("ascii"),
        _META_ITERATIONS: str(PBKDF2_ITERATIONS),
    }
    return chain, meta


def open_attestation_chain(
    passphrase: str, meta: dict[str, str], db_path: Path
) -> AttestationChain:
    """Rebuild the chain state from a marked store's meta.

    A malformed header refuses typed. A *wrong passphrase*
    cannot be detected here — the key is never stored, so
    there is nothing to check it against until the chain is
    verified over the rows: a wrong key simply recomputes to
    a different head, and verification reports tampering.
    That is the honest shape of a keyless chain, and it is
    why the marker open (flag off) refuses instead: an
    unattested open must never silently serve a store whose
    owner asked for attestation.
    """
    try:
        salt = base64.b64decode(meta[_META_SALT])
        iterations = int(meta[_META_ITERATIONS])
        head = meta[_META_HEAD]
        count = int(meta[_META_COUNT])
        bytes.fromhex(head)
    except (KeyError, ValueError) as exc:
        raise MuninnStorageError(
            f"muninn store {db_path} carries an unreadable attestation "
            f"header; refusing to open"
        ) from exc
    key = _derive_key(passphrase, salt, iterations)
    return AttestationChain(key, salt, head, count)


def chain_head_meta(chain: AttestationChain) -> dict[str, str]:
    """The ``meta`` rows carrying the chain's current head/count."""
    return {_META_HEAD: chain.head, _META_COUNT: str(chain.count)}


def sync_chain_head(chain: AttestationChain, meta: dict[str, str], db_path: Path) -> None:
    """Reset a chain's head/count from stored meta (no key work).

    The stored meta is the authority at the start of every
    activation transaction: if an earlier transaction rolled
    back (the RM-029 write guard), the in-memory advance went
    with it, and the next write must chain from the head the
    store actually holds — never from memory of a write that
    did not land.
    """
    try:
        head = meta[_META_HEAD]
        count = int(meta[_META_COUNT])
        bytes.fromhex(head)
    except (KeyError, ValueError) as exc:
        raise MuninnStorageError(
            f"muninn store {db_path} carries an unreadable attestation "
            f"header; refusing to write"
        ) from exc
    chain.head = head
    chain.count = count


def meta_from_connection(conn: sqlite3.Connection) -> dict[str, str] | None:
    """The store's attestation ``meta`` rows, or None if unmarked."""
    rows = conn.execute(
        "SELECT key, value FROM meta WHERE key LIKE 'attestation_%'"
    ).fetchall()
    meta = {str(k): str(v) for k, v in rows}
    return meta if _META_MARKER in meta else None


def probe_attestation(db_path: Path) -> tuple[bool, dict[str, str] | None]:
    """Pure pre-open probe: (readable, attestation meta).

    Never writes. ``readable`` is False for every case a read
    cannot settle (no file yet, no meta table, an unreadable
    or corrupt file): ``open_store``'s own corruption road
    judges those, and the caller's deferred post-open proof
    covers a store restored from an attested backup (the
    RM-049 pattern).
    """
    if not db_path.is_file():
        return False, None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            meta = meta_from_connection(conn)
        finally:
            conn.close()
    except sqlite3.Error:
        return False, None
    return True, meta


def verify_attestation(conn: sqlite3.Connection, chain: AttestationChain) -> str:
    """Recompute the chain over the log as it stands.

    Returns ``"ok"`` when the recomputed head and count equal
    the stored head and count the chain was opened with, and
    ``"tamper_detected"`` otherwise — an edited, inserted or
    deleted row, a rewritten head, or a wrong passphrase all
    land in the second bucket, by design indistinguishable.
    """
    head, count = chain.recompute(conn)
    if count == chain.count and hmac.compare_digest(head, chain.head):
        return "ok"
    return "tamper_detected"
