"""`apply_into` must not call itself, or every preset links every table (#974, #695).

`presets::apply_into` is an `#[inline(always)]` match over a `const` `Step`. Inlining is
the whole mechanism: it lets each call site fold the match to its one arm, so a preset
links only the tables its own steps reach. `strip_format` declares five steps that
neither transliterate nor demojize, and the difference is **27,490 bytes against
662,087**.

LLVM will not `alwaysinline` a self-recursive function. #951 added two arms that
re-entered `apply_into` to resolve the digit policy — reasonably, since it kept one copy
of each loop — and that alone dropped the attribute, unfolded the match, and re-linked
the Hanzi pinyin and CLDR emoji tables into every preset. Nothing failed: the output was
unchanged and every test stayed green.

`tests/test_wasm_table_coupling.py` is the gate that measures this properly, and it is
the reason the regression stood for two weeks: each surface is a full `--release` wasm
build, so it is `slow`-marked, `addopts` deselects `slow`, and no workflow runs it.

This is the cheap half. It cannot see whether LLVM inlined anything — it reads the source
for the one mechanism that is known to stop it, in milliseconds, on every PR. Keep both:
this catches the known cause, and the wasm gate catches an unknown one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PRESETS = ROOT / "src" / "presets.rs"

#: The function whose inlining the tree-shaking depends on.
DISPATCH = "apply_into"


@pytest.fixture(scope="module")
def source() -> str:
    return PRESETS.read_text(encoding="utf-8")


def _body_of(source: str, name: str) -> str:
    """The text of `fn name(...)`, brace-matched from its signature."""
    match = re.search(rf"^fn {re.escape(name)}\(", source, re.M)
    assert match, f"{name} is gone from {PRESETS.name}; this gate needs rewriting"
    start = source.index("{", match.start())
    depth = 0
    for i in range(start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start : i + 1]
    raise AssertionError(f"unbalanced braces in {name}")


def test_the_dispatch_is_inline_always(source: str) -> None:
    """Without the attribute LLVM leaves an 18-arm match out of line, measured in #695."""
    match = re.search(rf"^fn {DISPATCH}\(", source, re.M)
    assert match
    preceding = source[: match.start()]
    assert "#[inline(always)]" in preceding[-400:], (
        f"{DISPATCH} lost its #[inline(always)]. That attribute is the tree-shaking "
        "mechanism, not an optimisation hint: without it every preset links every table."
    )


def test_the_dispatch_does_not_call_itself(source: str) -> None:
    """The #974 regression, in the form a reader can check.

    An arm that re-enters `apply_into` to resolve a runtime value looks local and is not:
    it makes the function recursive, LLVM drops `alwaysinline`, and every preset grows by
    635 KB. Resolve the value and call the step's own body as a free function instead —
    `confusables_nfc_fixed_point_into` and its neighbour are the worked example.
    """
    body = _body_of(source, DISPATCH)
    calls = re.findall(rf"\b{DISPATCH}\s*\(", body)
    assert not calls, (
        f"{DISPATCH} calls itself {len(calls)} time(s). LLVM will not `alwaysinline` a "
        "recursive function, so the match stops folding to one arm and every preset "
        "links every table (#974: strip_format 27,490 -> 662,087 bytes). Extract the "
        "arm's body into a free function and call that from both arms."
    )


def test_only_the_fixed_point_combinator_walks_a_step_list(source: str) -> None:
    """A runtime walk over `&[Step]` is the shape #695 removed.

    `apply_steps` is the one that remains, for `Step::FixedPoint`'s inner sub-pipeline,
    and it is reachable only from that arm — so a preset without `FixedPoint` never links
    it. A second walker, or a call from anywhere else, puts the whole match back in play.
    """
    walkers = re.findall(r"^fn (\w+)\([^)]*steps: &\[Step\]", source, re.M | re.S)
    assert walkers == ["apply_steps"], (
        f"step-list walkers changed: {walkers}. Each one instantiates the full dispatch "
        "with a runtime `Step`, which is what #695 removed."
    )


def test_the_expensive_gate_still_covers_the_presets() -> None:
    """This file is the cheap half; it must not become the only half.

    If `tests/test_wasm_table_coupling.py` stops covering a preset, the categorical check
    — *is this table present in a surface that cannot reach it* — goes with it, and only
    the known cause above stays gated.
    """
    gate = (ROOT / "tests" / "test_wasm_table_coupling.py").read_text(encoding="utf-8")
    for surface in ("strip_format", "canonicalize", "canonicalize_strict", "strip_obfuscation"):
        assert f'"{surface}"' in gate, f"{surface} left the coupling gate"
