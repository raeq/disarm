"""Canonicals and sitemap entries name the URL that serves (#694).

`use_directory_urls: false` makes MkDocs write `.html` into every `rel=canonical` and every
sitemap `<loc>`; Cloudflare Pages answers the extensionless form with 200 and 308s the
`.html` form to it. So both of the signals telling a search engine where the content lives
pointed at redirects — 78 of each.

`scripts/mkdocs_canonical_urls.py` rewrites the two signals and nothing else: the `.html`
files are still built and still reachable, so no URL moves. This pins the transform, and
the build itself fails if a signal survives the pass — see `on_post_build`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "scripts" / "mkdocs_canonical_urls.py"


def _hook():
    spec = importlib.util.spec_from_file_location("mkdocs_canonical_urls", HOOK)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SITE = "https://docs.disarm.dev"

#: Left column is what MkDocs writes; right is what Cloudflare answers with 200. The first
#: three rows were measured against the live site before the hook was written.
CASES = [
    (f"{SITE}/user-guide/slugification.html", f"{SITE}/user-guide/slugification"),
    (f"{SITE}/index.html", f"{SITE}/"),
    (f"{SITE}/BINDINGS.html", f"{SITE}/BINDINGS"),
    (f"{SITE}/api/transforms.html", f"{SITE}/api/transforms"),
    (f"{SITE}/user-guide/index.html", f"{SITE}/user-guide/"),
]


@pytest.mark.parametrize(("written", "served"), CASES, ids=[c[0].rsplit("/", 1)[-1] for c in CASES])
def test_the_signal_names_the_served_url(written: str, served: str) -> None:
    assert _hook().served_url(written) == served


@pytest.mark.parametrize(("written", "served"), CASES, ids=[c[0].rsplit("/", 1)[-1] for c in CASES])
def test_the_transform_is_idempotent(written: str, served: str) -> None:
    """Safe to run twice, and safe if MkDocs ever stops writing the extension itself."""
    once = _hook().served_url(written)
    assert _hook().served_url(once) == once == served


def test_a_url_without_the_extension_is_left_alone() -> None:
    for url in (f"{SITE}/", f"{SITE}/BINDINGS", "https://example.com/x.html.txt"):
        assert _hook().served_url(url) == url


def test_the_hook_runs_on_every_build() -> None:
    """A hook nothing registers is a hook that never runs."""
    assert "scripts/mkdocs_canonical_urls.py" in (ROOT / "mkdocs.yml").read_text(encoding="utf-8")


def test_the_self_check_would_catch_a_missed_signal(tmp_path: Path) -> None:
    """Non-vacuity: the build-time guard has to be able to fail."""
    hook = _hook()
    (tmp_path / "sitemap.xml").write_text(
        f"<urlset><url><loc>{SITE}/CHANGELOG.html</loc></url></urlset>", encoding="utf-8"
    )
    (tmp_path / "page.html").write_text(
        f'<link rel="canonical" href="{SITE}/page.html" />', encoding="utf-8"
    )
    stale = hook._stale_signals(tmp_path)
    assert len(stale) == 2, stale
    with pytest.raises(RuntimeError, match="308"):
        hook.on_post_build(
            {"site_dir": str(tmp_path.with_name("missing"))} | {"site_dir": str(tmp_path)}
        )
