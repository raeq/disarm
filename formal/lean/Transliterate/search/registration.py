"""Premises that depend on process-global registration state.

The invariant proofs quietly assume the *built-in* tables and an empty
replacement pre-pass. `register_lang` and `register_replacements` let a caller
change both at runtime; this script shows which invariant each one can break.
It mutates process-global state, so run it in its own interpreter.

Run:  python3 registration.py
"""

from __future__ import annotations

import disarm

T = disarm.transliterate


def show(label: str, expr: str, value: object, holds: bool) -> None:
    print(f"[{'holds' if holds else 'FAILS'}] {label}\n        {expr}\n        -> {value!a}")


def main() -> None:
    disarm.clear_replacements()

    # I2 premise P1 (every table value is ASCII) is enforced by build.rs for the
    # shipped tables only. register_lang() accepts any value.
    disarm.register_lang("xx", {"é": "éé"})
    r = T("café", lang="xx", errors="ignore")
    show(
        "I2 with a registered lang (non-ASCII value accepted without validation)",
        "disarm.register_lang('xx', {'\\u00e9': '\\u00e9\\u00e9'}); "
        "disarm.transliterate('caf\\u00e9', lang='xx', errors='ignore')",
        r,
        r.isascii(),
    )
    rr = T(r, lang="xx", errors="ignore")
    show(
        "I3 with the same registered lang",
        "transliterate(<that>, lang='xx', errors='ignore')",
        rr,
        rr == r,
    )

    # I1: the replacement pre-pass runs before the ASCII fast path (documented).
    disarm.register_replacements({"a": "b"})
    r = T("a")
    show(
        "I1 with a registered ASCII-keyed replacement",
        "disarm.register_replacements({'a': 'b'}); disarm.transliterate('a')",
        r,
        r == "a",
    )
    disarm.clear_replacements()

    # I3: a replacement whose output re-matches its own key is applied again on
    # the second call.
    disarm.register_replacements({"x": "yx"})
    r1 = T("x", errors="ignore")
    r2 = T(r1, errors="ignore")
    show(
        "I3 with a self-re-matching replacement",
        "disarm.register_replacements({'x': 'yx'}); f = lambda s: disarm.transliterate(s, errors='ignore'); f(f('x'))",
        (r1, r2),
        r1 == r2,
    )
    disarm.clear_replacements()


if __name__ == "__main__":
    main()
