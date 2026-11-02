# Non-Database Files — RM-033

*The path is not a store: what sits there is not a database
at all.*

A caller can name any path. What sits at that path may be a
plain text file, an empty file, a directory, or something
stranger. Before this slice those shapes were answered only
incidentally, by roads built for other faults — and one of
them leaked a raw traceback:

* **A directory at the store path with a verified backup
  beside it raised a raw `IsADirectoryError` out of the
  open.** The directory failed the integrity probe, took the
  corruption road, and the restore's file copy
  (`shutil.copyfile` onto a directory) raised the built-in
  `OSError` straight through `open_store` — no typed error,
  no refusal message. (Measured pre-fix by probe, both
  packages.)
* **A directory without a backup was misreported as a
  corrupt store** — the typed refusal arrived, but it named
  the wrong fault.
* Text and empty files were already answered correctly by
  earlier slices (the corruption road, RM-032's zero-length
  rule) but were not pinned as a class of their own.

## The defined behaviour

All of it lives in each package's `_db.py` `open_store`
(the local backend only for Huginn; Qdrant has no local
files), and is pinned by `tests/test_non_database_files.py`
in both packages (8 tests each).

1. **Shape pre-flight, before everything.** A new first
   step, `_check_store_path_shape`, runs ahead of the
   RM-030 read-only pre-flight, ahead of any connection, and
   ahead of any restore attempt:
   * a **directory** at the store path raises the typed
     refusal `… store {path} is a directory, not a database
     file; refusing to open`. The directory and anything in
     it stand untouched; a backup beside it is neither
     consumed nor rotated, and a directory is never deleted
     or replaced to make room for a restore. Huginn's facade
     reports the refusal as an `unhealthy` `health()` dict,
     as with RM-030–RM-032.
   * any other existing **non-regular file** (FIFO, socket,
     device node) raises `… store {path} is not a regular
     file; refusing to open` — before any open is attempted
     on it (opening a FIFO could block; none of these can be
     a store).
   * a path that does not exist yet passes (the ordinary
     new-store case), as does any regular file — the later
     stages judge its contents.
2. **A text file is a corrupt store.** Long or short, a
   plain text file takes the corruption road: a verified
   rolling backup is restored over it (the restored store
   is the backup's state), else the typed refusal `… store
   {path} is corrupt and no rolling backup verified;
   refusing to start empty over lost memory`. A refused open
   leaves the file byte-identical and creates no sidecars.
   (RM-037 note: the corruption road now runs under the
   per-store coordination lock, so a refused open of an
   existing file may leave the zero-byte `.open-lock`
   coordination file beside it — named in
   `docs/FORMAT_STABILITY.md`, never read as data. The
   pre-flight refusals in rule 1 — directory, non-regular
   file, read-only — still create nothing at all.)
3. **An empty file is the RM-032 truncated store.** Zero
   bytes takes the same corruption road — restore a verified
   backup, else the same typed refusal — never SQLite's
   silently-fresh empty database.

The two new messages are RM-018 goldens: one CASE each in
both packages (`directory_store`, `nonfile_store`) plus
their TEMPLATE lines — muninn 45 cases / 62 templates,
huginn 50 cases / 63 templates, counted from the files.
