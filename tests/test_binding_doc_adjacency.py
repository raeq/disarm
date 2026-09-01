"""A `/** … */` doc block must document the declaration below it, not another doc block.

In TypeScript, Java and Kotlin only the **last** doc comment before a declaration is
attached. So inserting a new member between an existing doc block and the member it
described silently does two things at once: the new member inherits nothing, and the old
member loses its documentation entirely. Nothing fails — the file parses, the build passes,
and the rendered API docs are simply wrong.

That is what happened on #778/#851. `hasBidiControl` was added directly above
`hasBidiConflict`, landing between `hasBidiConflict`'s block and its declaration:

    /**
     * Whether `text` mixes strong left-to-right and strong right-to-left characters
     * ...
     */
    /**
     * All twelve UAX #9 explicit formatting characters, uncontexted.
     * ...
     */
    export function hasBidiControl(text: string): boolean { ... }

    export function hasBidiConflict(text: string): boolean { ... }

Caught by review on that PR, on two of the six binding surfaces. The Ruby, Python and Rust
copies of the same change were correct, which is the point: it is not a rule anyone breaks
deliberately, it is a rule an anchored insert breaks by accident. This gate makes the
accident visible.

The invariant is deliberately narrow — **two doc blocks may not be adjacent** — because that
is the whole failure and it needs no language parser to check. It says nothing about whether
a declaration is documented at all; these files document selectively on purpose.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: The binding surfaces written in a language where only the last doc block binds.
#: Rust (`///`) is absent on purpose: consecutive `///` lines are one block by definition,
#: so the failure mode there is a fused block rather than an orphaned one.
SURFACES = (
    "bindings/node/index.ts",
    "bindings/java/disarm-java/src/main/java/dev/disarm/Disarm.java",
    "bindings/java/disarm-java/src/main/java/dev/disarm/internal/Native.java",
    "bindings/java/disarm-kotlin/src/main/kotlin/dev/disarm/kotlin/Disarm.kt",
)

#: One `/** … */` block. Written to stop at its own `*/` — a `.*?` under `DOTALL`
#: backtracks straight past intervening blocks to satisfy the rest of the pattern, which
#: reports the file's first doc comment instead of the offending one.
_DOC = r"/\*\*(?:[^*]|\*(?!/))*\*/"

#: A doc block, then only blank lines, then the start of another doc block.
_ADJACENT = re.compile(_DOC + r"[ \t]*\n(?:[ \t]*\n)*[ \t]*(?=/\*\*)")

#: A file-level doc block: the first one in the file, with nothing before it but a
#: package declaration, imports, file annotations (`@file:JvmName`, which is what opens
#: the Kotlin surface), line comments or blank lines. It documents the file rather than a
#: declaration, so a member's block may legitimately follow it.
_ONLY_PREAMBLE = re.compile(r"\A(?:[ \t]*(?:package |import |@|//).*\n|[ \t]*\n)*\Z")


def _blocks_are_adjacent(text: str) -> list[int]:
    """1-based line numbers of every *orphaned* block's successor.

    The line reported is the second block's — the one that displaced the first — because
    that is where the inserted member is and where the fix goes.
    """
    out = []
    for m in _ADJACENT.finditer(text):
        if _ONLY_PREAMBLE.match(text[: m.start()]):
            continue  # file-level doc followed by the first member's doc
        out.append(text.count("\n", 0, m.end()) + 1)
    return out


def test_the_surfaces_exist() -> None:
    """A gate over files that have been renamed away passes for the wrong reason."""
    missing = [s for s in SURFACES if not (ROOT / s).is_file()]
    assert not missing, f"listed surface no longer exists: {missing}"


def test_no_doc_block_documents_another_doc_block() -> None:
    offenders = []
    for surface in SURFACES:
        text = (ROOT / surface).read_text(encoding="utf-8")
        offenders += [f"{surface}:{line}" for line in _blocks_are_adjacent(text)]
    assert not offenders, (
        "a /** */ doc block is immediately followed by another, so the first documents "
        "nothing and the declaration it was written for is undocumented. A new member was "
        "almost certainly inserted between a block and its declaration — move the block "
        "back down onto the declaration it describes:\n  " + "\n  ".join(offenders)
    )


def test_the_check_can_actually_fail() -> None:
    """Constructed, never pasted — the #794 lesson.

    This is the exact shape #851 shipped, and it is what the gate must catch.
    """
    bad = "const x = 1\n/** first. */\n/** second. */\nexport function f(): void {}\n"
    assert _blocks_are_adjacent(bad) == [3]

    spaced = "const x = 1\n/** first. */\n\n\n/** second. */\nexport function f(): void {}\n"
    assert _blocks_are_adjacent(spaced) == [5], "blank lines between must not hide it"

    good = "/** first. */\nexport function f(): void {}\n\n/** second. */\nexport function g(): void {}\n"
    assert _blocks_are_adjacent(good) == []


def test_a_file_level_doc_may_precede_a_member_doc() -> None:
    """The Kotlin surfaces open this way, and it is correct.

    A file/module block documents no declaration, so the next member's block does not
    displace anything. Only a block that had a declaration to lose counts.
    """
    kt = "/** file doc. */\n\n/** member doc. */\ntypealias Scheme = X\n"
    assert _blocks_are_adjacent(kt) == []

    after_imports = (
        "package a.b\n\nimport c.D\n\n/** file doc. */\n\n/** member doc. */\nclass E {}\n"
    )
    assert _blocks_are_adjacent(after_imports) == []

    annotated = '@file:JvmName("D")\n\npackage a.b\n\nimport c.D\n\n/** file doc. */\n\n/** member doc. */\ntypealias S = X\n'
    assert _blocks_are_adjacent(annotated) == [], "a Kotlin file annotation is still preamble"


def test_an_intervening_declaration_is_not_adjacency() -> None:
    """Two documented members in a row is the normal case and must stay silent."""
    ok = "const x = 1\n/** a. */\nexport function a(): void {}\n/** b. */\nexport function b(): void {}\n"
    assert _blocks_are_adjacent(ok) == []
