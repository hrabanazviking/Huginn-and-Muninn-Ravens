# SQL-Injection Audit (RM-040, TH-01)

Part IV — Security. Threat cited: **TH-01** (SQL injection: a
caller value reaches SQL as syntax and reads or destroys the
store). RM-039's model rated TH-01 *Partial (inspection)* —
every value appeared bound, but no hostile battery had ever
proven it. This audit proves it, and pins the proof so a
future SQL site cannot quietly change the answer.

**Verdict: TH-01 is closed for the SQLite surfaces.** Every
caller value in both packages reaches SQLite only as a bound
parameter. The Qdrant backend issues no SQL at all.

## Method

Every `execute` / `executemany` / `executescript` call site
in `src/muninn` and `src/huginn` was inventoried from the
AST (not from memory or grep alone) on the RM-039 head, and
each site's first argument classified: string constant,
f-string (template recorded), or variable (traced to its
construction). Separately, every SQL-shaped f-string
anywhere in either source tree was listed — including any
built into a variable before reaching `execute()`.

## Audit table

### Muninn — 81 sites (`_db.py` 8, `core.py` 73)

| Shape | Count | What it is |
|---|---|---|
| String constant, values bound as `?` parameters | most of 76 constants | Every insert / update / delete / select that touches caller data: content, category, path, tags, metadata, ids, strengths, timestamps, sources. |
| String constant, no values at all | the rest of 76 constants | Static PRAGMAs (`journal_mode=WAL`, `synchronous=FULL`, `foreign_keys=ON`, `quick_check`), counts, heal/repair statements, and the batch road's static temp-table / index DDL (`temp.muninn_batch_ids`, `idx_conn_b`). |
| F-string: `PRAGMA busy_timeout={int(busy_timeout_ms)}` | 1 | PRAGMAs cannot bind parameters; the interpolated value passes through `int()` first, so only digits can ever appear. The value comes from validated config, never from a caller string. |
| F-string: `UPDATE nodes SET {assignments} WHERE id = ?` | 1 | `update()`'s column names. `assignments` is built as `f"{k} = ?"` over the keys of the `updates` dict, and that dict is populated **only** from literal keys in `update()` itself, behind the closed field allow-list (`importance`, `emotional_valence`, `tags`, `metadata`, `path`, `memory_type`, `category`, plus the internal `content` / `content_is_json` / `content_hash` / `updated_at`). Every value is a bound `?`; a caller-supplied field name outside the allow-list raises `MuninnValidationError` before any SQL is built. |
| Variable: `executescript(schema_sql)` | 1 | The static `SCHEMA_SQL` constant defined in `core.py`, handed to `_db.py` at construction. No caller input reaches it. |
| Variable: `execute(sql)` in `_seed_last_ts_locked` | 1 | `sql` iterates a tuple of five string constants (`SELECT MAX(...)` per timestamp column). |
| Variable: `execute(sql, params)` in `retrieve` | 1 | `sql` starts as a constant base and gains only two constant fragments (`AND category = ?`; `AND (path = ? OR path LIKE ? ESCAPE '\')`). The category, the path and the escaped LIKE pattern are all bound in `params`; the LIKE pattern is additionally escaped (`_like_prefix_pattern`), so `%` / `_` in a path are literals, not wildcards. |

### Huginn — 42 sites (`_db.py` 8, `local_backend.py` 34)

| Shape | Count | What it is |
|---|---|---|
| String constant, values bound as `?` parameters | most of 36 constants | Every document / term / vector / corpus write and read that touches caller data: content, category, tags, ids, terms. |
| String constant, no values at all | the rest of 36 constants | Static PRAGMAs, counts, corpus heal statements. |
| F-string: `PRAGMA busy_timeout={int(busy_timeout_ms)}` | 1 | As in Muninn: `int()`-cast validated config only; PRAGMAs cannot bind. |
| F-strings: three `IN ({placeholders})` / `IN ({ph})` / `IN ({tph})` templates | 3 | Each placeholder string is `",".join("?" * len(<collection>))` — built from a collection's **length only**. No value, and no character of any value, is interpolated; every element is bound in the parameter list. |
| Variable: `executescript(schema_sql)` | 1 | The static `SCHEMA_SQL` constant defined in `local_backend.py`. |
| Variable: `execute(sql, params)` in `_candidate_docs_locked` | 1 | `sql` is the f-string `SELECT * FROM documents WHERE id IN ({placeholders})` (placeholders from `len(doc_ids)`, as above) plus at most two constant fragments (`AND category = ?`, `AND importance >= ?`); the ids, category and importance are all bound in `params`. |

That is the complete interpolated set: 2 f-string templates
in Muninn, 5 SQL-shaped f-strings in Huginn (4 at execute
sites, 1 feeding the pinned `sql` variable), 3 variable
sites in Muninn, 2 in Huginn, and **no other shape anywhere**
— no `%`-formatting, no string concatenation, and no
`.format()` builds SQL in either package.

## The hostile battery (proof, not inspection)

`tests/test_sql_injection.py` in both packages, stored and
retrieved **verbatim**:

- 12 Muninn / 11 Huginn hostile contents: single and double
  quotes, `'; DROP TABLE …; --`, `DELETE … WHERE 1=1`,
  `UNION SELECT`, comment markers, backslash escapes,
  embedded newlines around a payload, a curly quote +
  fullwidth semicolon look-alike, and an RTL-override prefix.
  After the whole battery every table survives
  (`health()` healthy, integrity ok) and counts are exact.
- Hostile category, tags, metadata keys/values and (Muninn)
  path segments round-trip verbatim and are findable by
  exact-match filters.
- Injection as a *filter* matches nothing it should not:
  `retrieve(category="' OR '1'='1") == []`,
  `search("zebra", category="' OR '1'='1") == []` — the
  payload is a literal value to compare, never a tautology.
- Muninn LIKE escaping: a node under `a%b/c` is found by
  `retrieve(path="a%b")`; a node under `axb/c` is not.
- Muninn `update()`: a hostile *value* is stored verbatim;
  a hostile *field name* (`"path = 'pwned', …"`) raises
  `MuninnValidationError` and the node is untouched.
- Huginn placeholder width: a 50-term hostile query binds
  every term and returns only the genuinely matching doc.

## The pin

The same test files classify every execute site from the
AST and pin: the site totals (Muninn 81, Huginn 42), the
exact f-string template sets, the exact variable-site names
and counts, and the set of SQL-shaped f-strings anywhere in
each source tree. A new site, a new template, or a new
shape (concatenation, `%`-formatting, a computed argument)
fails the suite until this audit is re-run and the pin is
deliberately updated. Negation proven at banking: a scratch
tree with an injected f-string site appended to Muninn
fails both audit tests (2 failed / 7 passed), and a scratch
tree with a string-concatenation site appended to Huginn
fails its classification test (1 failed / 6 passed); the
hostile battery passes unchanged on both scratch trees,
because the battery tests behaviour of the shipped code,
not the pin.

## Honesty ledger

- Live Qdrant round-trip: NOT PROVEN (unchanged) — and out
  of scope here: the Qdrant backend issues no SQL.
- The pin covers the packages' `src/` trees. In
  `scripts/`, the one SQL user is Muninn's
  `huge_batch_bench.py`: 4 sites, all string constants,
  its single value-carrying query bound as parameters;
  the benchmark scripts otherwise only read
  `sqlite3.sqlite_version`.
