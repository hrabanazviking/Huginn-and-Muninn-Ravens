# Error Messages — RM-018

Error strings are API. A caller (Bifröst, Hermes, a saga
engine) may legitimately match on a typed error's message —
`"strength must be in [0, 1]"` is as much a contract as the
exception type carrying it. From RM-018 on, no typed error's
message in either package may change casually: every message
shape is pinned by snapshot tests, and a change lands only as
a deliberate golden update in the same commit as the rewording.

## The two pins

Each package carries `tests/test_error_messages.py` with its
golden in `tests/golden_error_messages.txt`:

1. **Behavioural (CASE lines).** Every deterministically
   triggerable typed error is raised with fixed inputs —
   through the public API, the backends, or config
   construction — and the *exact* message must equal the
   golden. Muninn: **31 cases**. Huginn: **33 cases** (its
   Qdrant translations are produced against a fake client
   whose methods raise `RuntimeError("boom")`; no live server
   is involved and live Qdrant stays NOT PROVEN).
2. **Template (TEMPLATE lines).** Every
   `raise <Typed>Error(...)` site in `src/` is re-extracted
   from the AST — string constants verbatim, f-string values
   normalised to `{}` — and the multiset of
   `(error type, template)` pairs must equal the golden.
   Muninn: **33 sites**. Huginn: **36 sites** (35 distinct;
   the local backend's no-row-id guard appears at two insert
   paths). A new raise site, a removed one, or one reworded
   word fails this test until the golden is updated
   deliberately.

## What the behavioural pin cannot reach

Three huginn sites and two muninn sites have no deterministic
trigger, and are covered by the template pin only — stated
plainly, not silently skipped:

- `"<pkg> store {} could not be prepared: {}"` (both
  packages) — fires only when a store's schema script fails
  mid-open, after the integrity probe passed.
- `"node insert reported success but returned no row id"`
  (muninn, once) and `"document insert reported success but
  returned no row id"` (huginn, twice) — the RM-008 guards,
  unreachable by construction while SQLite honours its
  `lastrowid` contract.

## Changing a message on purpose

Reword the raise site, run the suite, read the failure's
diff, and update the golden CASE/TEMPLATE lines in the same
commit. The slice log entry for that commit must name the
rewording as deliberate — the golden is the record callers
will diff against.

## Acceptance, proven by negation

On a scratch copy of this tree: rewording muninn's
`"strength must be in [0, 1]"` fails the template test,
rewording huginn's `"query_text must be a string"` fails the
template test, and altering one muninn CASE line in the
golden fails the behavioural test — the pins catch drift
from either side. (Result recorded in `CAMPAIGN_STATE.md`
under RM-018; the scratch copy was discarded.)

No package code, public API, or schema changed in this
slice, so no Bifröst re-verification was required (RM-003
contract freeze + RM-004 schema snapshot green in the full
suites).
