# The bindings as faithful surfaces over the core

This directory checks the repository's central invariant for bindings: **the Rust core is
the single source of truth, and every binding is a thin, faithful surface over it.** It
holds a differential harness that drives every scalar value of Unicode plus a 40,000-string
corpus through the core and through the Python, Node, Ruby, Java and C bindings and
compares the answers byte for byte; a TLA+ model of the C ABI's ownership and input
protocol (`../tla/CABI/`); C programs that exercise the real C library under
AddressSanitizer and valgrind; and one reproduction per finding, in the language the
finding is about.

> **Status.** Every finding below was reproduced on the built library at the baseline.
> C1 is fixed and C2 and C3 documented in the C ABI contract (#1020). J1, R1, B1, B2, S1,
> D1, E1, E2, N1, N2 and J2 are fixed and E3 documented (#1046): the rule or default each
> one is about now lives in the core, and every binding reads it from there. D1 kept
> Python's documented `[?]` and moved the other bindings to it; E2 kept the documented
> `ErrorKind::Unsupported` and moved the code. Re-run after #1046 on the cases these
> findings touch (`tr`, `tr_de`, `tr_uk`, `tr_auto`, `tr_bad`, `sa`, `dj`, `dj_sm`, `fu`,
> `slug`, `zs`, `zs_def`, `zi_def`, `nc_ara`, `nc_heb`, `fc`, `re_empty`; `zs_def` and
> `zi_def` are new and call each binding's own default): 89,860,992 comparisons, no
> difference in any binding, Java now expressing `nc_ara` and `nc_heb`. The C runner's
> `tr_bad` blocks differ by CRC only, because C errors carry no kind and are compared by
> message. The `surr 3000 7` relational check passes in Python, Node and Ruby on all 79
> cases; Java has no such mode yet, and J1 is pinned by `FormalFindingsTest` and the
> shim's unit tests instead. The sections below describe the baseline.

Baseline: worktree at `595fbda` (main before #1016). Bindings built against the
**in-repo** core with the `[patch.crates-io]` redirect from AGENTS.md ("Binding gates"),
manifests reverted afterwards (`build.sh`). Python: the prebuilt 0.16.0 extension,
CPython 3.11.15. Node 22.22.2 (napi 3), Ruby 3.3.6 (magnus 0.8), OpenJDK 21.0.10 (jni
0.22.4), gcc 13.3 (safer-ffi 0.1.13), rustc 1.94.1, TLC 2.19 (tla2tools 1.7.4),
valgrind 3.22.

## Findings at a glance

Classes: (a) bug, (b) documentation overclaims, (c) parity gap against a documented claim.

| # | What | Binding | Class | Severity |
|---|------|---------|-------|----------|
| C1 | The C ABI never validates UTF-8: bytes that are not UTF-8 become a `&str` in safe Rust. Observed: segfaults, aborts (a panic in an `extern "C"` function), non-UTF-8 returned to the caller, and a different CJK character made up out of Latin-1 input | C | a | high |
| C2 | `NULL` for any `char const *` not documented as nullable is a segfault (release) or an abort (debug); the header does not say non-NULL | C | a/b | medium |
| C3 | Every empty result is one shared pointer into read-only memory, returned as an owned `char *`: a store into it faults; a store that shortens a heap result frees with the wrong `Layout` (model only) | C | a/b | medium |
| J1 | A lone surrogate becomes **three** U+FFFD, and one lone surrogate anywhere turns every well-formed emoji in the same string into six U+FFFD: `replaceEmoji` then removes nothing | Java/Kotlin | a | medium |
| R1 | The Ruby shim reads a String's bytes as UTF-8 whatever its encoding says: an ISO-8859-1 `"caf\xE9"` transliterates to `"caf[?]"`, a Windows-1251 word to `"[?][?][?][?][?][?]"` | Ruby | a | medium |
| B1 | `strip_zalgo`'s default cap is 2 in Node and Ruby; the core's is 3 since #788, and Python's is 3 | Node, Ruby | a | medium |
| B2 | An unknown `lang` is silently ignored by `transliterate`, `find_untranslatable` and `slugify` in Node, Ruby, Java, C and the Rust API, and rejected by Python (#68) and by `search_key` in the same bindings | all but Python | a | medium |
| S1 | `strip_accents` on a character with a singleton canonical decomposition depends on the rest of the string: `U+037E` stays `U+037E` alone but becomes `;` beside any combining mark; Python always folds it. 1,401 of 1,152,064 inputs differ | core; Python vs the rest | a | medium |
| D1 | `demojize` of an emoji it cannot name: `""` in the core, Node, Ruby, Java and C; `"[?]"` in Python. 3,105 inputs differ | Python vs the rest | a | low |
| E1 | `api::register_replacements` is documented as "applied before the tables", but no public Rust API function applies it; only the PyO3 glue does | Rust API vs Python | a | medium |
| E2 | The Rust API documents `ErrorKind::Unsupported` for a sealed registration; `kind()` returns `Other` | Rust API | b | low |
| E3 | `disarm_is_canonical` returns `-1` for any error, documented as "`preset` names neither a preset nor a profile"; a `ResourceLimit` on a valid preset also gives `-1` | C | b | low |
| N1 | Node size arguments (`maxMarks`, `threshold`, `maxGraphemes`, `maxLength`) accept `NaN`, fractions and `2**64` and coerce them: `stripZalgo('caf\u00e9', { maxMarks: NaN })` strips the accent | Node | a | low |
| N2 | "Everything disarm throws is a `DisarmError`" (Node docs): the infallible functions throw a plain `Error` on a wrong argument type. Ruby's `bidi_control?` likewise raises a bare `TypeError` | Node, Ruby | b | low |
| J2 | The core, C, Python, Ruby and Node (at run time) accept `arabic` and `hebrew` confusable targets (#792); the Java/Kotlin `TargetScript` enum has only `LATIN` and `CYRILLIC`, and Node's `TargetScript` type omits them too | Java/Kotlin, Node types | c | low |

Checked and clean: 429,719,872 differential comparisons in all (every case of every
binding over all 1,112,064 scalars and the corpus), with no difference but B2, S1 and D1; the surrogate contract of #469 in Python, Node and Ruby (77 cases
x 3,000 random surrogate-laced strings each, no difference); the C ownership protocol for
a client that keeps the unwritten rules (TLC, and ASan/LSan/UBSan/valgrind on the real
library); `python/disarm/_core.pyi` against the extension's run-time signatures (85
functions, no difference); every option default of Java, Kotlin, Node, Ruby and Python, by reading them
(all agree with the core except B1).

## The harness

A **case** is one function with one fixed set of options (`tr_de` is `transliterate` with
the `de` profile; `nc_lat_tr39` is `normalize_confusables` to Latin under the `tr39` digit
policy). There are 77, listed in `difftest.py`'s `ALL_CASES`. Every runner implements the
same protocol:

* **Inputs.** Index `i < 1,112,064` is the `i`-th Unicode scalar value (surrogates
  skipped); the next 40,000 are the lines of `corpus.hex` (hex of UTF-8, so no runner
  has to agree with another on escaping), generated by `gen_corpus.py` from a fixed seed:
  hand-picked spoofs and sequences, random strings of up to 40 characters from 29 pools
  (combining marks, bidi controls, tags, variation selectors, emoji modifiers, PUA,
  noncharacters, supplementary planes, digits of several scripts, ...), a 64 KiB mixed
  string and a 1 MiB one.
* **Encoding.** Every result is written in one canonical form `V`: `s<len>:<utf8>`,
  `b0`/`b1`, `i<n>;`, `n`, `l<n>:` and `r<n>:` for lists and structs (fields in
  declared order); an error is `e<inv|err>:` plus its message, `inv` meaning the
  binding's InvalidArgument class. So a structured report (`HostnameAnalysis`,
  `AnomalyReport`) is compared field by field, including byte offsets.
* **Comparison.** Each runner prints a CRC-32 of the encodings per block of 4,096
  inputs; `difftest.py` re-runs every block whose CRC differs from the Rust oracle's in
  `dump` mode on both sides and compares input by input.

| Runner | Drives | Notes |
|---|---|---|
| `rust_oracle` | `disarm::api` directly | the reference |
| `runners/py_runner.py` | the public `disarm` package | through `_api.py` and `_boundary.py`, so the Python wrapper layer is under test |
| `runners/c_runner.py` | `libdisarm_ffi.so` through ctypes | an ordinary C caller: `char *` in, copy out, `disarm_string_free` every pointer; U+0000 is skipped (a C string cannot carry it); C errors carry no kind, so they are compared by message |
| `runners/node_runner.cjs` | `bindings/node/index.js` | the idiomatic TypeScript layer, not the raw napi shim |
| `runners/ruby_runner.rb` | `lib/disarm.rb` | the idiomatic layer |
| `runners/JavaRunner.java` | `dev.disarm.Disarm` | loads `libdisarm_jni.so` via `-Ddisarm.native.lib` |

**Validating the harness.** Before its results counted: (1) with `HARNESS_PERTURB=i`, the
Python-hosted runners corrupt the one record for input `i`; `difftest.py` must then report
exactly that input and no other, and did (`U+7A920` for `i = 500000`, in both the Python
and C runners, in `tr` and `fc`); (2) the known Python-only `lang` rejection (#68) shows
up as case `tr_bad` differing on every input, as it must; (3) the C runner's skipped NUL
shows up as block 0 differing by CRC and then as zero differences input by input.

### Coverage

| Binding | Cases | Comparisons | Differences | Not expressible in the binding |
|---|---|---|---|---|
| Python | 77 | 88,708,928 | `tr_bad` (every input, B2), `sa` 1,401 (S1), `dj`/`dj_sm` 3,105 each (D1) | none |
| Node | 77 | 88,708,928 | none | none |
| Ruby | 77 | 88,708,928 | none | none |
| Java | 75 | 86,404,800 | none | `nc_ara`, `nc_heb` (J2) |
| C | 67 | 77,188,288 | none | `isn_nfc`, `gsplit`, `gtrunc1`, `ds`, `ha`, `fu`, `slug`, `zs`, `zi`, `isconf` (the C ABI does not export them) |

Kotlin was not built (it needs Gradle and the Kotlin plugin); it delegates every call to
the Java facade, so the Java rows cover its behaviour but not its signatures.

The boundary for malformed input is checked separately, relationally: `surr N SEED` mode
in the Python, Node and Ruby runners builds strings of random lone surrogates, pairs
written as two separate code units, and ordinary text, and requires `f(s) =
f(scrub(s))` for every case, where `scrub` is THREAT_MODEL.md's contract (pairs recombine,
each lone surrogate is one U+FFFD). 77 cases x 3,000 strings per binding, no difference.
Java has no such mode because it fails on the first input (J1).

`surface.py` inventories the public functions: of the 75 `disarm::api` functions the
bindings could expose, Python exposes 72, Node and Ruby 60, Java 59 and C 47. That is
not a finding in itself: the docs claim a shared set only for the functions named in
`docs/concepts/which-function.md`, and every binding has all of those.

## The C ABI

### The model (`../tla/CABI/CABI.tla`)

One C client makes up to `MaxCalls` calls, then frees everything it owns. The library
side is the code as written:

| Code | File:line | In the model |
|---|---|---|
| every text argument is `char_p::Ref`, read with `to_str()` | `bindings/cabi/src/lib.rs` (e.g. 66-67, 72-81); `safer-ffi-0.1.13/src/char_p.rs:223-231` (`from_utf8_unchecked`) | `BadCall("invalid_utf8")` is UB |
| `char_p::Ref` is `NonNull`; `from_raw_unchecked` on NULL | `safer-ffi-0.1.13/src/layout/_mod.rs:851-864` (`unreachable_unchecked` in release, a panic hence abort in debug) | `BadCall("null")` is UB |
| nullable arguments are `Option<char_p::Ref>` | `lib.rs:58` (`opt_str`), `lang` parameters | not modelled as bad |
| an empty output is not allocated: the address of `static EMPTY_SENTINEL` | `char_p.rs:468-484`; its drop skips that address, `char_p.rs:506-512` | `OutAddr(0, _) = STATIC` |
| a non-empty output's drop frees `strlen + 1` bytes | `char_p.rs:513-519` | `Free` checks `strl + 1 = len` |
| `DisarmResult`: exactly one half non-NULL | `lib.rs:32-56` | `ResultCall`, `ResultExclusive` |
| `disarm_string_free(NULL)` is a no-op | `lib.rs:919-925` | `Free` of a NULL handle |

The client is the one `disarm.h` describes: any `char const *` in `Inputs`, owns every
returned `char *` (mutable, so `ClientWrites` lets it store into the buffer, including a
NUL that shortens it), and frees each pointer once. Invariants: `NoNullArgUB`,
`NoInvalidUtf8UB`, `NoWriteToStatic`, `NoLayoutMismatch`, `NoDoubleFree`,
`ResultExclusive`, `NoLeak`, `NoAlias`.

| Config | Models | Result | States generated / distinct |
|---|---|---|---|
| `CABI_utf8.cfg` | the code; the client passes non-UTF-8 | **`NoInvalidUtf8UB` violated** (C1) | 2 / 2 |
| `CABI_null.cfg` | the code; the client passes NULL | **`NoNullArgUB` violated** (C2) | 2 / 2 |
| `CABI_write.cfg` | the code; the client stores into a result it owns | **`NoWriteToStatic` violated** (C3) | 29 / 26 |
| `CABI_truncate.cfg` | the code; the client shortens a heap result, then frees it | **`NoLayoutMismatch` violated** (C3) | 87 / 61 |
| `CABI_alias.cfg` | the code; two empty results | **`NoAlias` violated** (C3) | 90 / 68 |
| `CABI_contract.cfg` | the code, with a client that keeps the unwritten rules (non-NULL, UTF-8, read-only results), 3 calls | **pass** (all but `NoAlias`) | 9,647 / 2,800 |
| `CABI_fixed.cfg` | the proposed fix, every input the header admits, read-only results, 3 calls | **pass** | 14,033 / 3,844 |

The model was validated before its results counted: `mutants.py` breaks one rule at a
time (a client that stops before freeing, a library that hands out an address twice, a
failed call that fills both halves, a drop that frees one byte too few), and TLC reports
exactly the matching invariant on `CABI_contract.cfg` for each. So the contract pass is a
proof that the rules hold on every interleaving of three calls, not an artefact of an
invariant that cannot fail.

### The real library (`cabi/`)

`cabi/run.sh` compiles `contract.c` (every exported function on success and error paths,
the `DisarmResult` rule, UTF-8 validity of every output, every pointer freed) against
`libdisarm_ffi.so`:

* ASan + LSan + UBSan: 523 string-returning calls, 0 failures, no leak, no invalid access.
* LSan self-test: the same program with one `disarm_string_free` skipped reports
  `106 byte(s) leaked in 8 allocation(s)`: eight, not nine, because one of the nine
  inputs gives an empty result, which is the sentinel and was never allocated (C3).
* valgrind memcheck: 0 errors, 0 bytes definitely lost.

`cabi/repro.c` reproduces C1-C3 (below); valgrind reports `Invalid read of size 1` inside
`disarm_strip_bidi` for C1.

## Findings

Reproductions: `repro/`, `cabi/repro.c`, and `rust_oracle/src/bin/core_repro.rs`
(`cargo run --release --bin core_repro`). Outputs below are copied from runs on the
baseline; non-ASCII is shown escaped.

### C1: the C ABI accepts bytes that are not UTF-8 (a, high)

Every entry point passes its `char_p::Ref` arguments through `to_str()`
(`bindings/cabi/src/lib.rs`, e.g. line 67), which in safer-ffi 0.1.13 is
`str::from_utf8_unchecked` (`char_p.rs:223-231`); `ReprC::is_valid` for the pointer
checks only non-NULL. A `&str` that is not UTF-8 is undefined behaviour in safe Rust, and
the core's code reads it as UTF-8. `./repro utf8`, abridged:

```
input "caf\xE9" (Latin-1)      disarm_strip_bidi       -> SIGSEGV
                               disarm_fold_case        -> abort: "byte index 162 is out of bounds" (case_fold.rs:53),
                                                          "panic in a function that cannot unwind"
                               disarm_canonicalize     -> value "caf\xE9" (not UTF-8), error NULL
input "\xC0\xAF" "etc"         disarm_transliterate    -> abort: "byte index 1 is not a char boundary" (transliterate.rs:700)
                               disarm_canonicalize     -> abort (presets.rs:878)
input "a\xED\xA0\x80z"         disarm_strip_bidi       -> "a\xED\xA0\x80z" (not UTF-8)
                               disarm_transliterate    -> abort: "nfkc output is valid utf8" (transliterate.rs:881)
input "\xE9t\xE9"              disarm_strip_bidi       -> "\xE9\xB4\xA9" = U+9D29, a CJK ideograph
```

`disarm.h` says strings "cross the boundary as NUL-terminated UTF-8" but not that the
caller must guarantee it, and THREAT_MODEL.md ("Malformed-Unicode input at the binding
boundary") says every binding sanitizes malformed input at the boundary. C text from
files, sockets and `argv` is routinely Latin-1 or truncated.

Fix: decode once per argument with `String::from_utf8_lossy(r.to_bytes())` (the #469
contract: malformed input becomes U+FFFD and the call proceeds), in one helper used
instead of `.to_str()`. No signature changes, so `disarm.h` does not move.

### C2: NULL for a non-nullable argument (a/b, medium)

`disarm_transliterate(NULL)` is killed by SIGSEGV (`./repro null`) in a release build; a
debug build aborts on safer-ffi's "not a valid bit-pattern" panic. The header gives
`text` the same `char const *` type as the nullable `lang`, and says only that nullable
arguments may be NULL. Fix: declare every text parameter `Option<char_p::Ref<'_>>`, which
leaves the C signature identical (`char const *`), and return an error `DisarmResult`
(or NULL from a plain `char *` function) on `None`; at the least, document "every other
pointer argument must be non-NULL" in the crate docs that generate `disarm.h`.

### C3: an empty result is shared, read-only memory (a/b, medium)

```
two empty results: 0x7f94eb67fbf1 and 0x7f94eb67fbf1 (SAME pointer)
a common idiom on an owned char*: s[strcspn(s, "\r\n")] = '\0'
child killed by signal 11 (Segmentation fault)
```

safer-ffi represents `""` as the address of `static EMPTY_SENTINEL: u8`
(`char_p.rs:468-484`), and `to_c` (`lib.rs:28-30`) returns it for every empty output. The
header returns a mutable `char *` whose ownership "transfers to the caller", so a store
into it is legitimate C. The same root cause makes a store that shortens a heap result
unsound: the drop recomputes the length with `strlen` (`char_p.rs:513-519`) and frees a
`Box<[u8]>` of the wrong size, which violates `GlobalAlloc`'s `Layout` contract (not
observable with the system allocator, which ignores the size; TLC `CABI_truncate.cfg`).
Fix: document in the crate docs (hence `disarm.h`) that returned strings are read-only
until freed; this is what `CABI_fixed.cfg` checks.

### J1: Java turns a lone surrogate into three U+FFFD, and breaks the rest of the string (a, medium)

`java JavaRepro` (`repro/JavaRepro.java`):

```
transliterate("a\ud800b")                            "a[?][?][?]b"            Node: "a[?]b"
graphemeLen("a\ud800b")                              5                         Node: 3
replaceEmoji("x\U0001f600y\ud800", "")             "x\ufffd\ufffd\ufffd\ufffd\ufffd\ufffdy\ufffd\ufffd\ufffd"
                                                                               Node: "xy\ufffd"
demojize("\U0001f600 \ud800")                      six U+FFFD, " ", three U+FFFD  Node: "grinning face \ufffd"
```

Every JNI entry point reads its string with `mutf8_chars(env)?.to_string()`
(`bindings/java/rust/src/lib.rs:110` and the other `map_*` helpers). jni 0.22.4 decodes
modified UTF-8 and, if that fails anywhere in the string, falls back to
`String::from_utf8_lossy` over the whole CESU-8 buffer (`jni-0.22.4/src/strings/ffi_str.rs:109-119`),
so each surrogate's three bytes become three U+FFFD, and every well-formed astral
character in the same string (a six-byte surrogate pair in CESU-8) becomes six. An emoji
then no longer matches as an emoji: `replaceEmoji` removes nothing. THREAT_MODEL.md says
every binding maps each lone surrogate to one U+FFFD; the shim's own header comment
(lib.rs:30-34) records the gap as a follow-up. Fix: read UTF-16 (`GetStringChars` /
jni's `get_string` over UTF-16) and decode with `char::decode_utf16(..).map(|r|
r.unwrap_or('\u{FFFD}'))`, as the Node binding effectively does.

### R1: Ruby ignores the String's encoding (a, medium)

`ruby -I bindings/ruby/lib repro/ruby_encoding.rb`:

```
input (ISO-8859-1)                           ISO-8859-1             "caf\xE9"
Disarm.transliterate(latin1)                 UTF-8                  "caf[?]"
Disarm.transliterate(latin1.encode(UTF-8))   UTF-8                  "cafe"
Disarm.fold_case(utf16)                      UTF-8                  "c\x00a\x00f\x00\ufffd\x00"
Disarm.transliterate(cp1251)                 UTF-8                  "[?][?][?][?][?][?]"
Disarm.transliterate(cp1251.encode(UTF-8))   UTF-8                  "Moskva"
Disarm.edit_distance(latin1, "caf\u00e9")    US-ASCII               "1"
Disarm.replace_emoji(e_acute, "")            UTF-8                  "\ufffd"
Disarm.replace_emoji("\u{1f600}", e_acute)   UTF-8                  "\u00e9"
```

`Wtf8Text::try_convert` (`bindings/ruby/ext/disarm/src/lib.rs:162-173`) copies
`RString::as_slice()` and decodes it as UTF-8/WTF-8 without looking at the String's
encoding, while the plain `String` parameters of the same functions go through magnus,
which transcodes: the last two lines are one function reading one encoding two ways.
Fix: in `try_convert`, when the String's encoding is neither UTF-8 nor US-ASCII nor
ASCII-8BIT, transcode to UTF-8 first (`RString::conv_enc`, or `encode("UTF-8")`), then
apply the WTF-8 scrub.

### B1: `strip_zalgo` defaults to a cap of 2 in Node and Ruby (a, medium)

#788 raised the cap to equal `is_zalgo`'s threshold, 3 (`src/zalgo.rs:22-47`,
`DEFAULT_MAX_MARKS`; CHANGELOG "strip_zalgo's cap now equals is_zalgo's threshold"), and
Python follows it. Node (`bindings/node/index.ts:420-421`, `options.maxMarks ?? 2`) and
Ruby (`bindings/ruby/lib/disarm.rb:384`, `max_marks: 2`) did not, so both remove a mark
from text their own `is_zalgo` declines to flag, which is the defect #788 fixed:

```
node:    isZalgo('a\u0316\u0317\u0318')  false    stripZalgo(..)  "a\u0316\u0317"
ruby:    zalgo?                           false    strip_zalgo(..) "a\u0316\u0317"
python:  strip_zalgo('a\u0316\u0317\u0318')        'a\u0316\u0317\u0318'
```

The docs repeat the stale value: `docs/node/api.md:257`, `docs/ruby/api.md:372`, and
`docs/user-guide/text-cleaning.md:79,93` ("default: 2", in the Python and Rust tabs too).
Fix: default 3 in both bindings; correct the four doc lines.

### B2: an unknown `lang` is silently ignored except in Python (a, medium)

`api::Transliterate::lang` stores the code and `run` uses it without validation
(`src/api/transliterate.rs:169-173, 198-218`); an unknown code falls back to the default
tables. `validate_lang` (`src/transliterate.rs:37-62`, #68) is called only from the PyO3
glue (`src/py/transliterate.rs:220, 332, 404`, `src/py/slugify.rs:53, 124, 224`) and the
presets. So the rule "a typo'd `lang` is rejected" lives in a binding, and the other four
bindings, which wrap `api::Transliterate` and `api::slugify`, do not have it:

```
Rust:   Transliterate::new().lang("UK").run(kyiv)   = "Kiyiv"   (with "uk": "Kyiv")
node:   transliterate(kyiv, { lang: 'UK' })           "Kiyiv"
        slugify('M\u00fcnchen', { lang: 'dee' })       "munchen"
        searchKey('M\u00fcnchen', { lang: 'zz' })      threw DisarmInvalidArgument: unknown language code 'zz' ...
ruby:   Disarm.transliterate(kyiv, lang: "UK")        "Kiyiv"
java:   transliterate(kyiv, lang("UK"))                "Kiyiv"
C:      disarm_transliterate_opts(t, "default", "xx")  value, no error (sweep case tr_bad)
python: transliterate(kyiv, lang='UK')                 InvalidArgumentError: unknown language code 'UK' (did you mean 'sk'?) ...
```

Fix: validate in the core. Add `pub fn validate_lang(&str) -> Result<(), Error>` to
`api` (or a fallible `Transliterate::try_run`, and the same check in `api::slugify`'s
config), and call it from the Node, Ruby, JNI and C shims where they call `.lang(..)`.

### S1: `strip_accents` on a singleton decomposition depends on the rest of the string (a, medium)

`api::strip_accents` returns its input borrowed when the NFD form has no combining mark,
on the stated premise that NFD -> strip -> NFC is then the identity
(`src/transliterate.rs:1584-1599`, `strip_accents_cow`). It is not, for a character with
a singleton canonical decomposition: NFC maps U+037E GREEK QUESTION MARK to `;`, U+2126
OHM SIGN to U+03A9, U+F900 to U+8C48. The owning path (`strip_accents`, line 1578) does
apply NFC, and the PyO3 glue calls that one (`src/py/transliterate.rs:19-21`), while
Node, Ruby, Java and C call `api::strip_accents`:

```
Rust api:   strip_accents(U+037E) = U+037E       strip_accents("a\u{37e}\u{301}") = "a;"
python      strip_accents("\u037e") = ';'  (U+003B SEMICOLON)
node/ruby/c strip_accents("\u037e") = "\u037e"
```

The sweep found 1,401 inputs that differ between Python and the others. The
non-compositionality matters for a key builder: the same character is or is not folded
depending on whether an unrelated accent occurs elsewhere in the string. Fix: take the
fast path only when the text is also NFC (`unicode_normalization::is_nfc_quick(..) ==
IsNormalized::Yes`, or `is_nfc`).

### D1: `demojize` of an unnameable emoji: `""` everywhere but Python, `"[?]"` in Python (a, low)

The core drops an emoji it cannot name (`src/emoji.rs:918-930`); Python's `demojize`
defaults to `errors="replace", replace_with="[?]"` (`src/py/emoji.rs:251`) and writes
the sentinel. 3,105 inputs differ, e.g. a lone regional indicator:

```
python  demojize("\U0001f1e6") = '[?]'
node / ruby / c / java         = ""
```

Python documents its default; the other bindings do not mention the case. Fix: pick one
answer for the same call. Either Python's default becomes `errors="ignore"` (the core's
behaviour), or the core grows the policy and every binding gets the parameter.

### E1: `api::register_replacements` has no effect on the public Rust API (a, medium)

Documented as "global pre-transliteration replacements (applied before the tables)"
(`src/api/transliterate.rs:275-282`). `api::transliterate` and `Transliterate::run` call
`transliterate_impl` directly (`src/api/transliterate.rs:198-218`); the pre-pass
(`apply_replacements_bounded`, `src/transliterate.rs:19`) is applied only by the PyO3
glue (`src/py/transliterate.rs:230, 333, 441`) and the context path:

```
Rust:   register_replacements({"foo": "bar"}); api::transliterate("foo") = "foo"
Python: register_replacements({"foo": "bar"}); transliterate("foo")      = 'bar'
```

Fix: apply the pre-pass in the core's transliterate path (a fallible `try_run`, since the
bounded pre-pass can fail), and have Python call it instead of re-implementing it; or,
at the least, document that replacements apply only to the Python binding.

### E2: sealed-registration errors are documented as `Unsupported` (b, low)

`src/api/transliterate.rs:269, 279, 285, 290` document `ErrorKind::Unsupported` "once
sealed"; `Error::kind` maps `Sealed` to `Other` (`src/error.rs:740`), and Python raises
the base `DisarmError` (`src/error.rs:642`), consistent with `Other`:

```
register_replacements after seal: kind = Other
python: register_replacements after seal raised DisarmError | UnsupportedError? False
```

Fix: change the four doc comments to `ErrorKind::Other` (or reclassify `Sealed`, which
would move Python's class too; `UnsupportedError` subclasses `DisarmError`, so that is
compatible).

### E3: `disarm_is_canonical` reports `-1` for errors other than an unknown preset (b, low)

`lib.rs:512-525` maps every `Err` to `-1` and documents `-1` as "`preset` names neither a
preset nor a profile". 600,000 x U+FDFA exceeds the NFKC output cap (#768):

```
python  is_canonical(text)                       raised ResourceLimitError
C       disarm_is_canonical(text, "canonicalize") = -1
```

Fix: document `-1` as "could not be answered (unknown preset, or a resource limit)", or
return `-2` for a non-InvalidArgument error.

### N1: Node coerces non-integer sizes (a, low)

napi converts a JS number to `i64` (`bindings/node/src/lib.rs:57-66`, `checked_size`
rejects only negatives): `NaN` becomes 0, `0.9` becomes 0, `2**64` saturates.

```
stripZalgo('caf\u00e9', { maxMarks: NaN })      "cafe"
graphemeTruncate('abcdef', NaN)                 ""
isZalgo('a\u0301\u0301', { threshold: NaN })    true
slugify('hello world', { maxLength: 5.5 })      "hello"
```

Python raises `TypeError` for a float; Ruby and Java take integers. Fix: in `index.ts`,
reject anything that is not `Number.isSafeInteger(n) && n >= 0` with
`DisarmInvalidArgument`.

### N2: not everything thrown is a `DisarmError` (b, low)

docs/node/api.md ("Errors"): "Everything disarm throws is a `DisarmError`". The
infallible wrappers call the native function directly, not through `call()`:

```
transliterate(123)                       threw Error; instanceof DisarmError = false
transliterate(123, { lang: 'de' })       threw DisarmError; instanceof DisarmError = true
stripAccents(undefined) / demojize(null) / graphemeLen(42) / hasBidiControl({})   Error
```

Ruby, likewise: `Disarm.bidi_control?(nil)` raises `TypeError`
(`bindings/ruby/lib/disarm.rb:516` is the one wrapper without `translate_errors`), where
every other function raises `Disarm::InvalidArgument`. Fix: wrap every native call in
`call()` / `translate_errors`, or narrow the sentence to fallible calls.

### J2: confusable targets the JVM surface cannot name (c, low)

The core, C (documented, `lib.rs:111`), Python, Ruby and Node at run time accept
`arabic` and `hebrew` (#792; CHANGELOG #884: "the confusable surfaces take `"arabic"`").
`dev.disarm.TargetScript` has `LATIN, CYRILLIC` only
(`bindings/java/disarm-java/src/main/java/dev/disarm/TargetScript.java`), so Java and
Kotlin cannot ask for them at all; Node's `export type TargetScript = 'latin' |
'cyrillic'` (`bindings/node/index.ts:121`) rejects them at compile time although the
runtime accepts them. Fix: add `ARABIC("arabic")`, `HEBREW("hebrew")` and the two union
members.

## Not confirmed

* **Truncate-then-free.** Shortening a heap result before `disarm_string_free` frees
  with the wrong `Layout` (C3; TLC `CABI_truncate.cfg`). With the system allocator
  `free` ignores the size, so nothing observable happens on this build; it is UB by
  Rust's allocator contract and would matter under a sized allocator.
* **Python's surrogate retry and one-shot iterators.** `_surrogate_safe`
  (`python/disarm/_boundary.py:68-79`) retries with scrubbed arguments; a generator
  consumed by the first attempt would be empty on the retry. Not reachable:
  `find_key_collisions` and `nearest_match` reject a generator before the boundary, and
  `has_anomalies` and `slugify(stopwords=...)` materialise it first
  (`repro/python_repro.py`, last block).
* **Retry running a callback twice.** A `UnicodeEncodeError` raised inside an
  `EmojiProvider.lookup` could trigger the retry; the provider's exceptions are caught and
  turned into a warning before they reach `_surrogate_safe`, so it does not.
* **`to_c` substituting `""` for an interior NUL** (`lib.rs:28-30`). No output of the
  sweep (every scalar but U+0000, and the corpus) contained a NUL, so the substitution
  never ran; it would be silent if it did.

## Running it

```bash
bash formal/bindings/build.sh                     # oracle + every binding, against the in-repo core
python3 formal/bindings/gen_corpus.py target/formal-bindings/work/corpus.hex
DISARM_PYTHON=/path/to/python-with-disarm python3 formal/bindings/difftest.py --jobs 4 \
    --out target/formal-bindings/work/full.json   # about 35 minutes on 4 cores
python3 formal/bindings/summarize.py target/formal-bindings/work/full.json
bash formal/bindings/cabi/run.sh                  # ASan/LSan/UBSan, valgrind, C1-C3
TLA2TOOLS=/path/to/tla2tools.jar bash formal/tla/CABI/run_tlc.sh
TLA2TOOLS=/path/to/tla2tools.jar python3 formal/tla/CABI/mutants.py
$DISARM_PYTHON formal/bindings/runners/py_runner.py surr 3000 7    # and node_runner.cjs / ruby_runner.rb
$DISARM_PYTHON formal/bindings/stubcheck.py
DISARM_PYTHON=... python3 formal/bindings/surface.py
```

The reproductions: `repro/node_repro.cjs`, `repro/errors_repro.cjs` (node);
`repro/ruby_repro.rb`, `repro/ruby_encoding.rb`, `repro/errors_repro.rb`
(`ruby -I bindings/ruby/lib`); `repro/python_repro.py`, `repro/python_core_repro.py`,
`repro/resource_limit.py`; `repro/JavaRepro.java` (`javac -cp <disarm-java classes>`,
then `java -Ddisarm.native.lib=<libdisarm_jni.so>`); `repro/sweep_findings.sh`; and
`cargo run --release --bin core_repro` in `rust_oracle/`.

`build.sh` appends the `[patch.crates-io]` redirect to each binding's manifest, builds,
and restores the manifest even when the build fails, then refuses to exit 0 if a
manifest still carries a redirect. Java is compiled with `javac` into the target
directory rather than through Gradle, because Gradle's `build/` and
`bindings/java/rust/target` are not gitignored.
