"""RM-019 — API surface freeze for muninn.

RM-003 froze the handful of shapes Bifröst calls. This slice
freezes the *whole* public surface of the package, snapshotted
in ``golden_api_surface.txt``:

* every name in the top-level ``__all__``;
* every exported class, with its base classes (the error
  hierarchy and the ``Muninn`` facade's inheritance included);
* every public method of every exported class, with its
  (name, kind, default) signature shape — the RM-003 style;
* every dataclass field of the exported dataclasses, with its
  declared type and default;
* the exported module-level functions' shapes.

Semantics, per the roadmap: **additions are allowed** — a new
name or method does not fail this suite (it should still be
added to the golden in the commit that introduces it, so the
snapshot stays a complete inventory). **Removals, renames and
signature changes fail** until a deliberate major-version
slice updates the golden.
"""

import dataclasses
import inspect
from pathlib import Path

import muninn
from muninn import (
    HebbianMemory,
    MemoryNode,
    Muninn,
    MuninnConfig,
    MuninnConfigurationError,
    MuninnError,
    MuninnStorageError,
    MuninnValidationError,
)

GOLDEN = Path(__file__).parent / "golden_api_surface.txt"

EXPORTED_CLASSES = [
    HebbianMemory,
    Muninn,
    MemoryNode,
    MuninnConfig,
    MuninnError,
    MuninnValidationError,
    MuninnConfigurationError,
    MuninnStorageError,
]
EXPORTED_FUNCTIONS = []


def _shape(fn):
    out = []
    for p in inspect.signature(fn).parameters.values():
        if p.name in ("self", "cls"):
            continue
        default = "<required>" if p.default is inspect.Parameter.empty else repr(p.default)
        out.append(f"{p.name}:{p.kind.name}={default}")
    return ";".join(out)


def _raw_member(cls, name):
    """(owner, raw member) for the class in the MRO defining
    ``name`` — or (None, None). Members defined by builtins
    (``object``, ``Exception`` machinery such as ``add_note``)
    are not package surface and are skipped by the caller."""
    for klass in cls.__mro__:
        if name in vars(klass):
            return klass, vars(klass)[name]
    return None, None


def _surface_lines():
    lines = set()
    for name in muninn.__all__:
        lines.add(f"ALL | {name}")
    lines.add("VERSION | __version__")
    for cls in EXPORTED_CLASSES:
        bases = ",".join(base.__name__ for base in cls.__bases__)
        lines.add(f"CLASS | {cls.__name__} | bases={bases}")
        field_names = set()
        if dataclasses.is_dataclass(cls):
            for f in dataclasses.fields(cls):
                field_names.add(f.name)
                if f.default is not dataclasses.MISSING:
                    default = repr(f.default)
                elif f.default_factory is not dataclasses.MISSING:
                    default = "<factory>"
                else:
                    default = "<required>"
                lines.add(f"FIELD | {cls.__name__}.{f.name} | type={f.type} | default={default}")
        for name in dir(cls):
            if name.startswith("_") and name != "__init__":
                continue
            if name in field_names:
                continue
            owner, raw = _raw_member(cls, name)
            if owner is None or owner.__module__ == "builtins":
                continue
            if isinstance(raw, property):
                lines.add(f"PROPERTY | {cls.__name__}.{name}")
            elif isinstance(raw, (classmethod, staticmethod)):
                lines.add(f"METHOD | {cls.__name__}.{name} | {_shape(raw.__func__)}")
            elif callable(raw):
                lines.add(f"METHOD | {cls.__name__}.{name} | {_shape(raw)}")
            elif raw is not None or hasattr(cls, name):
                value = getattr(cls, name)
                lines.add(f"ATTR | {cls.__name__}.{name} | {type(value).__name__}")
    for fn in EXPORTED_FUNCTIONS:
        lines.add(f"FUNCTION | {fn.__name__} | {_shape(fn)}")
    return lines


def _golden_lines():
    lines = set()
    for line in GOLDEN.read_text().splitlines():
        if line and not line.startswith("#"):
            lines.add(line)
    return lines


def test_all_exports_resolve_and_are_unique():
    assert len(muninn.__all__) == len(set(muninn.__all__)), "__all__ has duplicates"
    for name in muninn.__all__:
        assert hasattr(muninn, name), f"__all__ names {name}, which does not exist"
    exported = {cls.__name__ for cls in EXPORTED_CLASSES}
    exported |= {fn.__name__ for fn in EXPORTED_FUNCTIONS}
    exported.add("__version__")
    assert exported == set(muninn.__all__), (
        "the freeze inventory and __all__ disagree: "
        f"inventory-only={sorted(exported - set(muninn.__all__))}, "
        f"__all__-only={sorted(set(muninn.__all__) - exported)}"
    )


def test_no_golden_surface_line_is_missing():
    golden = _golden_lines()
    actual = _surface_lines()
    missing = golden - actual
    assert not missing, (
        "public API surface shrank or changed shape — removals, "
        "renames and signature changes are frozen until a "
        "major-version slice. Missing/changed golden lines:\n"
        + "\n".join(sorted(missing))
        + "\nIf this change is deliberate and major, update "
        "golden_api_surface.txt in the same commit."
    )


def test_golden_is_sorted_inventory_of_the_surface():
    # The golden is a snapshot: every line in it must be a line
    # the collector can produce (no stale hand-written lines),
    # which the missing-lines test already proves; this pins
    # that the file itself is in canonical sorted order so
    # diffs stay readable.
    raw = [
        line
        for line in GOLDEN.read_text().splitlines()
        if line and not line.startswith("#")
    ]
    assert raw == sorted(raw), "golden_api_surface.txt is not in sorted order"
