"""Canonical links and sitemap entries name the URL that answers 200 (#694).

`mkdocs.yml` sets `use_directory_urls: false`, so MkDocs writes `.html` into every
`rel=canonical` tag and every `sitemap.xml` entry. Cloudflare Pages serves this site with
its own clean-URL behaviour: it answers the extensionless form with 200 and 308s the
`.html` form to it. Measured on the live site:

    /user-guide/slugification        200
    /user-guide/slugification.html   308 -> /user-guide/slugification
    /                                200
    /index.html                      308 -> /

So every signal telling a search engine where the content lives pointed at redirects: 78
canonicals, 78 sitemap entries, and the 78 `og:url` tags `overrides/main.html` emits from
the same `page.canonical_url`. A canonical naming a redirect is a
documented anti-pattern: the signal is weakened and sometimes discarded, which is the
opposite of what a canonical is for.

**Nothing moves.** This rewrites the two *signals* to the URL Cloudflare already serves.
The `.html` files are still built, still deployed and still reachable; every link that
exists today keeps working, and no indexed URL changes. That is the difference between this
and `use_directory_urls: true`, which would relocate all 78 URLs and needs a preview deploy
to confirm Pages does not redirect the directory form in turn (#694 option 1).

The rewrite checks its own work: if a canonical or a sitemap entry still ends in `.html`
after the pass, the build fails rather than shipping the thing this exists to prevent.
"""

from __future__ import annotations

import gzip
import re
from pathlib import Path
from typing import Any

#: `<link rel="canonical" href="…" />`, however the theme spaces it.
CANONICAL = re.compile(r'(<link\s+rel="canonical"\s+href=")([^"]+)(")')
#: The Open Graph and Twitter URL signals. `overrides/main.html` emits `og:url` from
#: `page.canonical_url`, so it carried the same `.html` form the canonical did — one
#: signal fixed and one left pointing at a 308 is not a fix (#694 review).
META_URL = re.compile(r'(<meta\s+(?:property|name)="(?:og:url|twitter:url)"\s+content=")([^"]+)(")')
#: `<loc>…</loc>`, one per sitemap entry.
LOC = re.compile(r"(<loc>)([^<]+)(</loc>)")


def served_url(url: str) -> str:
    """The URL Cloudflare Pages answers with 200, given the one MkDocs wrote.

    `foo/index.html` is the directory itself, so it keeps its trailing slash; every other
    page drops the extension. A URL that is already extensionless is returned unchanged,
    so this is safe to run twice and safe if MkDocs' output ever changes.
    """
    if url.endswith("/index.html"):
        return url[: -len("index.html")]
    if url.endswith(".html"):
        return url[: -len(".html")]
    return url


def _rewrite(pattern: re.Pattern[str], text: str) -> str:
    return pattern.sub(lambda m: f"{m.group(1)}{served_url(m.group(2))}{m.group(3)}", text)


def on_post_page(output: str, page: Any, config: Any) -> str:  # noqa: ANN401, ARG001
    """Point every URL signal on the page at the URL that serves it."""
    return _rewrite(META_URL, _rewrite(CANONICAL, output))


def on_post_build(config: Any) -> None:  # noqa: ANN401
    """Rewrite `sitemap.xml`, regenerate its gzip, and refuse to ship a redirecting signal."""
    site = Path(config["site_dir"])
    sitemap = site / "sitemap.xml"
    if sitemap.is_file():
        rewritten = _rewrite(LOC, sitemap.read_text(encoding="utf-8"))
        sitemap.write_text(rewritten, encoding="utf-8")
        # MkDocs ships both, and a stale `.gz` would serve the old entries to anything
        # that prefers it. `mtime=0` keeps the build reproducible, as MkDocs' own does.
        with (
            (site / "sitemap.xml.gz").open("wb") as raw,
            gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz,
        ):
            gz.write(rewritten.encode("utf-8"))

    stale = _stale_signals(site)
    if stale:
        raise RuntimeError(
            "#694: these signals still name a URL that 308s, which is what this hook "
            f"exists to prevent: {stale[:5]}"
        )


def _stale_signals(site: Path) -> list[str]:
    """Every canonical or sitemap entry still ending in `.html`."""
    out: list[str] = []
    sitemap = site / "sitemap.xml"
    if sitemap.is_file():
        out += [
            f"sitemap.xml: {m.group(2)}"
            for m in LOC.finditer(sitemap.read_text(encoding="utf-8"))
            if m.group(2).endswith(".html")
        ]
    for html in site.rglob("*.html"):
        text = html.read_text(encoding="utf-8", errors="replace")
        for pattern in (CANONICAL, META_URL):
            out += [
                f"{html.relative_to(site)}: {m.group(2)}"
                for m in pattern.finditer(text)
                if m.group(2).endswith(".html")
            ]
    return out
