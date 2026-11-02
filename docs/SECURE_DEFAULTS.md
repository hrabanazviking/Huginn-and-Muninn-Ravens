# Secure Defaults — RM-055

Threat TH-15 (`docs/THREAT_MODEL.md`): a default that is
convenient in development and wrong in deployment — backup
counts, timeouts, `auto` fallback silently degrading to
local, plaintext localhost Qdrant — ships to every caller
who never opens the config. The Part IV slices judged
defaults piecemeal as each field landed; this slice is the
one recorded review of **every** config default in both
packages, judged for safety, with the judgements recorded
here and in the guides.

## Method

Every field of `MuninnConfig` (19 fields) and
`HuginnConfig` (19 fields) was read against the threat
model and judged in one of four classes:

- **Safe-off / safe-none** — a capability that could leak,
  execute, download, or trust is off, or a secret is
  absent, by default. The secure posture is the default
  posture.
- **Safety-positive on** — the default being on *is* the
  protection (backups); its cost surface is judged with
  it.
- **Bounded** — a timeout, ceiling, or count with a finite
  validated value; nothing waits or grows without limit
  by default.
- **Compatibility-kept** — a default kept for the founding
  contracts (Bifröst constructs both configs nearly bare;
  recorded behaviour is pinned by earlier slices), with
  its risk and its mitigation named plainly, and the
  stricter road documented as an opt-in or opt-out.

`tests/test_secure_defaults.py` in both packages pins the
exact default of every field, the field *set* itself (a
new field fails the suite until it is reviewed here), the
off/on posture of the security flags, and that this
record and the guide name every field.

## Outcome: no default changed

That is the honest result of the review, not a shortcut.
Every default that could leak content, weaken transport,
run untrusted code, or fetch from the network is already
off or loopback-confined; every default that is on is
safety-positive or bounded; and each compatibility-kept
default below would do real harm if flipped blindly —
refusing legitimate stores at open, breaking the
no-config Bifröst contract, or demanding a passphrase a
default cannot invent. The three judgements a deploying
reader most needs to know:

1. `strict_path_safety=False` (both packages) is the
   review's most deliberate convenience keep — see its
   row. Locked-down deployments should turn it on.
2. Huginn's `backend="auto"` fallback is **not silent**:
   the probe is lazy, loopback by default, and bounded by
   `qdrant_timeout`, and the fallback reason and the
   effective backend are reported in `health()`.
   Deployments that must never touch the network set
   `backend="local"`; deployments that must fail loud
   set `backend="qdrant"`.
3. `store_encryption=False` and
   `integrity_attestation=False` (Muninn) cannot be on
   by default — each needs a passphrase, and a default
   must never invent a secret. Once a store is marked,
   it refuses unprotected opens, so the protection is
   complete from the moment a deployment opts in.

## Muninn — field by field

| Field | Default | Class | Judgement |
|---|---|---|---|
| `db_path` | `"~/.hermes/memory/muninn_hebbian.db"` | Bounded | Under the caller's own home; the file is created owner-only `0600` (RM-042) and its backups inherit its permissions (RM-043). Keep. |
| `learning_rate` | `0.1` | Bounded | Semantic rate, validated to (0, 1]; no security surface. Keep. |
| `decay_half_life_days` | `30.0` | Bounded | Semantic; validated > 0; decay runs only when the caller invokes it. Keep. |
| `confidence_half_life_days` | `90.0` | Bounded | Same judgement as `decay_half_life_days`. Keep. |
| `prune_threshold` | `0.01` | Bounded | Deletion happens only inside a caller-invoked `decay()`; validated to [0, 1). Keep. |
| `consolidation_threshold` | `0.8` | Bounded | Semantic; validated to (0, 1]. Keep. |
| `busy_timeout_ms` | `5000` | Bounded | A locked store is awaited five seconds, then a typed error (RM-031) — never an infinite wait. `0` is reachable only by explicit choice. Keep. |
| `backup_keep` | `3` | Safety-positive | Three generations is the recovery/confidentiality balance: the copies inherit the store's own permissions (RM-043) and `secure_forget` purges every generation (RM-051). `0` disables recovery and is explicit-only; the guides warn against it. Keep. |
| `auto_backup` | `True` | Safety-positive on | The on default *is* the durability protection; a backup is taken only when the store changed, and the copies it creates are judged under `backup_keep` above. Keep. |
| `max_nodes` | `20000` | Bounded | The ancestor's backpressure ceiling; bounds store growth (TH-13's thrash surface). Keep. |
| `max_content_bytes` | `1048576` | Bounded | The RM-027 oversize ceiling; oversize writes are refused typed, before any write. Keep. |
| `max_metadata_bytes` | `65536` | Bounded | The RM-027 metadata ceiling, same discipline. Keep. |
| `strict_path_safety` | `False` | Compatibility-kept | The recorded behaviour since the founding build: paths are `~`-expanded, never symlink-resolved, parents unchecked. Flipping it by default would refuse legitimate deployments (a home directory reached through a symlink) at open, with no migration path. The residual risk needs a local attacker who can already write the caller's directories (TH-02). The opt-in is documented in the guide for locked-down deployments. Keep, named plainly. |
| `debug_log_content` | `False` | Safe-off | No log record at any level carries memory content by default (TH-05, RM-044). Keep. |
| `store_encryption` | `False` | Safe-off | Cannot default on: it needs the `encryption` extra and a passphrase a default cannot invent. A marked store refuses plain opens for its whole life, so opting in is complete (RM-049). Deployments holding sensitive memories should enable it; the guide now names the field (it was missing — fixed in this slice). Keep. |
| `encryption_passphrase` | `None` | Safe-none | No secret is ever defaulted or invented; required and validated when `store_encryption` is on; excluded from `repr`, never stored or logged. Keep. |
| `integrity_attestation` | `False` | Safe-off | Same shape as `store_encryption`: needs `integrity_passphrase`. A marked store refuses unattested opens (RM-050). Keep. |
| `integrity_passphrase` | `None` | Safe-none | Same judgement as `encryption_passphrase`. Keep. |
| `max_spread_candidates` | `100000` | Bounded | The RM-053 query-cost ceiling (TH-13); a bite returns the partial result and is visible in `last_spread_activation_stats`. Keep. |
| `cache_size` | `0` | Safe-off | The RM-063 warm `get_node` cache, off by default: a cache trades freshness for speed and is per-object only (another object's writes are not seen until eviction or an own write), so the safe default is no cache — every read reads the store. When explicitly enabled it is bounded (validated `>= 0`, LRU eviction at the bound) and own writes always invalidate. Judged at RM-063, the slice that added it. Keep. |

## Huginn — field by field

| Field | Default | Class | Judgement |
|---|---|---|---|
| `backend` | `"auto"` | Compatibility-kept | The Bifröst contract: a no-config Huginn must come up on the local backend when no Qdrant exists. The fallback is not silent — the probe is lazy and loopback-only by default, bounded by `qdrant_timeout`, and the reason plus the effective backend/embedder are reported in `health()`. `backend="local"` never touches the network; `backend="qdrant"` fails loud. Keep, with both roads in the guide. |
| `qdrant_url` | `"http://localhost:6333"` | Compatibility-kept | Plaintext confined to loopback: the same config refuses a non-loopback `http` URL at construction unless `allow_insecure_http` is set (RM-045, TH-06). Keep. |
| `qdrant_api_key` | `None` | Safe-none | No credential is invented; when supplied, the key is handed only to the client constructor, excluded from `repr`, and never logged or carried in an error message (RM-045, RM-054). Keep. |
| `collection_name` | `"huginn_memories"` | Bounded | A neutral namespace name; no security surface. Keep. |
| `local_db_path` | `"~/.hermes/memory/huginn_local.db"` | Bounded | Same judgement as Muninn's `db_path` (RM-042, RM-043). Keep. |
| `embedder` | `"tfidf"` | Safe-off | The only embedder needing no network, no model download, and no extra. `sentence-transformers`, which downloads a model on first use, is opt-in only. Keep. |
| `vector_dim` | `384` | Bounded | Validated >= 8; sizes the hashing embedder and the Qdrant collection. Keep. |
| `st_model` | `"all-MiniLM-L6-v2"` | Safe-off | Inert unless the opt-in `sentence-transformers` embedder is chosen; naming a model is not fetching it. Keep. |
| `qdrant_timeout` | `2.0` | Bounded | Finite and validated > 0; bounds the `auto` probe and every Qdrant call. Keep. |
| `busy_timeout_ms` | `5000` | Bounded | Same judgement as Muninn's — and the same value; the shared defaults agree, pinned by both suites. Keep. |
| `backup_keep` | `3` | Safety-positive | Same judgement as Muninn's, same value. Keep. |
| `auto_backup` | `True` | Safety-positive on | Same judgement as Muninn's. Keep. |
| `max_content_bytes` | `1048576` | Bounded | The RM-027 ceiling, enforced in the facade before any backend is touched; same value as Muninn's. Keep. |
| `strict_path_safety` | `False` | Compatibility-kept | Same judgement as Muninn's; local backend only. Keep, named plainly. |
| `debug_log_content` | `False` | Safe-off | Same judgement as Muninn's (RM-044). Keep. |
| `allow_insecure_http` | `False` | Safe-off | Plain `http` to a non-localhost Qdrant host is refused at construction by default (RM-045). Keep. |
| `store_encryption` | `False` | Safe-off | Same judgement as Muninn's (RM-049); local backend only — the Qdrant server owns its disk. The guide now names the field (it was missing — fixed in this slice). Keep. |
| `encryption_passphrase` | `None` | Safe-none | Same judgement as Muninn's. Keep. |
| `max_search_candidates` | `10000` | Bounded | The RM-053 query-cost ceiling (TH-13), local backend only; a bite is visible in `last_search_stats`. Keep. |
| `cache_size` | `0` | Safe-off | The RM-063 warm `get` cache, off by default — the same judgement as Muninn's: per-object only, so the freshness trade must be an explicit choice. The cache lives in the facade and covers both backends; when enabled it is bounded with LRU eviction and own writes always invalidate. Judged at RM-063. Keep. |

## Drift found and fixed in this slice

The review reads the guides as the deployment surface —
and two config fields were missing from it.
`store_encryption` and `encryption_passphrase` appeared
in neither package's guide config table, and the
`docs/API_REFERENCE.md` config listings had drifted
behind RM-049/RM-050/RM-053 (the encryption pair, and
Muninn's attestation pair and `max_spread_candidates` /
Huginn's `max_search_candidates` in the code listings).
A deployment could not judge — or even discover — those
defaults from the guides. This slice adds the missing
rows and listings, and the new suites pin that the guide
names every config field, so the drift cannot silently
return.

## The standing rule this review leaves

A new config field lands with its judgement row in this
record in the same slice that adds it, and any change to
an existing default re-runs this review and updates the
record and the guides in the same commit. The field-set
pin in `tests/test_secure_defaults.py` is the mechanical
half of that rule: it fails on an unreviewed field or an
unrecorded default change.
