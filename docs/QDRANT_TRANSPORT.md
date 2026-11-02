# Qdrant Transport Safety — RM-045

*Security, slice seven: the one boundary that leaves the machine.*

Threat **TH-06** in `docs/THREAT_MODEL.md`: Huginn's Qdrant
backend crosses the network (TB-5) carrying the API key
(AS-07) and the memory payloads (AS-01). Before this slice
the default URL was plaintext `http://localhost:6333`, any
`http://` URL was accepted for any host, the key was handed
to the client with no handling audit, and wrapped client
exceptions — whose text the ravens do not control — were
returned to the caller verbatim and, in `auto` mode, logged
at INFO inside the fallback reason. Localhost plaintext was
a stated convenience, not a control. This slice makes it a
control, audits the key's handling end to end, and pins both
in tests.

## The defined behaviour

**HTTPS is required by default for non-localhost Qdrant
URLs.** `HuginnConfig` validation (at construction, whatever
the configured backend) now checks the URL's transport:

- the scheme must be `http` or `https` and the URL must
  name a host — anything else is refused with a typed
  `HuginnConfigurationError`;
- `https` is accepted for any host;
- plain `http` is accepted only for a **loopback host** —
  `localhost` (and `*.localhost`), the 127.0.0.0/8 range and
  `::1`, judged by `ipaddress` — which keeps the recorded
  default `http://localhost:6333` working unchanged;
- plain `http` to any other host is refused, unless the
  caller explicitly opts in with the new flag:

**`allow_insecure_http` is a config flag, off by default:**
`HuginnConfig(..., allow_insecure_http=True)`. It is a plain
boolean flag, used as given, like `auto_backup` /
`strict_path_safety`. Lookalike hosts do not slip through:
`localhost.evil.example` and `127.0.0.1.evil.example` are
hostnames, not loopback addresses, and are refused. The
three refusal messages are static strings — they carry
neither the API key nor the URL itself (a URL can carry
credentials of its own), and they are pinned in the RM-018
golden like every other typed message.

**The API key's handling, audited:**

- Its one destination is the `QdrantClient` constructor,
  exactly as configured — proven by a recording fake client.
- It is excluded from the config's `repr`
  (`field(repr=False)`), so logging or printing a config
  cannot leak it.
- No package log call passes it, and the one INFO record
  that carries a wrapped client error — `auto` mode's
  fallback line — now carries the scrubbed text only.
- Every client exception the Qdrant backend wraps
  (`ping`, collection creation, upsert, delete, retrieve,
  search, count) has every occurrence of the configured key
  replaced with `***` before the `HuginnBackendError` is
  raised (`scrub_api_key` in `qdrant_backend.py`). The
  facade applies the same scrub again, defence in depth, to
  the fallback reason it records for `health()` and to the
  error string of an `unhealthy` health report — the two
  diagnostic surfaces a host ships onward.

Payloads in transit are protected by the transport rule
itself: with https required remotely, content and queries
cross the network encrypted; on loopback they never leave
the machine. Payload *keys* are RM-046's road (TH-07).

## How it is proven

Pinned by `tests/test_qdrant_transport.py` (15 tests,
fake clients only):

- the flag's default, the accepted loopback spellings, the
  https road, the refusal for remote http (exact message,
  key- and URL-free), the opt-in road, loopback lookalikes,
  non-http schemes and hostless URLs;
- the config `repr` carries no key;
- a recording fake proves the constructor receives the URL,
  the key and the timeout exactly as configured;
- **error strings scanned for key material** (the roadmap's
  acceptance): leaky fakes embed the key in their exception
  text, and the ping, collection-create, upsert, delete,
  retrieve, search and count errors all come back key-free
  with the `***` placeholder standing where the key stood;
  the `auto` fallback reason, its INFO log records and the
  explicit backend's `health()` error are scanned the same
  way.

Negation: the same file against the pre-RM-045 installed
packages (RM-044 venv) fails the flag, transport and
scrubbing tests and passes only the behaviours this slice
preserves (counts in `docs/SLICE_LOG.md` /
`CAMPAIGN_STATE.md`).

The existing fake-client suite (`test_qdrant_fake.py`) now
opts in explicitly for its non-localhost fake hosts — the
recorded proof that the refusal fires on exactly the shape
that suite always used. The RM-018 goldens gained the three
new config messages (CASE + TEMPLATE); the RM-019
API-surface golden gained the new field.

The public config surface changed additively, so the
**Bifröst contract re-verification was run before banking**
(fresh venv, bifrost at b66e98cc — its own suites and the
BifrostBridge smoke; result in `docs/SLICE_LOG.md` and
`CAMPAIGN_STATE.md`).

TH-06 is closed by this slice, at the code level the threat
model reviewed: the transport rule is enforced at
construction and the key's handling is test-pinned rather
than inspection-only. A **live Qdrant round-trip is still
NOT PROVEN** — no real server has been run; every proof
above is against fake clients, and the threat model's
register is updated at the Part IV gate (RM-056), per its
citation rule.
