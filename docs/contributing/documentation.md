# Documentation

How the docs site is built, and the gates that keep what it says true.

## Building documentation

```bash
pip install --require-hashes -r requirements/docs.txt
mkdocs serve              # local preview at http://127.0.0.1:8000
mkdocs build              # build static site to site/
```

`requirements/docs.txt` is **generated** — the `[docs]` extra in `pyproject.toml` is the
single source of truth, and the lockfile is compiled from it (same pattern as
`requirements/bench.txt`). After changing the extra, regenerate:

```bash
uv pip compile pyproject.toml --extra docs --generate-hashes -o requirements/docs.txt
```

## Doc-test recipes

Cookbook examples are **executed in CI** against the shipped wheel — a wrong or
broken snippet turns the suite red (#154). This kills "recipe rot": output
claims that are wrong at authoring time, or that silently break when the API
moves. The harness is [Sybil](https://sybil.readthedocs.io/); it runs every
fenced `python` block in an allowlisted page and checks any `assert` it
contains.

Run the doc-tests locally (they need the `[test]` extra, which pulls in Sybil):

```bash
pip install -e ".[test]"
python scripts/run_doc_tests.py       # all pages, each in its own process
pytest docs/user-guide/filenames.md   # a single page
```

The runner executes each page in a **separate process**. Some documented APIs
mutate process-global state (`register_lang` is not reversible), so running every
page in one process would let one page's registration leak into another and break
exact-output examples. `pytest docs/` (one process) is therefore not the gate.

**Recipe template.** Assert outputs; never decorate them with `# =>`:

````markdown
```python
from disarm import sanitize_filename

assert sanitize_filename("café.txt") == "cafe.txt"
```
````

Rules:

- **Assert, don't comment.** `assert f(x) == "y"` is checked; `f(x)  # => "y"`
  is not. The `# =>` pattern is what we are removing (#156).
- **Public API only.** Reaching into internals (`disarm._...`) in a published
  example is itself a doc bug — the example must exercise what users can call.
- **One namespace per page.** Blocks share state top-to-bottom, so import once
  and reuse the binding in later blocks.
- **Hide setup** that would clutter the prose in an invisible block — it runs
  but does not render:

  ```markdown
  <!--- invisible-code-block: python
  tmp = make_fixture()
  -->
  ```

- **Skip** a block that is intentionally not runnable (e.g. pseudo-code or a
  shell transcript mislabelled `python`) with `<!--- skip: next -->`.

**Enabling a page.** Two lists in `docs/conftest.py`, and the difference is what
the page claims:

| list | blocks run | assertions checked | use it when |
|---|---|---|---|
| `EXECUTED_RECIPES` | yes | yes | the examples assert their outputs |
| `EXECUTE_ONLY_RECIPES` | yes | nothing to check | the examples only need to not raise |

The ratchet is about *assertions* and is unchanged: a page joins
`EXECUTED_RECIPES` only once its examples assert rather than decorate with `# =>`.
What the second list removed (#656) is the third state — a page with `python`
blocks that **nothing ran at all**, so a signature change broke a published
example in silence. Eight pages were in it.

`tests/test_doc_recipe_coverage.py` keeps that state gone: a page with a `python`
block and no listing fails there. Add the page to a list rather than widening the
exclusion.

## `README.md` is the source; `docs/index.md` is generated (#656)

Do not edit `docs/index.md`. It is produced by `scripts/generate_docs_index.sh`
from `README.md` plus `docs/_index_nav.md`, which rewrites the `(docs/…)` link
prefixes and appends the site navigation. Edit one of the two sources and
regenerate:

```bash
bash scripts/generate_docs_index.sh           # write it
bash scripts/generate_docs_index.sh --check   # fail if it is out of date
```

The banner at the top of the file said this already, and it did not hold. Before
the `--check` gate existed the file had drifted **both ways at once**: two
*Features* bullets lived only in the generated file, where the next run would have
deleted them, and a Node.js nav entry, a whole-script-spoof example and a
coverage-residue note lived only in the sources and had never reached the site.
The second kind is the dangerous one — the change appears on GitHub, so it looks
applied.

**This is also what executes the README.** Every `python` block in `README.md`
lands in `docs/index.md`, which is first on `EXECUTED_RECIPES` and runs under
Sybil on every CI run. In sync, the README's examples are asserted; out of sync,
they are not. So a README example is written to the same standard as any other
recipe: assert outputs, never decorate them with `# =>`.

## Per-language usage tabs (Rust & Ruby)

User-guide pages show usage in `pymdownx.tabbed` tabs — `=== "Python"` /
`=== "Rust"` / `=== "Ruby"` — over shared, language-neutral concept prose (#50).
**Each binding's tab may only use functions that binding actually exposes** (Rust
≈ the full `disarm::api`; Ruby is a smaller surface — see
`bindings/ruby/lib/disarm.rb`). Do not invent a call; if a topic isn't in a
binding, omit that tab. Every tab is gated:

```bash
python scripts/check_doc_rust_examples.py   # compile + run every ```rust block
ruby scripts/check_doc_ruby_examples.rb      # eval every Ruby `# =>` line (needs the built gem)
```

- **Rust tabs** use `assert_eq!`. The gate extracts every ```rust block, wraps
  each in a `#[test]`, and compiles + runs it against the pure core with
  `#![deny(unused_must_use)]` — so an example that **discards** its result (a
  `Result`, `Vec`, or `Cow`) is a hard error. Assert the output; don't leave a
  bare call with a `// =>` comment. Mark a genuinely illustrative block (a trait
  sketch, a macro) with `<!--- rust-skip -->` (the Rust gate's own opt-out —
  distinct from Python's `<!--- skip: next -->`, which Sybil would choke on
  before a non-Python block).
- **Ruby tabs** document outputs with `# =>` and start with `require "disarm"`.
  The gate evals each `Disarm.* # => value` line against the freshly-compiled gem
  (it tolerates trailing prose after the literal). It runs in the Ruby workflow
  on `bindings/ruby/**` **and** `docs/**` changes.
