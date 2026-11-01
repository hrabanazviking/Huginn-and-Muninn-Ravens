# Config Immutability (RM-017)

Both raven configs — `MuninnConfig` and `HuginnConfig` — are
**frozen dataclasses**: validated once at construction, then
immutable for the life of the object.

## Why

A store reads its config throughout its life (Muninn's learning
rate, decay half-lives, backpressure ceiling and backup policy;
Huginn's backend choice, embedder, timeouts and backup policy).
Before RM-017 the dataclasses were ordinary mutable objects, so
any caller holding a reference could change a live store's
behaviour mid-flight — silently, and possibly into a combination
that was never validated (the validator runs only at
construction).

## What frozen means

- Assigning to any field after construction raises
  `dataclasses.FrozenInstanceError` (a subclass of
  `AttributeError`). The attempt fails loudly at the call site;
  the store never sees it.
- Construction is unchanged: the same fields, defaults and
  validation — a bad value still raises the package's typed
  configuration error (`MuninnConfigurationError` /
  `HuginnConfigurationError`) before any object exists.
- The contract signatures pinned by RM-003 do not move:
  freezing changes assignment behaviour, not the field set,
  kinds or defaults.

## The road to a different configuration

Build a new one:

```python
import dataclasses

cfg2 = dataclasses.replace(cfg, learning_rate=0.5)
```

`replace` runs the full constructor, so the new config is
re-validated — an out-of-range replacement raises the typed
configuration error exactly as a bad direct construction would.
The original config is untouched.

The memory constructors' `**overrides` already take this road:
`HebbianMemory(cfg, learning_rate=0.5)` stores a replaced copy
and never mutates the caller's `cfg`. To run a store under a
different configuration, construct a new store object with the
new config.

## Proof

`tests/test_config_immutability.py` in both packages (RM-017):
assignment attempts on representative fields raise
`FrozenInstanceError`; a mutation attempt against a live store
leaves its behaviour at the validated values (Muninn's first
wiring still starts at the configured learning rate; Huginn's
live backend cannot be flipped); `replace` produces a distinct,
re-validated config; constructor overrides leave the caller's
config untouched. The tests were also run against a scratch
copy with the freeze removed: the two mutation tests in each
package fail there, so the pin catches a regression.
