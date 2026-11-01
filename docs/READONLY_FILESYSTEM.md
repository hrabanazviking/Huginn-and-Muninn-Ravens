# Read-Only Filesystem Behaviour — RM-030

*Hostile filesystems, slice four: the store's home cannot be
written to.*

A Muninn or Huginn local store lives in WAL mode: opening it is
itself a write (the schema is applied, the schema-version marker
is stored, WAL sidecars are created and checkpointed). Before
this slice there was no defined behaviour for a store whose
location is read-only — the failure depended on exactly where
SQLite or the filesystem happened to refuse first, and could
escape as a raw `sqlite3`/`OSError`, or worse, be mistaken for
corruption and sent down the backup-restore road, which would
try to *write* a backup over a read-only location while telling
the caller the store was corrupt.

## The defined behaviour

**There is no read-only mode.** A store is opened for writing
or not at all. Opening a store whose location is read-only
fails loudly and immediately with the package's typed storage
error and one stable message shape, pinned by the RM-018
goldens:

- Muninn: `muninn store {path} is read-only and cannot be opened
  for writing` (`MuninnStorageError`)
- Huginn: `huginn store {path} is read-only and cannot be opened
  for writing` (`HuginnStorageError`; the facade's `health()`
  keeps its never-raises contract and reports the same refusal
  as an `unhealthy` dict with `error_type: HuginnStorageError`)

"Immediately" is structural, not hopeful: the refusal happens in
a pre-flight at the head of `open_store` in each package's
`_db.py`, *before* any connection is attempted — so it never
waits out the configured busy timeout, never probes the store,
and never reaches the integrity/restore logic. The failed open
touches nothing: the store file's bytes are unchanged, no WAL
sidecar is created, and no backup generation is taken, restored
or rotated. Unmark the location and the same store opens with
its data intact and zero recovery performed.

A location is read-only when either:

1. **It is marked read-only** — the store file, or the directory
   that must hold it (the parent, or the nearest existing
   ancestor when the parent does not exist yet), carries no
   write permission bit at all (`mode & 0o222 == 0`: the
   `chmod 444` file, the `chmod 555` directory, a read-only
   snapshot). The bit check is deliberate: a file or directory
   marked read-only is read-only by its owner's declaration,
   and the refusal holds even for a process privileged enough
   to override the bits — which is also what makes the
   behaviour testable by any user, at any privilege level.
2. **This process cannot write there** — `os.access(..., W_OK)`
   fails, as on a genuinely read-only mount or under an ACL
   denial. Behind the pre-flight, every stage of the open
   (parent creation, the integrity probe, the connection, the
   schema preparation) also classifies its failures: a
   filesystem errno `EROFS`/`EACCES`/`EPERM` or one of SQLite's
   read-only wordings (`attempt to write a readonly database`,
   `unable to open database file`) is translated into the same
   typed read-only error instead of the corruption road or a
   raw exception.

Locked-store contention is *not* read-only and is not claimed
here: a store that is merely busy still honours the busy
timeout (that behaviour is RM-031's slice to define).

## How it is proven

Pinned by `tests/test_readonly_filesystem.py` in both packages
(muninn 4 tests, huginn 3):

- Muninn: an existing store file marked `0o444` is refused with
  the exact message in under 5 s despite a 60 s busy timeout —
  never a raw `sqlite3.Error`/`OSError`, never the word
  "corrupt" — with the file's SHA-256 unchanged, no backup
  taken, and a clean zero-recovery reopen once unmarked; a
  store inside a `0o555` directory is refused the same way; a
  *new* store inside a `0o555` directory is refused and never
  created; a new store below a read-only ancestor (through a
  not-yet-existing subdirectory) is refused and the
  subdirectory is never created.
- Huginn: the same refusal for the local backend at file level;
  the facade's `health()` reporting the refusal as `unhealthy`
  with the typed error named while a real write raises it; a
  new store in a read-only directory refused and never created.

Negation: all seven tests fail against the pre-RM-030 installed
packages (RM-029 venv) — as a privileged process the old code
simply opened the marked stores and wrote to them, with no
read-only behaviour defined at all.

The Qdrant backend has no local file and is untouched by this
slice; a live Qdrant round-trip remains NOT PROVEN.
