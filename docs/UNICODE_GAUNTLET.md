# Unicode & Encoding Gauntlet — RM-034

*All the world's scripts are welcome. Text that cannot be
encoded honestly is refused, typed.*

The ravens store text from anywhere: Arabic and Hebrew
written right-to-left, CJK, emoji joined into one glyph by
zero-width joiners, letters built from combining marks. And
Python hands them one shape of text that no honest store can
hold: a string carrying an **unpaired surrogate** code point
(U+D800–U+DFFF), constructible through `\udXXX` escapes or a
careless decode of damaged bytes. UTF-8 cannot encode it,
SQLite cannot bind it, and JSON can only smuggle it through
as a `\udXXX` escape — producing files whose strings no
other system can read back as encoded text.

## What v1.0.0 did with a lone surrogate (measured by probe)

* **Muninn string content** died with a raw
  `UnicodeEncodeError` from the content hash's `.encode()`.
* **A Muninn path or category** died the same way — the path
  in the RM-028 size check, the category at the SQLite bind.
* **Muninn tags, metadata and JSON-valued content were
  silently stored**: `json.dumps` escaped the surrogate into
  ASCII, the write succeeded, and retrieval handed back a
  string that still cannot be encoded anywhere else.
* **Huginn content** died with a raw `UnicodeEncodeError`
  from the RM-027 size check; **a Huginn category** died at
  the SQLite bind; **a Huginn tag** was silently stored as a
  JSON escape; **a Huginn query** silently searched for
  nothing and returned an empty result.

## The defined behaviour

One checker per package — `_check_no_lone_surrogates` in
each package's `core.py` — scans a text code point by code
point and raises the typed validation error
`{field} must not contain lone surrogates` at the first
U+D800–U+DFFF character. It runs **before any write** (and,
for refused writes, the store's counts are proven unchanged
by the gauntlet tests):

* **Muninn** — `remember` / `store` / `update` check content
  (a plain string, and recursively every string inside a
  JSON-shaped value: dict keys and values, list/tuple/set
  items, at any depth), metadata (the same recursive walk,
  including the string form of values the metadata dump
  would stringify), tags, category, and the path (inside
  the RM-028 normaliser, so reads through `get_by_path` /
  `get_children` are judged by the same rule). `retrieve`'s
  query, tag filter and category filter are checked too.
  Circular structures are not walked twice — `json.dumps`
  refuses them with its established typed message, as
  before.
* **Huginn** — the check sits in the facade, so it holds on
  the local and Qdrant backends alike (the RM-027
  discipline): `upsert_memory` checks content, category and
  tags; `_check_query_text` checks every query-shaped
  argument (`search`, `analyze_query`, `semantic_search`,
  `fly`, `multi_hop_retrieve`), `_check_category` checks
  read-side categories, and `_check_documents` checks every
  `semantic_search` document. A surrogate query inside
  `fly` keeps the ancestor discipline: it comes home as an
  error flight naming the refusal, never a raise.

## The welcome half, pinned

The refusal is exactly as narrow as the fault: only the
U+D800–U+DFFF range is refused. Everything else is stored
and returned **verbatim — no normalisation, ever**:

* RTL content (Arabic, Hebrew) round-trips byte-for-byte
  and is searchable in both packages.
* Emoji ZWJ sequences (the family glyph, the
  skin-tone-modified technologist) round-trip byte-for-byte.
* Combining marks are never folded: the decomposed
  `cafe + ◌́` and the precomposed `café` are **two different
  memories** in both stores, each retrieved exactly as
  written.
* Astral-plane characters (𝄞, 𐍈) are single Python code
  points above U+FFFF — they are *not* lone surrogates
  (a UTF-16 surrogate *pair* is a transport encoding of one
  character, not two unpaired halves) and pass untouched.

Pinned by `tests/test_unicode_gauntlet.py` in both packages
(muninn 17 tests, huginn 10). Negation, recorded before the
fix: muninn **12 failed / 5 passed**, huginn **6 failed /
4 passed** against the pre-RM-034 code — the passes are
exactly the welcome half, which already held. The new
message is an RM-018 golden in both packages (CASE
`content_surrogate` + `path_surrogate` for muninn, CASE
`content_surrogate` + `query_surrogate` for huginn, plus
the shared TEMPLATE `{} must not contain lone surrogates`):
counted from the files, muninn now carries 47 CASE / 63
TEMPLATE lines and huginn 52 CASE / 64 TEMPLATE lines.
