"""A rustdoc link whose text names a member must target that member (#951 review).

``[`DigitPolicy::Numeric`](crate::api::DigitPolicy)`` renders as a link to the *type*, and
``cargo doc`` cannot object: the target resolves. Only a reader notices, on docs.rs, that
the variant they clicked took them somewhere else. This reads every intra-doc link in
``src/`` whose text is a path and asserts the target's last segment is the text's. The
sweep that introduced it found twenty-four more of the same shape, all ``ErrorKind``.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
LINK = re.compile(r"\[`([A-Za-z_][\w:]*)`\]\((crate::[\w:]+)\)")


def test_a_link_whose_text_names_a_member_targets_that_member() -> None:
    wrong = []
    for path in sorted(SRC.rglob("*.rs")):
        for m in LINK.finditer(path.read_text(encoding="utf-8")):
            text, target = m.group(1), m.group(2)
            if "::" in text and text.split("::")[-1] != target.split("::")[-1]:
                wrong.append(f"{path.relative_to(SRC.parent)}: {m.group(0)}")
    assert not wrong, "\n".join(wrong)


def test_the_scan_sees_links() -> None:
    """A regex that matched nothing would make the gate above vacuous."""
    n = sum(len(LINK.findall(p.read_text(encoding="utf-8"))) for p in SRC.rglob("*.rs"))
    assert n >= 20, n
