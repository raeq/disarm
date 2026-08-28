# Language bindings

disarm is **one pure-Rust core** (`disarm` on crates.io, `unsafe_code = "forbid"`)
wrapped by per-language bindings. This document is the standard for what a binding
must deliver, written so that **each new language is one clean cycle, not three**.

The Ruby binding (`bindings/ruby/`) is the reference implementation — read it
alongside this document; the design discussion is in #45 and #357, and the
release/cross-build lessons are baked into the checklist below.

## The principle: native-feeling, not transliterated

A binding is **not** a 1:1 re-export of the Rust or Python API. It must read as if a
fluent speaker of the target language wrote it — its naming, its error handling, its
packaging, its docs. The shared *behaviour* comes from the core; the *surface* is the
ecosystem's, every time. A user of the binding should never be able to tell it is
"really Rust underneath."

Two corollaries shape every binding:

- **The algorithm cores stay binding-neutral.** The Layer-1 algorithm modules carry no
  binding types at all. The one binding that exists today (PyO3) keeps its glue — the
  `#[pymodule]` in `lib.rs`, the `From<ErrorRepr> for PyErr` in `error.rs`, and
  `src/py/*` — **feature-gated** (`extension-module`) at the crate's edge, never inside
  the cores. A new binding adds its own glue at its own edge, consumes the pure `disarm`
  crate (or its C-ABI), and the algorithm modules never learn it exists — the same
  boundary `src/obs.rs` states for logging ("No `pyo3`/`napi`/`wasm` ever appears in
  this path").
- **Two layers per binding.** A thin **native shim** exposes the core's functions with
  raw, positional, string-token signatures; a **pure-target-language idiomatic layer**
  sits on top and is the only thing users touch. In Ruby that is the `_`-prefixed
  magnus functions (`ext/disarm/src/lib.rs`) under the hand-written `lib/disarm.rb`.
  Keeping the shim dumb means the core's surface can be reshaped without re-teaching
  every binding the idioms.

## Definition of done — the per-binding checklist

A binding is shippable only when **all** of these hold. Treating any one as "later" is
exactly what turns one cycle into three.

### Surface
- [ ] **Idiomatic API.** Naming, argument style, and call shape match the ecosystem
  (see the table). No Rust/Python spellings leaking through.
- [ ] **Idiomatic options.** Keyword args / options objects / builders / sensible
  defaults, as the language expects — never a wall of positional booleans.
- [ ] **Idiomatic enums / tokens.** Symbols (Ruby), string unions or `const enum` (TS),
  typed enums (Java/Go) — accepted in the form that ecosystem reaches for.
- [ ] **Error model mapped to the idiom.** A native error type/hierarchy
  (`Disarm::Error < StandardError`, a `DisarmError` JS class, a Go `error` value, a
  Java exception) over the core's `ErrorKind` — never raw strings or the host
  language's bare `RuntimeError`/`Error`.

- [ ] **ABI/API additions are additive.** For the C ABI specifically, an exported
  function's signature is frozen once released: widening it breaks every linked caller.
  Add an `_opts` variant and keep the original delegating to it. The committed
  `bindings/cabi/disarm.h` makes any change show up as a diff (#580).

### Docs & tests (idiomatic and first-class, not an afterthought)
- [ ] **README in the ecosystem's voice.** Install via *its* package manager; every
  example in *its* idiom; nothing copied verbatim from the Python README.
- [ ] **Docs** — a per-language usage page that plugs into the language-neutral-core +
  per-language-specifics structure (#50). Concepts are shared; usage is native.
- [ ] **Tests in the language's native framework** (RSpec, vitest/jest, `go test`,
  JUnit, PHPUnit, testthat). They cover the *idiom* (defaults, token coercion, error
  mapping) and *behavioural parity* with the core — not merely "it loads."

### Build & release
- [ ] **Self-contained dependency on the published core.** Depend on `disarm` from
  crates.io **by version, never a repo path** — the release build container only
  mounts the binding directory, so a path dep cannot resolve. (The Ruby gem learned
  this at release time.)
- [ ] **Precompiled native artifacts** for the platforms the ecosystem expects
  (cross-gems, napi prebuilds or a `wasm` build, per-OS JNI jars, …) so a plain
  install needs no Rust toolchain.
- [ ] **CI builds + tests the binding on its platform matrix — and also compiles the
  binding against core changes.** A path-filtered "bindings only build on binding
  changes" pipeline let a core-API change (a tuple → struct return) ship a broken 0.10
  gem; the cross-build only ran at release. Guard against drift: build every binding in
  the core's own CI, or pin a contract test.
- [ ] **Release via OIDC / trusted publishing** where the registry supports it
  (RubyGems, npm, and PyPI all do) — not a long-lived API key. It is more secure *and*
  sidesteps MFA-blocked `push` (an API-key gem push prompts for WebAuthn and times out).
- [ ] **The full release build reproduced locally** (cross-compile + package — e.g. the
  registry's own docker image) **before tagging.** Packaging bugs then surface in
  minutes locally instead of against an immutable published version.

### Versioning (see [RELEASING.md](RELEASING.md) → *Across languages*)
- [ ] Ships in a **lockstep minor** with the other registries (a new binding is the
  headline of a minor, the way Ruby was `0.10`). Per-registry **patch** fixes may
  diverge.

**Binding ↔ core compatibility.** The shared `0.MINOR` *is* the compatibility statement:
a binding's `0.MINOR.x` wraps core `0.MINOR`, in every ecosystem at once. As of **0.14**,
all registries are aligned:

| Artifact | Registry | Wraps core |
|----------|----------|------------|
| `disarm` crate | crates.io | — (is the core) |
| `disarm` wheel | PyPI | `0.14` |
| `disarm` gem | RubyGems | `0.14` |
| `disarm` package | npm | `0.14` |
| `dev.disarm:disarm` | Maven Central | `0.14` |
| `dev.disarm:disarm-kotlin` | Maven Central | `0.14` |

Per [RELEASING.md](RELEASING.md), a fix touching one binding may ship as a per-registry
**patch** (e.g. an npm-only `0.11.3`) without re-cutting the others — so the third
component can drift while the `0.MINOR` feature set stays identical. When that drift gets
confusing, update the *Wraps core* column above rather than forcing no-op releases.

### JVM signature stability (#588)

Every public Kotlin function with a default argument carries **`@JvmOverloads`**. This is
not stylistic. A Kotlin default compiles to one JVM method plus a synthetic `$default`
bridge, not to an overload per arity, so **adding a defaulted parameter deletes the
signature that shipped** — anything compiled against the previous artifact gets
`NoSuchMethodError`, Java callers and un-recompiled Kotlin callers alike.

It happened twice before anyone noticed. `disarm-kotlin:0.13.0` published
`normalizeConfusables(String, TargetScript)` and `analyzeHostname(String)`; #574 and #562
each added a default and removed one. #562 made the identical break in the C ABI, where it
*was* caught and reverted by #580 — that surface has a committed, drift-gated header, and
this one had nothing.

`JvmSignatureTest` is now the equivalent gate. It reads the compiled facade by reflection
rather than the source text, and fails when any defaulted function exposes only its widest
arity. Adding a parameter without `@JvmOverloads` turns it red.

The cost is generated methods, not maintained ones: `slugify` has twelve defaults and so
emits thirteen arities. That is the price of the guarantee, and it is paid by the compiler.

## Per-language conventions

Starting points, not mandates — pick the binding tech the ecosystem actually trusts at
release time.

| Language | Native tech | Registry | Naming | Errors | Tests | Docs |
|---|---|---|---|---|---|---|
| **Ruby** ✅ #45 | magnus + rb-sys | RubyGems | `snake_case`, `?` predicates, symbols | `Disarm::Error < StandardError` | RSpec | YARD / markdown |
| **Node** #44 | napi-rs (native) or wasm-pack | npm | `camelCase`, options objects, string unions, `.d.ts` | `DisarmError extends Error` | vitest / jest | TSDoc + types |
| **Go** #47 | cgo over the C-ABI | pkg.go.dev | exported `CamelCase`, `(T, error)` | `error` values, `errors.Is` sentinels | `go test` | godoc |
| **Java** ✅ #43 | JNI over safer-ffi | Maven Central (`dev.disarm:disarm`) | `camelCase`, builders, packages | `DisarmException` hierarchy | JUnit | [JVM API](https://docs.disarm.dev/java/api.html) + Javadoc |
| **Kotlin** ✅ #43 | (rides the Java artifact) | Maven Central (`dev.disarm:disarm-kotlin`) | `String` extensions, default args, `@JvmOverloads` | shares the Java hierarchy | kotlin.test | [JVM API](https://docs.disarm.dev/java/api.html) + KDoc |
| **PHP** #46 | ext-php-rs | Packagist / PECL | PSR, namespaced | `DisarmException` | PHPUnit | phpDocumentor |
| **R** #48 | extendr | CRAN | `snake_case` / `.` funcs | `condition` / `stop()` | testthat | roxygen2 + vignette |

## Reference & sequencing

- **Reference implementation:** `bindings/ruby/` — the magnus shim
  (`ext/disarm/src/lib.rs`), the idiomatic layer (`lib/disarm.rb`), RSpec specs, the
  README, and `publish-ruby.yml` (cross-gems + OIDC trusted publishing).
- **Do the docs restructure (#50) early.** Its trigger — "core + at least one
  non-Python binding published" — was met when Ruby shipped in `0.10`, so the
  language-neutral docs scaffold is already due, and every subsequent binding plugs
  straight into it instead of bolting on a Python-shaped page.
