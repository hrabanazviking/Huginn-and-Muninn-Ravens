"""Store encryption for Huginn (RM-049): application-level envelope
encryption of the content-bearing values, per the RM-048 decision
record in ``docs/STORE_ENCRYPTION.md`` (threat TH-09).

The design in one paragraph: with ``store_encryption`` on, each
store holds one random 32-byte **data key**, wrapped under a
key-encryption key derived from the caller's passphrase with
PBKDF2-HMAC-SHA256 (stdlib). Content values are sealed with
AES-256-GCM from the one bounded ``cryptography`` extra — the
stdlib has no cipher, and no hand-rolled AEAD is permitted —
and stored as ``enc:v1:`` text envelopes in the same TEXT
columns, so the schema and the store machinery are untouched
and the file stays openable by plain sqlite3 (structure,
category and importance stay plaintext — content
confidentiality is the purchase, per the decision record).
``content_hash`` becomes a keyed HMAC lookup tag under a
subkey derived from the data key, so the idempotent-store
path keeps working without ever storing a plaintext hash of
the content, and the term index stores the same keyed tag of
each token in place of the token.

The extra is imported lazily, only when encryption is switched
on, through :mod:`importlib` (so the type floor never has to
resolve a package an installing host may not have); a missing
extra with the flag on is a typed configuration error, never an
import crash mid-store.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib
import importlib.util
import secrets
import sqlite3
from pathlib import Path
from typing import Any

from .errors import HuginnConfigurationError, HuginnStorageError

ENVELOPE_PREFIX = "enc:v1:"
PBKDF2_ITERATIONS = 600_000

_META_MARKER = "encryption_version"
_META_SALT = "encryption_salt"
_META_ITERATIONS = "encryption_iterations"
_META_WRAPPED_KEY = "encryption_wrapped_key"
_META_KEY_CHECK = "encryption_key_check"
_KEY_CHECK_CONSTANT = "huginn store encryption key check v1"
_WRAP_AAD = b"meta.encryption_wrapped_key"
_KEY_CHECK_AAD = "meta.encryption_key_check"


def require_cryptography() -> None:
    """The ``encryption`` extra must be importable (typed refusal)."""
    if importlib.util.find_spec("cryptography") is None:
        raise HuginnConfigurationError(
            "store_encryption requires the 'cryptography' package; "
            "install huginn with its 'encryption' extra"
        )


def _load_aesgcm() -> Any:
    module = importlib.import_module("cryptography.hazmat.primitives.ciphers.aead")
    return module.AESGCM


def _derive_kek(passphrase: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, iterations, dklen=32
    )


class StoreCipher:
    """Seals and opens one store's values under its data key."""

    def __init__(self, data_key: bytes):
        aesgcm = _load_aesgcm()
        self._aesgcm = aesgcm(data_key)
        self._lookup_key = hmac.new(
            data_key, b"huginn lookup key v1", hashlib.sha256
        ).digest()

    def encrypt(self, text: str, aad: str) -> str:
        """Seal ``text`` as an ``enc:v1:`` envelope bound to ``aad``."""
        nonce = secrets.token_bytes(12)
        sealed = self._aesgcm.encrypt(nonce, text.encode("utf-8"), aad.encode("utf-8"))
        return ENVELOPE_PREFIX + base64.b64encode(nonce + sealed).decode("ascii")

    def decrypt(self, value: str, aad: str) -> str:
        """Open an envelope; a non-envelope value passes through.

        Every value in an encrypted store's content columns is an
        envelope by construction, so the passthrough only ever
        serves values written before this road existed in stores
        the open-time proof has already accepted as plain.
        """
        if not value.startswith(ENVELOPE_PREFIX):
            return value
        raw = base64.b64decode(value[len(ENVELOPE_PREFIX) :])
        opened = self._aesgcm.decrypt(raw[:12], raw[12:], aad.encode("utf-8"))
        return bytes(opened).decode("utf-8")

    def lookup_tag(self, data: bytes) -> str:
        """Keyed lookup tag: HMAC-SHA256 under the lookup subkey."""
        return hmac.new(self._lookup_key, data, hashlib.sha256).hexdigest()


def new_store_cipher(passphrase: str) -> tuple[StoreCipher, dict[str, str]]:
    """A fresh cipher for a new store, plus its ``meta`` rows."""
    data_key = secrets.token_bytes(32)
    salt = secrets.token_bytes(16)
    kek = _derive_kek(passphrase, salt, PBKDF2_ITERATIONS)
    aesgcm = _load_aesgcm()
    nonce = secrets.token_bytes(12)
    wrapped = aesgcm(kek).encrypt(nonce, data_key, _WRAP_AAD)
    cipher = StoreCipher(data_key)
    meta = {
        _META_MARKER: "1",
        _META_SALT: base64.b64encode(salt).decode("ascii"),
        _META_ITERATIONS: str(PBKDF2_ITERATIONS),
        _META_WRAPPED_KEY: base64.b64encode(nonce + wrapped).decode("ascii"),
        _META_KEY_CHECK: cipher.encrypt(_KEY_CHECK_CONSTANT, _KEY_CHECK_AAD),
    }
    return cipher, meta


def open_store_cipher(
    passphrase: str, meta: dict[str, str], db_path: Path
) -> StoreCipher:
    """Unwrap a marked store's data key — the open-time key proof.

    A wrong passphrase fails the unwrap (or the key check) and
    raises the typed storage error; nothing has been written.
    """
    try:
        salt = base64.b64decode(meta[_META_SALT])
        iterations = int(meta[_META_ITERATIONS])
        wrapped_raw = base64.b64decode(meta[_META_WRAPPED_KEY])
    except (KeyError, ValueError) as exc:
        raise HuginnStorageError(
            f"huginn store {db_path} carries an unreadable encryption "
            f"header; refusing to open"
        ) from exc
    kek = _derive_kek(passphrase, salt, iterations)
    aesgcm = _load_aesgcm()
    try:
        data_key = bytes(aesgcm(kek).decrypt(wrapped_raw[:12], wrapped_raw[12:], _WRAP_AAD))
    except Exception as exc:
        raise HuginnStorageError(
            f"huginn store {db_path} is encrypted and the supplied "
            f"passphrase does not unlock it; refusing to open"
        ) from exc
    cipher = StoreCipher(data_key)
    try:
        check = cipher.decrypt(meta[_META_KEY_CHECK], _KEY_CHECK_AAD)
    except Exception as exc:
        raise HuginnStorageError(
            f"huginn store {db_path} is encrypted and the supplied "
            f"passphrase does not unlock it; refusing to open"
        ) from exc
    if check != _KEY_CHECK_CONSTANT:
        raise HuginnStorageError(
            f"huginn store {db_path} is encrypted and the supplied "
            f"passphrase does not unlock it; refusing to open"
        )
    return cipher


def meta_and_count_from_connection(
    conn: sqlite3.Connection, count_sql: str
) -> tuple[dict[str, str] | None, int]:
    """The store's encryption ``meta`` rows and content-row count.

    ``count_sql`` is one of the caller's own constant count
    queries (the RM-040 audit shape: SQL arrives as a named
    constant, never built here). Returns the meta rows when the
    store carries the encryption marker, else None, plus the
    row count the query reports.
    """
    rows = conn.execute(
        "SELECT key, value FROM meta WHERE key LIKE 'encryption_%'"
    ).fetchall()
    meta = {str(k): str(v) for k, v in rows}
    row = conn.execute(count_sql).fetchone()
    return (meta if _META_MARKER in meta else None), (int(row[0]) if row else 0)


def probe_store(
    db_path: Path, count_sql: str
) -> tuple[bool, dict[str, str] | None, int]:
    """Pure pre-open probe: (readable, encryption meta, row count).

    Never writes. ``readable`` is False for every case a read
    cannot settle (no file yet, no meta table, an unreadable or
    corrupt file): ``open_store``'s own corruption road judges
    those, and the caller's deferred post-open proof covers a
    store restored from an encrypted backup.
    """
    if not db_path.is_file():
        return False, None, 0
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            meta, count = meta_and_count_from_connection(conn, count_sql)
        finally:
            conn.close()
    except sqlite3.Error:
        return False, None, 0
    return True, meta, count
