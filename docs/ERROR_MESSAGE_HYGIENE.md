# Error-Message Hygiene — RM-054

Threat TH-14 (`docs/THREAT_MODEL.md`): typed errors
deliberately carried the store path the caller supplied and,
on storage failures, the underlying SQLite/client exception
text — text the ravens do not control and had never scanned
for file contents, keys, or paths beyond the caller's own.
RM-018 pinned the message *shapes*; this slice controls what
may ride inside them.

## The rule

A typed error's message is built only from:

- fixed text written in the package;
- values the package itself computed or validated (counts,
  sizes, ids, type names, enum members);
- the store path, Qdrant URL and collection name the caller
  itself supplied in config (the standing allowance — a
  caller cannot be leaked its own configuration);
- the underlying exception's **class name** — never its text.

The underlying exception's full text remains available to
the caller through the exception chain (every wrap site
raises `from exc`); it simply never becomes part of a string
these packages format. The non-raising error surfaces follow
the same rule because they are formatted from typed
messages: Huginn's `health()` error string, the `auto`
fallback reason, and a flight's `error` field — and the
facade still applies RM-045's key scrub to the strings it
reports, as defence in depth.

## Why class name, not scrubbed text

RM-045 masked the one known secret (the Qdrant API key) out
of client text and left the rest. That cannot bound text the
ravens do not control:

- **File contents.** SQLite generates some of its error
  text from the store file itself. A trigger's
  `RAISE(ABORT, '…')` message is file content, and before
  this slice it rode verbatim into the typed error on both
  the write road (`… write failed during …: <trigger text>`)
  and the open road (`… could not be prepared: <trigger
  text>`) — proven by probe against the RM-053 tree, and
  pinned as a regression by the trigger fixtures in
  `tests/test_error_message_hygiene.py`.
- **Keys beyond the known one.** A server or proxy error can
  quote any credential it saw, a store trigger can name a
  passphrase, and neither is enumerable in advance.
- **Foreign paths.** Underlying text can name files the
  caller never supplied (an attached database, a server-side
  path, a proxy's filesystem).

Scrubbing a list of known strings cannot prove a negative
about arbitrary text. Not forwarding the text can.

## What changed

Fourteen wrap sites, one shape each:

- **SQLite, both packages** (`_db.py`): the two
  `could not be prepared` branches per package now end with
  the exception's class name (`_db._error_kind`).
- **SQLite write guards** (Muninn `core.py`, Huginn
  `local_backend.py`): the generic branch likewise. The two
  classified branches keep their fixed texts — locked
  (RM-031) and, new in this slice, disk-full: an
  `_is_full_error` classification (SQLITE_FULL result code
  13, or SQLite's canonical wording) emits the package's own
  `database or disk is full` line, so RM-029's message shape
  survives without echoing SQLite to get it.
- **Qdrant** (Huginn `qdrant_backend.py`): the eight wrap
  sites that used RM-045's text scrub now take the class
  name from the same helper seam (`_scrub`, kept name,
  changed contract). `scrub_api_key` itself remains,
  applied by the facade to reported error strings.

Deliberate message changes, recorded per the RM-018 rule:
the seven Qdrant CASE lines in Huginn's golden now end in
`RuntimeError` (the fake clients' class) instead of the
fakes' wording (`boom` / `down` / `nope`), and RM-045's
transport tests assert absence of the whole client wording
where they asserted the `***` mask before. The
`could not be prepared` branches also gained their first
deterministic CASE triggers in both packages (a store
trigger aborting the prepare-time meta insert — the
RM-018 doc's "cannot be triggered deterministically" note
is superseded for this site), as did the generic write-guard
branch. No TEMPLATE line changed except by addition: the
new fixed disk-full branch adds one template per package.

## Scope, stated plainly

- Validation messages that echo a caller's own argument
  value back to that same caller (`importance … got
  'high'`) are deliberate, RM-018-pinned API. TH-14's
  object was *uncontrolled* text; a value the caller just
  handed over, returned to that caller, is not it.
- Errors the packages do not type (a third-party
  constructor raising raw inside an optional extra, for
  example) are not typed errors and are out of scope; the
  typed wraps are the contract.
- TH-14's register line is re-checked at the RM-056 part
  gate, per the threat model's rule.

## How it is proven

`tests/test_error_message_hygiene.py` in both packages
(muninn 7, huginn 8): a combined planted leak — a stored
memory's exact content, a foreign absolute path, the Qdrant
API key and both passphrases — is placed in trigger text,
client error text and wrong-passphrase attempts, and every
resulting typed message (plus Huginn's `health()` error,
fallback reason and flight `error`) is scanned for every
token; the surviving diagnostic is pinned to the exception
chain (`__cause__`), the allowed own-path presence is
pinned, and an AST pin forbids any raise site from
interpolating an exception variable except through
`_error_kind` / `_scrub`. Negation against the RM-053 tree:
muninn **5 failed / 2 passed**, huginn **5 failed /
3 passed** — the passes are exactly the shapes that were
already fixed text (disk-full, wrong-passphrase).

Live Qdrant and sentence-transformers stay NOT PROVEN: all
network proof is against fake clients, as in RM-045/RM-046.
