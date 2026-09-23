# Formal model of the output sanitizers and encoders (Lean 4)

Lean 4 models of `sanitize_filename` (`src/filename.rs`), `slugify` on the ASCII path
(`src/slugify.rs`), `UniqueSlugifier` (`src/py/slugify.rs`), `strip_log_injection`
(`src/log_injection.rs`), `escape_html` and `percent_encode` (`src/encoders.rs`), and
`edit_distance` / `nearest_match` (`src/utils.rs`, `src/api/safety.rs`). The models are
validated against the built library by differential testing; the postconditions the code
and docs claim are then proved about them, generally where possible and bounded
exhaustively otherwise. Every failed property was cut down to a minimal input and
reproduced on the library, through Python and through the Rust core.

The parts that rest on Unicode tables (`slugify(allow_unicode=True)`,
`is_suspicious_hostname`, `decode_to_utf8`, reverse transliteration) are not modelled.
They were swept directly against the library instead: every Unicode scalar alone and
embedded, plus the targeted grids below.

Written against `main` at `595fbda`. Line numbers (`L326`) refer to that commit. The
toolchain is core Lean 4.34.0 only, with no Mathlib.

## Layout

| File | Contents |
|---|---|
| `Sanitizers/Filename.lean` | `sanitize_filename`, branch by branch (`sanitize`), and the proposed fix (`sanitizeFixed`). |
| `Sanitizers/Slug.lean` | `slugify_impl_with_stopset` on the ASCII path (`slugify`), and the fix (`slugifyFixed`). |
| `Sanitizers/Unique.lean` | `_UniqueSlugifier::slugify` without `check`: with the per-base hint (`run`), without it (`runNoHint`), and the fix (`runFixed`). |
| `Sanitizers/LogInjection.lean`, `Sanitizers/Encoders.lean`, `Sanitizers/EditDistance.lean` | The other three, and the decoders the encoders are checked against. |
| `Sanitizers/Lists.lean` | List lemmas. |
| `Sanitizers/FilenameProofs.lean`, `SlugProofs.lean`, `UniqueProofs.lean`, `EncoderProofs.lean` | General theorems (induction). |
| `Sanitizers/Enumerate.lean`, `Sanitizers/Bounded.lean` | Grids and predicates; the bounded exhaustive theorems (`native_decide`). |
| `Sanitizers/Findings.lean` | The failed properties as minimal counterexamples, checked by the kernel (`decide`), with the fixed model's answer beside each. |
| `Sanitizers/Vectors.lean` | 54 documented examples (docs, docstrings, unit tests) replayed on the models (`decide`). |
| `Sanitizers/Axioms.lean` | `#print axioms` for the headline theorems (not in the default build). |
| `Main.lean`, `scripts/difftest.py` | The differential test. |
| `Explore.lean` | `lake exe explore 5`: per grid, how many cases fail each property, and the first. |
| `scripts/sweep_filename.py`, `sweep_slug.py`, `sweep_misc.py` | Direct sweeps of the library, no model. |
| `scripts/repro.py`, `scripts/repro.rs` | Every finding, on the Python binding and on the Rust core. |
| `scripts/escape_nonascii.py` | Rewrites non-ASCII in a script as escapes (the repository rejects literal invisibles). |

## The properties

Collected from the docstrings, `docs/` (including `docs/security/` and
`docs/limitations.md`), `THREAT_MODEL.md`, the Rust doc comments and the unit tests.

| Id | Property | Source |
|---|---|---|
| P1 | `sanitize_filename` never returns `""` | #485, `finalize_name` doc, `empty_input_never_returns_empty` |
| P2 | ... never `"."` or `".."` | #487, `never_returns_directory_reference` |
| P3 | ... no character illegal on the platform (`/ \ : * ? " < > \|` NUL; POSIX `/` NUL) | docstring, `docs/user-guide/filenames.md` table |
| P4 | ... no control character | `attacker_battery_all_safe` |
| P6 | ... no leading dot or space, no trailing dot or space | #485/#487, `finalize_name` doc |
| P7 | ... at most `max_length` bytes | docstring |
| P8 | universal/windows: the name is not a reserved device name, in any case, with any extension, after Windows' trailing dot/space strip | docstring, `docs/architecture/security.md`, `docs/limitations.md` |
| P9 | a sanitized name is a fixed point | #487 criterion 2, #570, `is_idempotent_over_the_battery` |
| S1 | `slugify` words are `[a-z0-9]` (ASCII path); `allow_unicode` keeps only L/N/M and inner ZWJ/ZWNJ | docstrings, #712 |
| S2 | no leading, trailing, doubled or partial separator | `slugify_output_charset`, review M-C1 |
| S3 | at most `max_length` bytes; `allow_unicode` cuts on a grapheme boundary, never ending in a joiner | docstring, #711 |
| S5 | `lowercase=True` output has no upper case | docstring |
| S6 | stopwords removed, case-insensitively (`save_order`: only at the ends) | `SlugConfig` docs, python-slugify parity |
| S7 | at most two combining marks per base (`allow_unicode`) | docstrings, #712 |
| U | `UniqueSlugifier` returns pairwise distinct slugs, each a slug (S2, S3) | class docstring |
| L1-L4 | `strip_log_injection`: no CR/LF/NEL/LS/PS/C0/C1/DEL (TAB unless `keep_tab`); idempotent; nothing else changed; a bad replacement rejected | docstring, `THREAT_MODEL.md` |
| E1, E2 | `escape_html` / `percent_encode` round-trip with their decoders; output inside the safe set | docstrings |
| H1, H2 | `is_suspicious_hostname`: `canonical` carries no bidi control or invisible; a hostname the mapping silently rewrites is flagged | docstring (#603, #605, #709) |

## The models

**Domain.** The filename and slug models take the text *after* NFC and transliteration,
and are run on ASCII input, where both are the identity (the differential test includes
TAB, NUL, the C0 controls and DEL, so this is checked, not assumed). On ASCII,
`neutralize_introduced_percent` never fires and `floor_char_boundary` is the identity, so
byte lengths are character counts. The models otherwise follow the code line by line:

| Rust (`src/filename.rs`) | Lean (`Filename.lean`) |
|---|---|
| L116-142 `collapse_dot_sequences`, applied at L210 and L227 | `collapse` (twice) |
| L248-255 trailing dot/space trim before the split | `rtrim isDS` |
| L257-265 split at the last dot, if not at index 0 | `split` |
| L268-281 stem loop, `prev_was_sep` | `stemLoop` |
| L284-286 strip trailing separators (`while`) | `stripSep` |
| L289-310 leading, then trailing, dot/space strip | `cleanStem` |
| L314-323 extension filter | `cleanExt` |
| L85-111 `apply_max_length` | `applyMax` |
| L326-338 reserved branch; L354-370 post-truncation check on the first-dot stem | the two `isReserved` tests in `sanitize` |
| L169-178 `finalize_name` | `finalize` |

| Rust (`src/slugify.rs`, ASCII path) | Lean (`Slug.lean`) |
|---|---|
| L648-666 lowercase | `lower` |
| L707-759 separator loop | `build` |
| L761-764 strip ONE trailing separator | `stripOnce` |
| L813-852 `filter_stopwords`, on `str::split` (including `split("")`) | `split`, `filterStop`, `join` |
| L786-802 truncation; L859-883 `truncate_at_boundary`; L891-903 partial-separator strip | `truncate`, `truncWord`, `stripPartial` |

`Unique.lean` models `build_unique_candidate` (`src/py/slugify.rs` L295-327) and the loop
at L416-479, including the `MAX_UNIQUE_ATTEMPTS` bound, the `min_unique_len` check and the
`lossy` flag, with `seen` and `next_counter` as association lists. `LogInjection.lean`
and `Encoders.lean` are the code (`is_log_injection_char`, `escape_html_str`,
`percent_encode_into` over UTF-8 bytes); `EditDistance.lean` is the row DP of
`utils::edit_distance` beside the recursive Levenshtein specification.

## Validation

### Differential testing (model vs library)

```bash
lake build difftest
python3 scripts/difftest.py --exhaustive 5 --random 300000 --seed 1016
```

| Model | Cases | Inputs |
|---|---|---|
| `sanitize_filename` | 8,803,040 | every word of length <= 5 over `. space / * _ c o n x` x separators `_`, empty, `-`, space x `max_length` 0-6, 8 x universal, POSIX x both `preserve_extension` (8,503,040), plus 300,000 random words <= 16 over 38 characters (controls, all Windows-illegal characters, `%`, `$`), random separators including `--`, `.` and `ab`, and `platform="windows"` |
| `slugify` | 2,539,440 | every word <= 5 over `a B 1 space - !` x separators `-`, empty, `--`, `-_`, `.` x `max_length` 0-5 x `word_boundary` x four stopword lists (2,239,440), plus 300,000 random |
| `UniqueSlugifier` | 30,005 | 30,000 random call sequences (1-12 calls, 9 texts, 4 separators, `max_length` 0-9, all flags) and five runs of 120 calls across the digit boundaries |
| `strip_log_injection` | 330,968 | every word <= 4 over 14 characters (CR, LF, TAB, NUL, ESC, DEL, NEL, CSI, LS, PS, RLO, ZWSP, `a`, `e`-acute) x 4 replacements x `keep_tab` |
| `escape_html`, `percent_encode` | 356,855 | every word <= 4 over 14 characters (the five metacharacters, space, `+`, `%`, `/`, `~`, a 2-byte and a 4-byte character, NUL) through all five encoders, plus 150,000 random |
| `edit_distance` | 23,529 | words <= 4 over `a`, `b`, `e`-acute, U+0301 |

**Result: 12,083,837 of 12,083,837 comparisons agree.** The driver also reports the
specification's value for `edit_distance` (`lev`): it equals the DP on every case.

The filename and slug exhaustive grids are exactly the grids `Bounded.lean` quantifies
over, so each bounded theorem about the *current* model is also a result about the built
library on those inputs.

### Direct sweeps (library only, no model)

| Sweep | Calls | Result |
|---|---|---|
| `sanitize_filename`, every scalar `c` in `c`, `a{c}b.txt`, `{c}.con`, `CON{c}`, `x{c}{c}y`, three platforms, P1-P9 each | 16,680,960 (x2 for P9) | POSIX: all hold. Universal and Windows: 185 each fail P8 and P9, all `{c}.con` (Finding 1) |
| `sanitize_filename`, 27 reserved names + `COM`/`LPT` with superscript 1-3 + `CONIN$`/`CONOUT$`, three casings x 5 extensions x 6 trailing strings x 8 prefixes x 4 separators x 12 `max_length` x both `preserve_extension` x 2 platforms | 9,676,800 | P8 fails through Findings 1 and 2 only (classified by mechanism); nothing else |
| `sanitize_filename`, every `max_length` boundary of 35 names | 5,700 | P9 fails (Finding 3) |
| `slugify`, every scalar alone and embedded, default path | 5,560,320 | all hold (ASCII charset, S2, S4) |
| `slugify(allow_unicode=True)`, the same, two separators | 11,120,640 | Findings 4, 10, 11 |
| `slugify`, 300,000 random inputs x random separators, `max_length`, flags; `UniqueSlugifier` sequences | 300,594 | Findings 5, 7, 9, 13 |
| `strip_log_injection`, every scalar alone, embedded and doubled x 3 replacements x `keep_tab`; every neutralized replacement | 20,017,219 | all hold (L1-L4) |
| `escape_html` / `percent_encode` (4 components), every scalar in 4 contexts, against `html.unescape` / `urllib.parse.unquote(_plus)` | 4,448,256 | all hold: round trip, ASCII, safe set, well-formed `%XX` |
| `is_suspicious_hostname`, every scalar inside a label | 1,112,064 | no bidi control and no documented invisible in `canonical`; 28 characters silently deleted (Finding 12) |
| `detect_encoding` vs `decode_to_utf8(None)` vs `decode_to_utf8(label)`, random bytes | 200,000 | agree (the #710 claim holds) |
| `edit_distance`, `nearest_match` vs a reference Levenshtein | 200,000 | all hold |

The Rust core was checked separately: `scripts/repro.rs` reproduces every finding except
Finding 9 (`UniqueSlugifier` is a binding-layer type) through the Layer-2 API at
`595fbda`, independent of the installed wheel. `cargo test --no-default-features --lib`
over the filename, slugify, log-injection, encoder, hostname and reverse modules passes at
that commit (142 passed, 2 ignored): no existing unit test there catches a finding.

## What is proved

### In general, for every input, by induction

None of these use `sorry` or `native_decide`. `Axioms.lean` shows at most `propext`,
`Quot.sound` and `Classical.choice`.

| Theorem | Statement |
|---|---|
| `Filename.sanitize_ne_nil` | P1: never empty, for every separator, `max_length`, platform, `preserve_extension` |
| `sanitize_not_dot`, `sanitize_not_dotdot` | P2: never `.` or `..` |
| `sanitize_no_leading_dot_space`, `sanitize_no_trailing_dot_space` | P6 |
| `sanitize_chars` | every output character is a separator character or passes the platform filter (not illegal, not a control, not whitespace) |
| `sanitize_legal` | P3/P4: with a separator that passes the filter, no illegal, control or whitespace character, on every platform |
| `sanitize_length` | P7: at most `max_length` when `max_length > 0` |
| `Slug.slugify_chars` | S1: every character is a separator character or an ASCII alphanumeric of the lowercased input |
| `Slug.slugify_length` | S3 |
| `Unique.run_nodup`, `runNoHint_nodup` | **Uniqueness**: the slugs one `UniqueSlugifier` returns are pairwise distinct, for every configuration and call sequence, with or without the hint |
| `Unique.runFixed_nodup` | the same for the fixed model (non-empty slugs) |
| `Enc.unescape_escape` | `escape_html` is inverted by the five-entity decoder |
| `Enc.escape_no_raw_meta` | no raw `<` `>` `"` `'` in its output |
| `Enc.pctDecode_pctEncode` | `percent_encode` is inverted by `unquote` (`unquote_plus` for `form`) on bytes |
| `Enc.pctEncode_ascii`, `pctEncode_safe` | its output is ASCII; each byte is `%`, an upper-case hex digit, `+` (form) or kept by the component; `%` is never kept |
| `Log.strip_clean`, `strip_idem` | with an accepted replacement, no neutralized character survives, and the function is idempotent |
| `Log.strip_nil_eq_filter`, `strip_length_one` | with `""`, it is `filter`; with one character, it preserves length |
| `Log.neutralizes_documented` | CR, LF, NEL, LS, PS, NUL, ESC, DEL and CSI are neutralized; TAB unless `keep_tab` |

### Bounded exhaustively (`Bounded.lean`, `native_decide`)

| Theorem | Grid (cases) | Result |
|---|---|---|
| `current_filename_default_sep` | the filename grid above (8,503,040) | with separator `_` and no truncation, P1-P8 fail **only** where the stem sanitized to nothing: Finding 1 is the only way in |
| `fixed_filename_safe` | the same | the fixed model meets P1-P8 everywhere |
| `fixed_filename_idem` | the same | without truncation, the fixed model is idempotent; the current model fails P9 on 3,872 of those cases and on 278,931 of all 8,503,040 |
| `current_slug_shape_single_char` | the slug grid, separators `-` `.` (2,090,144) | S2 (no leading, trailing or doubled separator) and S5 hold for one-character separators |
| `fixed_slug_shape` | separators `-` `.` `--` `-_` (4,180,288) | the fixed model meets S2 for multi-character separators too (the current model fails 57,060) |
| `fixed_slug_stopwords` | the same | the fixed model leaves no stopword, case-insensitively |
| `unique_hint_is_sound` | every call sequence <= 4 over five texts x 2 separators x `max_length` 0-6 (10,934) | the per-base hint (#242) changes no output |
| `fixed_unique_shape` | the same | every non-empty slug of the fixed model meets S2 and S3 (the current model fails 2,902) |
| `dp_eq_lev` | all pairs of words <= 4 over `a b c` (14,641) | the DP is the Levenshtein distance |

`Vectors.lean` replays 54 documented examples on the models (all ASCII examples with an
exact expected value in `docs/user-guide/filenames.md`, `docs/limitations.md`, the
docstrings, and the Rust unit tests of these modules). All pass.

## Findings

**Status of the slug findings.** 4, 5, 6, 7, 8, 9, 10, 11 and 13 are fixed by #PR, with
regression tests in `tests/slugify_formal_findings.rs`, `src/slugify.rs` and
`tests/test_slugify_formal_findings.py`. `Slug.lean` and `Unique.lean` still model the
code at `595fbda`, so the differential test now disagrees with the library on those
inputs. `build_unique_candidate` moved from `src/py/slugify.rs` into the core, as
`unique_slug_candidate` in `src/slugify.rs`. The shipped fixes follow `slugifyFixed` and `runFixed`, except: stopwords match
case-insensitively with `lowercase=False` too (the model lowercases them only under
`lowercase`); the `UniqueSlugifier` head is cut on a cluster boundary and cleaned of
joiners under `allow_unicode`, as well as of a partial separator; an empty slug is
returned without consulting `check`; and Finding 11 is fixed in the documentation, which
now says a precomposed base's own marks count toward the cap.

Numbered as in `scripts/repro.py`, listed by severity. Each has a reproduction in
`scripts/repro.py` (Python) and, except Finding 9, `scripts/repro.rs` (Rust core); the
model-level ones (1, 2, 3, 5-9) are also kernel-checked in `Findings.lean`. Outputs below
are copied from `repro.py`. Classes: (a) code bug, (b) doc overclaim, (c) inconsistency.

### Finding 1 (a): a stem that sanitizes to nothing leaves a reserved device name as the whole filename

**Severity: medium.** The universal and Windows modes promise the output is never a
Windows device name; on the bounded grid with the default separator and no truncation this
is the only way to get one (`current_filename_default_sep`). Any first part that
sanitizes away works: an illegal
character, a separator, a space, `../`, a control, a zero-width character.

```python
>>> import disarm
>>> [disarm.sanitize_filename(t) for t in ["_.con", "*.con", " .nul", "/.aux", "../.con", "\x00.com1", "?.LPT1"]]
['con', 'con', 'nul', 'aux', 'con', 'com1', 'LPT1']
>>> disarm.sanitize_filename("*.NUL", platform="windows")
'NUL'
>>> disarm.sanitize_filename("con")        # and the output is not a fixed point
'_con'
```

On Windows, opening `nul`, `con`, `aux`, `com1` or `lpt1` opens the device: a write to
`nul` succeeds and discards the data, `con` blocks on the console, `com1` and `lpt1` go to
a port. The sweep finds 185 single characters `c` for which `c + ".con"` does this.

**Root cause.** `src/filename.rs` L257-265 split `"*.con"` into stem `"*"` and extension
`".con"`. The stem sanitizes to `""` (L268-310), so the reserved check at L326 reads `""`,
and the post-truncation check at L357-361 reads the part of `".con"` before its first dot,
also `""`. `finalize_name` (L169-178) then trims the leading dot, after both checks.

**Fix.** After L310, when `result` is empty and there is an extension, the extension *is*
the name: move `ext[1..]` into `result` and drop the extension, before L326 (`sanitizeFixed`
fix 1; `fixed_filename_safe`). Moving the reserved checks after `finalize_name` (fix 2)
also closes it.

### Finding 2 (a): the separator is not validated; a space separator hides a reserved name from the check

**Severity: low to medium** (the separator is a caller argument, but `" "` is a natural
choice for readable names, and `replacement_text` is the pathvalidate-compatible alias).

```python
>>> disarm.sanitize_filename("con _", separator=" ", max_length=4, preserve_extension=False)
'con'
>>> disarm.sanitize_filename("AUX .txt", separator=" ", preserve_extension=False)
'AUX .txt'
>>> disarm.sanitize_filename("../etc/passwd", separator="/")
'/etc/passwd'
>>> disarm.sanitize_filename("a b", separator="\x00")
'a\x00b'
```

The first is a bare `con`. In the second the post-truncation check compares `"AUX "` with
the device list; Win32 strips trailing spaces before the extension when it matches device
names (see *Not confirmed*), so Windows reads `AUX`. The last two put a path separator or
NUL, which the function exists to remove, into the name. `strip_log_injection` already
rejects a replacement that contains what it neutralizes (`validate_log_replacement`,
`src/log_injection.rs` L80-93); `sanitize_filename` has no counterpart.

**Root cause.** `src/filename.rs` L180-202 validate `platform` and `lang`, not `separator`;
L274 inserts it. L357-360 take the first-dot stem without trimming spaces, and run before
`finalize_name` (L374) trims the name, so a truncation that ends in the separator (`"con "`)
passes the check and is trimmed afterwards.

**Fix.** Reject a separator containing a character the platform treats as illegal or
control (`InvalidArgument`, like `invalid_log_replacement`), and run the last reserved
check after `finalize_name`, on the stem Windows reads: before the first dot, trailing
spaces removed (`sanitizeFixed` fix 2; `winStem`).

### Finding 3 (a): outputs that are not fixed points

**Severity: low.** #487 made "a sanitized name is a fixed point" a criterion and #570 fixed
one way it failed ("two systems that sanitize a different number of times derived
different names from one input"). Four more remain, with default arguments in the first:

```python
>>> f = disarm.sanitize_filename
>>> f("_.x.*"), f(f("_.x.*"))                                   # extension cleans to "."
('_.x', 'x')
>>> f("ab_cd", max_length=3, preserve_extension=False), f("ab_", max_length=3, preserve_extension=False)
('ab_', 'ab')
>>> f("a.bcd.txt", max_length=6), f("a..txt", max_length=6)     # ".." in the output
('a..txt', 'a.txt')
>>> f("a. .b", separator="", preserve_extension=False)           # ".." again
'a..b'
>>> f(". ./", separator="-", preserve_extension=False), f("-", separator="-", preserve_extension=False)
('-', '_')
```

**Root causes** (`src/filename.rs`). (1) L314-323 can clean an extension to a bare `"."`,
which `finalize_name` (L170) drops, so the next call splits at an earlier dot: #570's
problem through another door. (2) `apply_max_length` (L346-352) cuts the stem after the
L284-310 strips, so a cut can end in the separator or a dot, next to the extension's dot.
(3) The dot collapse (L210, L227) runs before the stem loop deletes whitespace, which an
empty separator turns into adjacent dots. (4) L284-286 strip trailing separators, then
L300-310 trailing dots, once each, so `"-.-"`-shaped tails keep a separator. The docs'
pipeline (`docs/user-guide/filenames.md`, step 7: "Strip leading/trailing separators and
dots") also overclaims: leading separators are never stripped (`f(". x") == "_x"`).

**Fix.** `sanitizeFixed` fixes 3 and 4: collapse dots again after the stem loop; trim the
stem's tail of separators, dots and spaces together, before and after truncation; and
re-split when the extension cleans to `"."`. `fixed_filename_idem` checks the result
without truncation. With truncation the fix is incomplete: 100 of the 8,503,040 grid cases
stay non-idempotent in the fixed model (against 278,931 in the current one); the first,
`"_.*.*"` on POSIX with `max_length=3`, is a stem made only of a separator before a
POSIX-legal extension. That part is left open.

### Finding 12 (c): the hostname screen passes 28 characters that UTS #46 deletes

**Severity: low.** `is_suspicious_hostname` folds `compat_fold` into the verdict because
"`\uff45vil.com` is absent from a blocked set, screens clean, and resolves to `evil.com`"
(#709). The same holds for every default-ignorable code point outside the
`has_invisible` classes: the UTS #46 mapping deletes it, `canonical` is `evil.com`, and
nothing is flagged.

```python
>>> [disarm.is_suspicious_hostname(h)[0] for h in ["e\u00advil.com", "e\u115fvil.com", "e\u034fvil.com", "e\u180bvil.com", "e\U0001bca0vil.com"]]
[False, False, False, False, False]
>>> [disarm.is_suspicious_hostname(h)[1].canonical for h in ["e\u00advil.com", "e\u115fvil.com"]]
['evil.com', 'evil.com']
>>> [disarm.has_anomalies(h) for h in ["e\u115fvil.com", "e\u180bvil.com", "e\U0001bca0vil.com"]]
[True, True, True]
```

The full list from the sweep: U+00AD, U+034F, U+115F, U+1160, U+17B4, U+17B5,
U+180B-U+180D, U+180F, U+206A-U+206F, U+1BCA0-U+1BCA3, U+1D173-U+1D17A. Three of them the
library's own anomaly detector calls anomalous for the same string.

**Root cause.** `src/hostname.rs` L23-29 (`is_invisible_in_hostname`) is the zero-width,
tag, variation-selector, noncharacter and private-use classes; `idna::domain_to_unicode`
(L354) then deletes these 28 silently.

**Fix.** Flag a label whose UTS #46 mapping deleted a code point, or add
`Default_Ignorable_Code_Point` to `is_invisible_in_hostname`, and document it beside
`has_invisible`.

### Finding 14 (a): an explicit encoding is overridden by a byte-order mark, and `strict` does not notice

**Severity: low to medium.** The docs tell callers to "prefer explicit encoding metadata
over auto-detection". An explicit encoding is not what is used when the bytes start with a
BOM:

```python
>>> disarm.decode_to_utf8(b"\xfe\xff\x00A", "utf-8", strict=True)
('A', False)
>>> disarm.decode_to_utf8(b"\xff\xfeA\x00B\x00", "iso-8859-1")
('AB', False)
```

`FE FF 00 41` is not valid UTF-8, and `strict=True` exists to turn a lossy decode into an
error; instead the bytes are decoded as UTF-16BE, silently. A caller that validates "this
upload is UTF-8" accepts UTF-16, and one that decodes with a declared single-byte charset
gets a different string than any other decoder given the same declaration.

**Root cause.** `src/encoding.rs` L202 calls `Encoding::decode`, which performs WHATWG BOM
sniffing and lets a BOM override the encoding, on the explicit path too.

**Fix.** On the explicit path use `decode_with_bom_removal` (removes only a BOM of the
given encoding) or `decode_without_bom_handling`; keep `decode` for auto-detection, where
#710 relies on it.

### Finding 4 (b): `allow_unicode` keeps 130 symbols

**Severity: low.** Both docstrings (Python and `SlugConfig::allow_unicode`) and the #712
comment at `src/slugify.rs` L103-115 say `allow_unicode` keeps `L* | N* | M*` and that
symbols become separators. 130 `So` characters are kept: the circled Latin letters
U+24B6-U+24E9 and the squared / negative circled / negative squared Latin capitals
U+1F130-U+1F189.

```python
>>> disarm.slugify("\u24b6dmin", allow_unicode=True)
'\u24d0dmin'
```

A slug is an identifier; `\u24d0dmin` is not `admin` but renders close to it.

**Root cause.** `char::is_alphanumeric` (L117, and the first disjunct at L708) is the
`Alphabetic` property, which includes these through `Other_Alphabetic`.

**Fix.** Test the general category (L/N/M), not `Alphabetic`, or document the exception.

### Finding 13 (a): a truncated `allow_unicode` slug can end in ZWJ or ZWNJ

**Severity: low.** #711's purpose was that truncation never leaves "a slug ending in a bare
zero-width joiner"; #712 says joiners are "never emitted at the start or end of a token".

```python
>>> disarm.slugify("a\u200db", allow_unicode=True, max_length=4)
'a\u200d'
>>> disarm.slugify("a\u200cb", allow_unicode=True, max_length=4, word_boundary=True)
'a\u200c'
```

**Root cause.** Grapheme rule GB9 attaches a joiner to the character before it, so
`floor_grapheme_boundary` (`src/slugify.rs` L149-162) keeps `a` + ZWJ as one cluster, and
nothing after the cut (L786-802, L859-883) removes a trailing joiner.

**Fix.** After truncation, trim trailing `SLUG_JOINERS`, then a trailing separator.

### Finding 9 (a): `UniqueSlugifier` suffixes break the slug's own shape

**Severity: low.** Uniqueness itself holds (`run_nodup`), but the suffixed candidates do
not keep the invariants every plain slug keeps:

```python
>>> u = disarm.UniqueSlugifier(max_length=5); [u("ab cd") for _ in range(3)]
['ab-cd', 'ab--1', 'ab--2']
>>> u = disarm.UniqueSlugifier(max_length=2); [u("ab") for _ in range(3)]
['ab', '-1', '-2']
>>> u = disarm.UniqueSlugifier(); [u("!!!") for _ in range(3)]
['', '-1', '-2']
>>> u = disarm.UniqueSlugifier(max_length=13, allow_unicode=True); [u("a\u0915\u094d\u200d\u0937") for _ in range(2)]
['a\u0915\u094d\u200d\u0937', 'a\u0915\u094d\u200d-1']
```

A doubled separator, a leading separator with the base gone (every base shares the `-1`,
`-2`, ... namespace), and a token ending in ZWJ with its cluster split, which is Finding
13's defect again and what #711 set out to prevent.

**Root cause.** `src/py/slugify.rs` L316-324 cut the base with `floor_char_boundary` and
append the suffix, with no trailing-separator or joiner strip and no cluster boundary;
L307-313 return the suffix alone when it does not fit.

**Fix.** Cut the head with the slug's own truncation (cluster boundary under
`allow_unicode`, then strip a trailing partial separator and joiners); require at least
one base character (`min_unique_len = sep.len() + 2`); do not suffix an empty base
(`Unique.runFixed`; `fixed_unique_shape`, `runFixed_nodup`).

### Finding 10 (a): `allow_unicode` slugs are not NFC when lowercasing makes a composable pair

**Severity: low.** #477 composes on the `allow_unicode` path so that decomposed and
precomposed spellings give one slug. Composition runs before lowercasing, and lowercasing
can create a pair that composes:

```python
>>> disarm.slugify("T\u0308", allow_unicode=True), disarm.slugify("\u1e97", allow_unicode=True)
('t\u0308', '\u1e97')
>>> disarm.slugify("t\u0308", allow_unicode=True)
'\u1e97'
```

Two slugs that render identically for one text, and an output that is not a fixed point.
With six common marks, 33 upper-case letters do this (`T`, Greek capitals with
perispomeni, psili, ypogegrammeni, ...).

**Root cause.** `src/slugify.rs` L616-629 (compose) precede L648-666 (lowercase).

**Fix.** Compose after lowercasing on the `allow_unicode` path.

### Finding 5 (c): plain truncation leaves a partial multi-character separator

**Severity: low.** `truncate_at_boundary` strips a trailing partial separator (review M-C1,
L881); the plain branch does not.

```python
>>> disarm.slugify("a b", separator="-_", max_length=2), disarm.slugify("a b", separator="-_", max_length=2, word_boundary=True)
('a-', 'a')
```

python-slugify strips it (`string[:max_length].strip(separator)`).
**Root cause:** `src/slugify.rs` L797-800 remove only a whole separator. **Fix:** call
`strip_trailing_separator_prefix` there (`slugifyFixed`; `fixed_slug_shape`).

### Finding 6 (c): `word_boundary` drops a whole word it had room for

**Severity: low.**

```python
>>> disarm.slugify("very long title here", max_length=9, word_boundary=True)
'very'
```

`very-long` is 9 bytes and ends on a word; python-slugify, whose parameters the docstring
says "port directly", returns it. **Root cause:** L873-876 search for a separator inside
the cut even when the cut lands exactly on one. **Fix:** keep the cut when
`slug[boundary..]` starts with the separator (`truncWordFixed`).

### Finding 7 (b): stopwords are not case-insensitive

**Severity: low.** `SlugConfig::stopwords` and `with_stopwords` say "case-insensitive"
(`src/slugify.rs` L293, L446); python-slugify lowercases stopwords when `lowercase=True`.

```python
>>> disarm.slugify("The Fox", stopwords=["The"])
'the-fox'
```

**Root cause:** the stop set is built verbatim (L777; `_slugify_batch` L146 and `_Slugifier` L247 in
`src/py/slugify.rs`) and compared with the lowercased slug. **Fix:** lowercase the
stopwords when `lowercase` is set.

### Finding 8 (a): with an empty separator, stopwords are removed character by character

**Severity: low.**

```python
>>> disarm.slugify("abc", separator="", stopwords=["b"])
'ac'
```

**Root cause:** `slug.split("")` (L821, L841) yields single characters. **Fix:** skip
stopword filtering when the separator is empty (there are no words), or filter the tokens
before they are joined.

### Finding 15 (b): "the sanitizer will not manufacture a `%`" holds only while the input has none

**Severity: informational.** The `sanitize_filename` docstring says the rule "is now exact:
`%` never appears in the output unless it appeared in the input", which is literally true,
and also that "what the sanitizer will not do is manufacture one", which is not: one typed
`%` lets every manufactured one through.

```python
>>> disarm.sanitize_filename("%\uff05\uff12\uff25\uff05\uff12\uff25\uff05\uff12\uff26etc.txt")
'%%2E%2E%2Fetc.txt'
```

A caller who can type `%` can also type `%2E%2E%2F`, so this adds no capability.
**Root cause:** `src/filename.rs` L62 tests `raw_input.contains('%')` once for the whole
string. **Fix:** reword the docstring, or neutralize `%` characters in excess of the
input's count.

### Finding 11 (b): the combining-mark cap is not "two per base" for precomposed bases

**Severity: informational.** The `allow_unicode` docs say marks are "capped at two per base
character", and the comment at L731-735 says 30 stacked marks "must not come back as
three". A precomposed base that already carries three (243 characters, e.g. U+1F82) is
kept whole:

```python
>>> import unicodedata
>>> sum(unicodedata.combining(c) > 0 for c in unicodedata.normalize("NFD", disarm.slugify("\u1f82", allow_unicode=True)))
3
```

This is the right behaviour for polytonic Greek; the docs should say "at most two
*added* marks, or the base's own if it has more".

## Not confirmed, and checked-not-a-bug

* **Windows reads `"AUX .txt"` as `AUX`.** Finding 2's second example relies on
  `RtlIsDosDeviceName_U` stripping spaces before the extension (as the ReactOS
  implementation does); it was not run on Windows here. The other examples of Findings 1
  and 2 are exact device names and need no such assumption.
* **`CONIN$` and `CONOUT$`** are not in `WINDOWS_RESERVED`. Microsoft's naming page does not
  list them, and disarm does not claim them.
* **`COM` and `LPT` with superscript 1-3** (which Microsoft does list) are transliterated to
  digits and prefixed: checked in the reserved sweep.
* **A fullwidth IPv6 literal** (`"\uff3b::1\uff3d"`) screens clean with `compat_fold=False`
  and `canonical == "[::1]"`. IP literals are not labels, so the per-label rule does not
  apply as written; WHATWG URL parsing rejects that host, so no live bypass was found.
* **`strip_log_injection` passes bidi controls, zero-width characters, U+FEFF and U+00AD.**
  Nothing in its docs or `THREAT_MODEL.md` claims otherwise; recorded as a scope note.
* **`slugify` is not idempotent in general** (truncation can cut a word down to a stopword;
  python-slugify does the same). Only "a valid slug is unchanged" is claimed, and holds.
* **The per-base hint** (#242) changes no output on the bounded grid
  (`unique_hint_is_sound`), with a small `MAX_UNIQUE_ATTEMPTS`. Beyond it, the only way
  the two walks could differ is the error *kind* once the hint passes 10,000, which needs
  a `lossy` candidate to be consumed; a lossy candidate is the suffix of an earlier
  counter, already in `seen`, so this should not arise. Argued, not proved.
* **25 visible format characters** (U+0600-U+0605, U+06DD, ...) survive into a hostname's
  `canonical`, but every such hostname is flagged suspicious, and they are outside the
  documented classes.

## Re-running

```bash
export PATH=/path/to/lean-4.34.0/bin:$PATH
cd formal/lean/Sanitizers
lake build                               # every proof; about 2 minutes from clean, 1.5 of them Bounded.lean
lake env lean Sanitizers/Axioms.lean     # the axiom audit
lake exe explore 5                       # grid failure counts and first counterexamples (about 6 minutes)
python3 scripts/difftest.py              # needs an importable `disarm`
python3 scripts/repro.py                 # every finding; exit status = number not reproduced
python3 scripts/sweep_filename.py        # the direct sweeps (minutes each)
python3 scripts/sweep_slug.py
python3 scripts/sweep_misc.py
```
