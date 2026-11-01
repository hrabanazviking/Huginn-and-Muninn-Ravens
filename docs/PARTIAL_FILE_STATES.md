# Partial-File States — RM-032

*Hostile filesystems, slice six: the store is several files,
and some of them are missing.*

A ravens store is not one file. Beside the main database sit
SQLite's `-wal` and `-shm` sidecars, the rolling `.bak-N`
backup generations, and the transient `.bak-tmp` that
`take_backup` writes a new snapshot to before rotating it
into place. A crash, a killed backup, a partial copy, or a
careless cleanup can leave any combination of those files
behind. Before this slice, three of those combinations had
no defined behaviour — and two of them lost memory silently:

* **A main store truncated to zero bytes opened as a fresh,
  empty store.** SQLite's own convention treats a zero-length
  file as a new database, so the open succeeded, the schema
  was applied, and every memory was simply gone — *even when
  a verified rolling backup sat beside the truncated file*.
  Worse, the empty store was then backed up on later opens,
  rotating the good generations out of the chain. (Measured
  pre-fix by probe, both packages: 0 nodes/documents after
  open, `recovered_from_backup` false, a new `.bak-2`
  containing the empty store.)
* **A non-empty WAL left without its main file was silently
  discarded.** The open took the new-store road, created a
  fresh main file, and the WAL — frames of committed memory
  whose store file was gone — vanished in the process.
  (Measured pre-fix by probe, both packages.)
* **A `.bak-tmp` left behind by a killed backup lingered**
  until some later backup happened to overwrite it, inviting
  any reader to mistake it for a backup generation.

## The defined behaviour

All of it lives in each package's `_db.py` `open_store` (the
local backend only for Huginn; Qdrant has no local files),
runs after the RM-030 read-only pre-flight, and is pinned by
`tests/test_partial_file_states.py` in both packages.

1. **Main present, WAL missing — normal.** This is the
   post-checkpoint state of every cleanly closed store. The
   store opens, all checkpointed data is intact, and no
   recovery is reported. The honest boundary: data committed
   but never checkpointed lives only in the WAL — if the WAL
   is deleted externally, that tail is gone and no code can
   recover it. The checkpointed store is what opens.
2. **Main present, WAL present but invalid — normal.** A
   garbage `-wal` (bad magic/checksums) is discarded by
   SQLite's own WAL recovery; the checkpointed data stands
   and no recovery is reported. A *valid* WAL is replayed by
   SQLite as always.
3. **Main truncated — the corruption road.** A partially
   truncated main file already failed `quick_check` and took
   the restore road; that is now pinned with a WAL beside it.
   A main file truncated to **zero bytes** is classified as
   truncated, not fresh, before any connection is made: the
   restore road runs — the newest verified `.bak-N` is
   restored (`recovered_from_backup` true, restored content
   is the backup's state), or, when no generation verifies,
   the typed refusal `… store {path} is corrupt and no
   rolling backup verified; refusing to start empty over
   lost memory` is raised and the zero-length file is left
   untouched for inspection. RM-033 will pin the neighbouring
   non-database shapes (text file, directory) the same way.
4. **Main missing, non-empty WAL present — restore or
   refuse.** The WAL's presence is evidence a store existed
   and its main file was lost. A verified backup is restored
   (the restore removes the orphaned sidecars), or opening
   raises the typed refusal naming the partial state —
   `… store {path} has a write-ahead log but no main file
   and no rolling backup verified; refusing to start empty
   over lost memory` (new RM-018 CASE + TEMPLATE in both
   packages; Huginn's facade reports it as an `unhealthy`
   `health()` dict, as with RM-030/RM-031). On refusal
   nothing is created: no fresh main file appears and the
   WAL stands for inspection. An *empty* WAL carries no
   frames and is not evidence: main missing with only an
   empty (or absent) WAL is an ordinary new store. Main
   missing with backups but no WAL is likewise a new store
   — deleting the main file remains how a store is removed;
   its generations stay on disk for a human to restore by
   hand, and are never silently resurrected or deleted.
5. **`.bak-tmp` leftover — removed on open, never read.**
   The temp snapshot is transient by contract (see
   `docs/FORMAT_STABILITY.md`): the open removes a leftover
   `.bak-tmp` before anything else and never treats it as a
   store or a restore candidate. The proof is adversarial:
   a *complete, valid* store copy sitting at the `.bak-tmp`
   path, beside a corrupt main and no generation, still gets
   the typed refusal — not a resurrection — and when both a
   generation and a valid temp exist, the restore provably
   comes from the generation.

## Proof

New `tests/test_partial_file_states.py`: muninn 10 tests,
huginn 10 tests — WAL missing, garbage WAL, zero-length
restore, zero-length refusal (exact message, file untouched,
refusal repeatable), partial truncation with WAL, missing
main with WAL (restore and refusal, exact message, evidence
preserved), temp removal on a *quiet* open (no backup taken,
generation byte-identical, so the removal is the new cleanup
and not a backup side effect), temp never a candidate, and
generation-beats-temp. **Negation: 7 failed / 3 passed per
package against the pre-RM-032 installed packages** (RM-031
venv) — the failures are exactly the three defects and the
temp-removal pins; the passes are the behaviours that
already held (WAL missing, garbage WAL, generation restore).

No public API, signature, or schema change (RM-003 freeze +
RM-004 snapshot green); the open's error behaviour changed,
so the Bifröst contract re-verification was run before
banking, as with RM-030/RM-031.
