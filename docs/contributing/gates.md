# Keys, artifacts and releases

The [test tiers](testing.md), the [lint gates](linting.md) and the
[doc-tests](documentation.md#doc-test-recipes) all run against your worktree or the
branch. The three checks below cover what those cannot see: a stored key that moved,
a file missing from the commit, and a docs site ahead of the release.

## Key-builder output is gated (#644)

`search_key`, `catalog_key` and `sort_key` produce values a consumer **stores**
and compares later, so a change to them is a reindex event on somebody's
production data. `docs/RUST_API.md` states the contract — *a patch release never
changes key-builder output; a minor release may* — and
`tests/test_key_stability.py` holds it.

If it fails, **read the diff before doing anything else.** It prints a
per-function count and a sample of what moved:

```
search_key: 267 of 22878 changed (1.17%)
    'подъезд'
      was 'podъezd'
      now 'podezd'
```

Then decide. If the movement is intended:

```bash
python scripts/gen_key_fixture.py     # rewrite the expected values
```

Commit the regenerated fixture **in the same change**, write it up in the
release's *Upgrade notes*, and cut that release as a **minor**. Regenerating to
make the test go green without reading the diff is the one use the script does
not have.

Review does not substitute for this. `0.14.0` moved `search_key` on 4.1% of a
5,030-input corpus, and the change responsible (#602) was a correctness fix whose
diff said nothing about keys.

The corpus is not reproducible and its licence is not MIT; both are recorded in
`tests/fixtures/key_stability/README.md`.

## Does the artifact work? (#667, #669)

Every step above tests your worktree. It contains untracked files, generated
artefacts, a populated `target/` and whatever `.gitignore` hides — so a file
present locally and absent from the commit is invisible to all of it. And
`maturin develop` produces no distributable artifact at all, so nothing before a
push touches installability.

Two checks close that, sharing one body (`scripts/smoke_installed.py`):

```bash
# The tracked tree — exactly what someone fetching this commit receives.
tmp=$(mktemp -d) && git archive HEAD | tar -x -C "$tmp"
python -m venv "$tmp/venv" && "$tmp/venv/bin/pip" install "$tmp"
(cd "$tmp" && "$tmp/venv/bin/python" "$OLDPWD/scripts/smoke_installed.py")

# The sdist — the artifact CI does not cover either, until #667's job runs.
maturin sdist --out "$tmp/dist"
python -m venv "$tmp/sv" && "$tmp/sv/bin/pip" install --no-binary disarm "$tmp"/dist/*.tar.gz
(cd "$tmp" && "$tmp/sv/bin/python" "$OLDPWD/scripts/smoke_installed.py")
```

Run them from **outside** the checkout, as above. A source tree on `sys.path`
shadows the installed package and the check passes without testing an install —
the failure it exists to find. The script says so if it happens.

These cost a full compile each, which is too slow per commit and about right per
push. `.github/workflows/smoke.yml` runs both in CI: the tracked-tree job on
every push to `main` with **no** paths filter, since the point is that it runs on
every commit that lands.

## The docs describe `main`; the reader executes a tag (#641)

Every gate above runs against the branch. The site deploys from `main` on each
push, but `pip install disarm` gives a reader the newest **tag**. At the worst
point those were 68 commits apart, and `docs/security/cve-validation.md` named
five entry points that raised `AttributeError` on the release it described.

Two things now cover that gap:

- A `mkdocs` hook stamps every page with the commit it was built from and the
  published version (`scripts/mkdocs_build_banner.py`). Nothing to do when
  writing docs; it is mentioned here so nobody deletes it as decoration.
- A weekly job resolves every `disarm` name the docs use against the newest
  published wheel. Run it yourself against any build:

  ```bash
  python scripts/check_docs_against_release.py
  ```

  A **red run means documented API has outrun the last release** — cut one, or
  correct the page. It is deliberately not a pull-request gate: documentation
  ships with the feature it documents, so during that window the gap is correct
  and a PR gate would block every feature branch.

  Names it cannot fix are listed in `_KNOWN_GAPS`, each against an open issue.
  An entry may only go in with an issue number, and the script fails if a listed
  name starts resolving — so the list shrinks rather than accumulating.
