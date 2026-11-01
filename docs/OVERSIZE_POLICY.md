# Oversize Content Policy — RM-027

Before this slice, both ravens accepted content (and, in
Muninn, metadata) of any size: a caller could hand a store a
gigabyte string and the first sign of trouble would be the
disk, not the API. RM-027 replaces unbounded acceptance with
explicit, configurable ceilings and typed refusal.

## The ceilings

| Package | Field | Default | Measures |
|---|---|---|---|
| Muninn | `MuninnConfig.max_content_bytes` | 1048576 (1 MiB) | UTF-8 bytes of the stored content text — the raw string, or its JSON serialization for non-string content |
| Muninn | `MuninnConfig.max_metadata_bytes` | 65536 (64 KiB) | UTF-8 bytes of the metadata's serialized JSON form |
| Huginn | `HuginnConfig.max_content_bytes` | 1048576 (1 MiB) | UTF-8 bytes of the content string |

Size is counted in **bytes, not characters**: a multibyte
character costs what it costs the store. A 5-character string
of `é` is 10 bytes.

Huginn carries no metadata ceiling because Huginn memories
carry no caller metadata argument — the upsert payload is
content, category, importance, tags and valence. Muninn
carries both ceilings. (RM-036 applies these bounds to
adversarial tags/metadata shapes as its own slice.)

## The refusal

- Above the ceiling, the write raises the package's typed
  validation error (`MuninnValidationError` /
  `HuginnValidationError`) with the measured size and the
  ceiling in the message:
  `content size {n} bytes exceeds max_content_bytes ({c} bytes)`
  (and the `metadata size … max_metadata_bytes …` twin).
- The refusal happens **before any write**: a rejected
  `remember` / `upsert_memory` / `update` leaves the store
  byte-identical, and the store keeps working afterwards.
- Muninn enforces on both write paths (`remember`, and
  `update` for new content or metadata). Huginn enforces in
  the facade, before any backend is touched, so the policy
  holds identically on the local and Qdrant backends.
- At and below the ceiling, behaviour is exactly what it was
  before this slice.

## Configuration

Both fields are ordinary frozen-config fields (RM-017):
validated at construction (`>= 1`; a non-convertible value is
the package's typed configuration error), changeable only
through `dataclasses.replace`, which re-validates. The
defaults are generous on purpose — the founding workloads,
including the fuzz suites' 140 KB documents, sit far below
1 MiB — so an existing caller sees no change until it opts
into a tighter policy.

## Proof

`tests/test_oversize_policy.py` in both packages: boundary
tests below, at and above each ceiling; UTF-8 byte counting;
JSON content measured as its serialized text; refused writes
leaving node/document counts unchanged and the store
functional; config validation through construction and
`replace`. The suite fails in full against the pre-RM-027
packages (muninn 8 failed, huginn 5 failed). The new error
messages are pinned in the RM-018 goldens (CASE + TEMPLATE),
and the new config fields in the RM-019 API-surface goldens.
