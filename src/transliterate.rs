use std::borrow::Cow;
use std::collections::HashMap;
use unicode_normalization::UnicodeNormalization;

use crate::tables;
use crate::unicode_ranges as ur;
use crate::ErrorMode;

// Resource limits are centralized in `crate::limits` (#256).
use crate::limits::{MAX_CAPACITY_HINT, MAX_REPLACEMENT_OUTPUT_BYTES};

/// Apply the global replacement pre-pass under the output-size bound, mapping an
/// amplification overflow to the canonical `ErrorRepr::ReplacementOutputTooLarge`.
///
/// Single source for the cap + error construction shared by every transliterate
/// entrypoint (#251); previously duplicated at four sites. On the PyO3 paths the
/// call-site `?` converts the `ErrorRepr` to a `PyErr` (#181).
pub(crate) fn apply_replacements_bounded(text: &str) -> Result<Cow<'_, str>, crate::ErrorRepr> {
    tables::apply_replacements(text, MAX_REPLACEMENT_OUTPUT_BYTES).map_err(|size| {
        // #208: WARN with sizes only (a resource-limit hit), never the text.
        tl_warn!("replacement output too large: size={size} max={MAX_REPLACEMENT_OUTPUT_BYTES}");
        crate::ErrorRepr::ReplacementOutputTooLarge {
            size,
            max: MAX_REPLACEMENT_OUTPUT_BYTES,
        }
    })
}

/// Validate a `lang` argument eagerly (#68).
///
/// An unknown code (typo like `"RU"` or `"russian"`) would otherwise silently
/// fall back to the default tables and produce quietly-wrong output — unlike
/// `errors=`/`form=`, which reject bad values. Returns an error listing the
/// valid codes. The special `"auto"` detection mode, the BCP-47 aliases
/// (`nb`/`nn`/`da`), and any `register_lang()` additions are also accepted.
pub(crate) fn validate_lang(lang: Option<&str>) -> Result<(), crate::ErrorRepr> {
    if let Some(l) = lang {
        if l != "auto" && !tables::is_valid_lang(l) {
            // `list_langs()` already includes any `register_lang()` codes, so
            // we only need to call out the extras it omits: the "auto" mode and
            // the BCP-47 aliases accepted by `is_valid_lang`.
            let valid = tables::list_langs();
            // "did you mean …?" hint against the valid codes + accepted aliases (#186).
            let suggestion = crate::utils::closest_match(
                l,
                valid
                    .iter()
                    .map(String::as_str)
                    .chain(["auto", "nb", "nn", "da"]),
            )
            .map(|s| format!(" (did you mean '{s}'?)"))
            .unwrap_or_default();
            return Err(crate::ErrorRepr::UnknownLang {
                got: l.to_owned(),
                suggestion,
                valid: valid.join(", "),
            });
        }
    }
    Ok(())
}

/// Script class for tracking inter-script word spacing.
///
/// Used to determine whether a space separator should be inserted between
/// adjacent transliterated characters (e.g. between consecutive CJK ideographs,
/// but not between consecutive kana).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ScriptClass {
    /// Start-of-string or no character yet.
    None,
    /// CJK Unified Ideograph (Han character).
    Ideograph,
    /// Hangul syllable or jamo.
    Hangul,
    /// Hiragana or Katakana.
    Kana,
    /// ASCII / Latin character.
    Latin,
    /// Indic Brahmic scripts (Devanagari, Bengali, Tamil, etc.).
    Indic,
    /// Any other script (Cyrillic, Arabic, etc.).
    Other,
}

/// `errors="strict"` (#184): raise [`crate::ErrorRepr::Untranslatable`] on the first
/// character with no transliteration; otherwise return the transliteration
/// (which is identical under any error mode when nothing is unmapped). `text` is
/// already post-replacement, so reported offsets are relative to that.
pub(crate) fn transliterate_strict(
    text: &str,
    lang: Option<&str>,
    strict_iso9: bool,
    gost7034: bool,
    tones: bool,
) -> Result<String, crate::ErrorRepr> {
    // #240: single pass with early exit. The former implementation ran the
    // engine twice — once via `find_untranslatable_impl` (which materialised the
    // *complete* Vec of every unmapped char just to read the first) and again to
    // transliterate — so O(u) space and 2× time. Here one pass builds the result
    // while collecting the FIRST untranslatable character and stopping there
    // (`stop_on_first`): on success `result` IS the transliteration (no second
    // pass); on the first offender the partial result is abandoned and reported.
    let mut first: Vec<(char, usize)> = Vec::new();
    let result = transliterate_impl_inner(
        text,
        lang,
        ErrorMode::Ignore,
        "",
        strict_iso9,
        gost7034,
        tones,
        Some(&mut first),
        true, // stop at the first untranslatable character
    );
    if let Some((ch, byte_offset)) = first.into_iter().next() {
        return Err(crate::ErrorRepr::Untranslatable { ch, byte_offset });
    }
    Ok(result.into_owned())
}

/// Validate the *combination* of `transliterate()` keyword arguments (#231).
///
/// The semantic conflict matrix lives in the core (the single source of truth)
/// rather than only in the `python/disarm/_api.py` wrapper, so a second
/// binding enforces the identical contract by calling this one function.
///
/// `target` selects *reverse* transliteration; `context` and `tones` are
/// *forward-only*. The individual `errors` enum value and the `strict_iso9`/
/// `gost7034` exclusivity are validated by the per-operation entrypoints; this
/// function only rejects contradictory *combinations* of otherwise-valid kwargs.
///
/// The default sentinels for `errors` (`"replace"`) and `replace_with`
/// (`"[?]"`) are the documented public-API defaults — a value other than the
/// default means the caller set a forward-only parameter explicitly.
///
/// Returns the core [`crate::ErrorRepr`] so it is unit-testable without a
/// Python interpreter; the PyO3 shim
/// `crate::py::transliterate::_validate_transliterate_args` wraps it.
pub(crate) fn validate_transliterate_args(
    lang: Option<&str>,
    target: Option<&str>,
    errors: &str,
    replace_with: &str,
    strict_iso9: bool,
    gost7034: bool,
    tones: bool,
    context: bool,
) -> Result<(), crate::ErrorRepr> {
    if target.is_some() && lang.is_some() {
        return Err(crate::ErrorRepr::LangTargetExclusive);
    }
    if context && target.is_some() {
        return Err(crate::ErrorRepr::ContextTargetExclusive);
    }
    if context && tones {
        return Err(crate::ErrorRepr::TonesWithContext);
    }
    if context && errors == "strict" {
        return Err(crate::ErrorRepr::StrictWithContext);
    }
    if target.is_some() {
        // Collect any forward-only parameter set to a non-default value. Sorted
        // so the rendered list is deterministic (matches the former Python order).
        let mut forward_only: Vec<&str> = Vec::new();
        if errors != "replace" {
            forward_only.push("errors");
        }
        if replace_with != "[?]" {
            forward_only.push("replace_with");
        }
        if strict_iso9 {
            forward_only.push("strict_iso9");
        }
        if gost7034 {
            forward_only.push("gost7034");
        }
        if tones {
            forward_only.push("tones");
        }
        if !forward_only.is_empty() {
            forward_only.sort_unstable();
            return Err(crate::ErrorRepr::ForwardOnlyWithTarget {
                names: forward_only.join(", "),
            });
        }
    }
    Ok(())
}

/// Context-aware transliteration using dictionary-based vowel restoration.
///
/// Returns an error if no context dictionary is loaded for the language.
/// Individual words that are absent from a loaded dictionary fall back to
/// context-free transliteration.
///
/// Pure Layer-1 core (#38): returns the native [`crate::ErrorRepr`]; the PyO3
/// shim `crate::py::transliterate::_transliterate_context` converts via `?`.
pub(crate) fn transliterate_context(
    text: &str,
    lang: Option<&str>,
    errors: &str,
    replace_with: &str,
    strict_iso9: bool,
    gost7034: bool,
) -> Result<String, crate::ErrorRepr> {
    // #130: Defence-in-depth — the PyO3 boundary check in each entry-point guards
    // direct Rust callers; Python callers are covered by the same check.
    if strict_iso9 && gost7034 {
        return Err(crate::ErrorRepr::MutuallyExclusiveBare);
    }
    validate_lang(lang)?;
    let error_mode = ErrorMode::parse(errors)?;
    // Global pre-transliteration replacements (no-op unless registered), applied
    // before context tokenisation so forward transliteration behaves the same
    // with and without context=True. Output of the pre-pass is bounded
    // (amplification guard); raw input size is not capped (#80).
    let text = apply_replacements_bounded(text)?;
    let text = text.as_ref();

    // #107: Try to get the appropriate context dictionary, distinguishing
    // "corrupt" (file present but malformed) from "absent" (not found).
    // Persian: try Persian dict first, fall back to Arabic (shared loanwords).
    let dict_result: Result<Option<&'static crate::context::ContextDict>, &'static str> = match lang
    {
        Some("he") => crate::context::get_hebrew_dict(),
        Some("fa") => match crate::context::get_persian_dict() {
            Ok(Some(d)) => Ok(Some(d)),
            Ok(None) => crate::context::get_arabic_dict(), // absent → try Arabic
            Err(e) => Err(e),                              // corrupt → propagate
        },
        _ => crate::context::get_arabic_dict(),
    };

    let lang_name = match lang {
        Some("he") => "Hebrew",
        Some("fa") => "Arabic/Persian",
        _ => "Arabic",
    };

    match dict_result {
        Ok(Some(d)) => {
            // Use context-aware transliteration
            let result = crate::context::transliterate_context(text, lang, d, |word, lang| {
                transliterate_impl(
                    word,
                    lang,
                    error_mode,
                    replace_with,
                    strict_iso9,
                    gost7034,
                    false,
                )
                .into_owned()
            });
            Ok(result)
        }
        Ok(None) => {
            // Dictionary not loaded — point the user at a remedy that actually works
            // (#60). Context dictionaries are not shipped in the wheel; build them
            // and expose them via DISARM_DICT_DIR.
            Err(crate::ErrorRepr::ContextDictNotFound {
                lang: lang_name.to_owned(),
            })
        }
        Err(corrupt_msg) => {
            // #107: file was found but is corrupt — different remediation from "not found".
            Err(crate::ErrorRepr::ContextDictCorrupt {
                lang: lang_name.to_owned(),
                reason: corrupt_msg.to_owned(),
            })
        }
    }
}

/// Internal transliteration implementation.
///
/// Returns `Cow::Borrowed` when the input is pure ASCII (zero allocation),
/// `Cow::Owned` otherwise.
pub(crate) fn transliterate_impl<'a>(
    text: &'a str,
    lang: Option<&str>,
    error_mode: ErrorMode,
    replace_with: &str,
    strict_iso9: bool,
    gost7034: bool,
    tones: bool,
) -> Cow<'a, str> {
    // #208: this thin wrapper is a clean boundary — the per-codepoint loop lives
    // in `_inner`, so a single completion record here never logs in the hot path.
    // The timer is cfg-gated so it costs nothing when `log` is off.
    #[cfg(feature = "log")]
    let start = std::time::Instant::now();
    let out = transliterate_impl_inner(
        text,
        lang,
        error_mode,
        replace_with,
        strict_iso9,
        gost7034,
        tones,
        None,
        false, // not strict — translate the whole input
    );
    // Metadata only — lengths/flags/duration, never the input or output text.
    tl_debug!(
        "transliterate: in_bytes={} in_chars={} out_bytes={} lang={lang:?} mode={error_mode:?} \
         iso9={strict_iso9} gost={gost7034} tones={tones} borrowed={} dur_us={}",
        text.len(),
        text.chars().count(),
        out.len(),
        matches!(out, Cow::Borrowed(_)),
        start.elapsed().as_micros(),
    );
    out
}

/// Scan `text` and return every character that has no transliteration —
/// `(char, byte_offset)` in order of appearance (#184). "No transliteration"
/// means the character reaches the unmapped branch of the engine: no table
/// entry (lang override / strict_iso9 / gost7034 / default), and no NFKC
/// recovery. Because this drives the *same* engine as `transliterate_impl`, the
/// reported set is exactly what the transform would replace/ignore/preserve, so
/// it cannot drift. ASCII characters are always translatable (identity).
pub(crate) fn find_untranslatable_impl(
    text: &str,
    lang: Option<&str>,
    strict_iso9: bool,
    gost7034: bool,
    tones: bool,
) -> Vec<(char, usize)> {
    let mut out = Vec::new();
    // The error mode is irrelevant to *which* chars are unmapped; Ignore avoids
    // building any replacement output we would discard.
    let _ = transliterate_impl_inner(
        text,
        lang,
        ErrorMode::Ignore,
        "",
        strict_iso9,
        gost7034,
        tones,
        Some(&mut out),
        false, // collect *all* untranslatable characters, not just the first
    );
    out
}

/// Inner transliteration with an optional unmapped-position collector (#184).
/// When `untranslatable` is `Some`, every character reaching the unmapped branch
/// is pushed as `(char, byte_offset)`. All public callers go through
/// `transliterate_impl` (collector `None`); `find_untranslatable_impl` passes a
/// vec.
#[allow(clippy::too_many_arguments)]
fn transliterate_impl_inner<'a>(
    text: &'a str,
    lang: Option<&str>,
    error_mode: ErrorMode,
    replace_with: &str,
    strict_iso9: bool,
    gost7034: bool,
    tones: bool,
    untranslatable: Option<&mut Vec<(char, usize)>>,
    stop_on_first: bool,
) -> Cow<'a, str> {
    // Fast path: pure ASCII input needs no transliteration (and ASCII is always
    // translatable, so the collector stays empty).
    // `str::is_ascii()` is a single SIMD-friendly scan — sub-nanosecond for
    // short strings, and it lets us skip all per-character work + allocation.
    if text.is_ascii() {
        return Cow::Borrowed(text);
    }

    // Resolve lang="auto" to detected language code.
    let resolved: Option<String>;
    let lang = if lang == Some("auto") {
        resolved = crate::scripts::resolve_auto_lang(text);
        resolved.as_deref()
    } else {
        lang
    };

    // #235 item 1+3: resolve the per-call lookup ONCE and dispatch into a
    // monomorphized loop. The built-in language override map is resolved a
    // single time (not via a ~24-arm `match lang` per character) and the
    // user-registered tables are consulted (behind the `HAS_REGISTERED_LANGS`
    // gate, so the common case never locks) only on a miss. Building the
    // mode-specific `lookup` closure *before* the loop lets `transliterate_run`
    // monomorphize into one tight loop per mode instead of re-testing the
    // loop-invariant strict/gost/lang branches for every character.
    //
    // Lookup priority within each closure:
    // 1. strict_iso9: scholarly ASCII Cyrillic table (ISO 9-style digraphs, NOT
    //    the diacritic ISO 9:1995 standard — #94) → default table.
    // 2. gost7034: GOST 7.0.34 table → default table.
    // 3. otherwise: built-in lang override → user-registered → default table.
    // `tones=true` selects toned pinyin in the default table.
    if strict_iso9 {
        transliterate_run(
            text,
            |ch| {
                tables::lookup_iso9(ch)
                    .map(Cow::Borrowed)
                    .or_else(|| default_lookup(ch, tones))
            },
            error_mode,
            replace_with,
            lang,
            strict_iso9,
            gost7034,
            tones,
            untranslatable,
            stop_on_first,
        )
    } else if gost7034 {
        transliterate_run(
            text,
            |ch| {
                tables::lookup_gost7034(ch)
                    .map(Cow::Borrowed)
                    .or_else(|| default_lookup(ch, tones))
            },
            error_mode,
            replace_with,
            lang,
            strict_iso9,
            gost7034,
            tones,
            untranslatable,
            stop_on_first,
        )
    } else {
        let builtin_lang_map = lang.and_then(tables::resolve_lang_map);
        transliterate_run(
            text,
            |ch| {
                builtin_lang_map
                    .and_then(|m| m.get(&ch).copied().map(Cow::Borrowed))
                    .or_else(|| lang.and_then(|l| tables::lookup_registered(l, ch)))
                    .or_else(|| default_lookup(ch, tones))
            },
            error_mode,
            replace_with,
            lang,
            strict_iso9,
            gost7034,
            tones,
            untranslatable,
            stop_on_first,
        )
    }
}

/// Default-table lookup, honouring the `tones` flag (toned vs toneless pinyin).
#[inline]
fn default_lookup(ch: char, tones: bool) -> Option<Cow<'static, str>> {
    if tones {
        tables::lookup_default_toned(ch).map(Cow::Borrowed)
    } else {
        tables::lookup_default(ch).map(Cow::Borrowed)
    }
}

/// Index of the first non-ASCII byte in `bytes`, or `bytes.len()` if all ASCII.
///
/// Scans eight bytes at a time, testing the high bit of each lane in one
/// `u64 & 0x8080…` (the technique `str::is_ascii` uses), then refines to the
/// exact byte (#235 item 4). Lets the transliteration loop find ASCII-run
/// boundaries far faster than a byte-by-byte check on the common ASCII-heavy
/// mixed-script input.
#[inline]
fn first_non_ascii(bytes: &[u8]) -> usize {
    const CHUNK: usize = 8;
    const HIGH_BITS: u64 = 0x8080_8080_8080_8080;
    let n = bytes.len();
    let mut i = 0;
    while i + CHUNK <= n {
        let word = u64::from_ne_bytes(
            bytes[i..i + CHUNK]
                .try_into()
                .expect("slice is exactly CHUNK bytes"),
        );
        if word & HIGH_BITS != 0 {
            break; // a non-ASCII byte lives in this chunk; pinpoint it below
        }
        i += CHUNK;
    }
    while i < n && bytes[i] < 0x80 {
        i += 1;
    }
    i
}

/// The per-character transliteration loop, generic over the resolved per-call
/// `lookup` so LLVM emits one tight, branch-lean loop per lookup mode (#235
/// item 3). `lookup` returns the primary mapping for a character (mode-specific
/// table, falling back to the default table), or `None` if unmapped.
#[allow(clippy::too_many_arguments)]
fn transliterate_run<'a, F>(
    text: &'a str,
    lookup: F,
    error_mode: ErrorMode,
    replace_with: &str,
    lang: Option<&str>,
    strict_iso9: bool,
    gost7034: bool,
    tones: bool,
    mut untranslatable: Option<&mut Vec<(char, usize)>>,
    stop_on_first: bool,
) -> Cow<'a, str>
where
    F: Fn(char) -> Option<Cow<'static, str>>,
{
    let mut result = String::with_capacity(estimate_capacity(text));
    let mut prev_class = ScriptClass::None;
    // Track last char appended to `result` — avoids O(n) `result.chars().last()` scan.
    let mut last_appended: Option<char> = None;
    // Indic virama/mātrā context: when the previous character was an Indic
    // consonant (whose table entry includes the inherent "a"), a following
    // virama or dependent vowel must strip that trailing "a" first.
    let mut last_was_indic_consonant = false;

    let bytes = text.as_bytes();
    let len = bytes.len();
    let mut i = 0;
    while i < len {
        // #235 item 4: bulk-skip ASCII runs. Scan word-at-a-time to the next
        // non-ASCII byte and copy the whole run with one `push_str` (memcpy)
        // instead of a per-character push + capacity check. The ideograph/
        // Hangul → ASCII-alnum spacing rule only depends on the run's *first*
        // character, so it is applied once at the run boundary; every later
        // character in the run has `prev_class == Latin` and never inserts a
        // space.
        if bytes[i] < 0x80 {
            let run_end = i + first_non_ascii(&bytes[i..]);
            let run = &text[i..run_end];
            last_was_indic_consonant = false;
            let first = bytes[i] as char;
            if matches!(prev_class, ScriptClass::Ideograph | ScriptClass::Hangul)
                && first.is_ascii_alphanumeric()
            {
                if let Some(last) = last_appended {
                    if last.is_alphanumeric() {
                        result.push(' ');
                    }
                }
            }
            result.push_str(run);
            // `run` is non-empty and all ASCII, so its last byte is its last char.
            last_appended = Some(bytes[run_end - 1] as char);
            prev_class = ScriptClass::Latin;
            i = run_end;
            continue;
        }

        // Non-ASCII: decode one scalar and advance `i` immediately, so the
        // mid-body `continue` on NFKC recovery cannot skip the increment.
        let ch = text[i..]
            .chars()
            .next()
            .expect("i is at a char boundary inside the string");
        let byte_offset = i;
        i += ch.len_utf8();

        let char_class = classify_char(ch);
        let is_cjk = matches!(
            char_class,
            ScriptClass::Ideograph | ScriptClass::Hangul | ScriptClass::Kana
        );

        let mut mapped: Option<Cow<'static, str>> = lookup(ch);

        // Indic virama/mātrā handling: strip the inherent "a" from the
        // previous consonant when followed by virama or a dependent vowel
        // sign.  This runs *before* the mapped/unmapped branch so that
        // virama stripping is not contingent on the character having a table
        // entry — correctness must not depend on table completeness.
        if char_class == ScriptClass::Indic {
            let role = indic_char_role(ch as u32);
            match role {
                IndicRole::Virama | IndicRole::DependentVowel if last_was_indic_consonant => {
                    // Pop the trailing inherent 'a' from the previous consonant.
                    if result.ends_with('a') {
                        result.pop();
                    }
                    last_was_indic_consonant = false;
                    // Correctness must not depend on table completeness (see the
                    // comment above). A virama (and, defensively, a dependent
                    // vowel) absent from the tables must still be *consumed* like
                    // the empty mapping a complete table would carry — otherwise
                    // release builds fall through to the error handler and emit it
                    // as `replace_with` / preserve the raw mark: silent output
                    // corruption for any script whose virama is missing (#200).
                    // Debug builds previously only `debug_assert!`'d this; promote
                    // it to a runtime fallback so debug and release agree.
                    if mapped.is_none() {
                        mapped = Some(Cow::Borrowed(""));
                    }
                }
                IndicRole::Consonant => {
                    last_was_indic_consonant = true;
                }
                _ => {
                    last_was_indic_consonant = false;
                }
            }
        } else {
            last_was_indic_consonant = false;
        }

        // An empty-string mapping means "this character has no ASCII
        // representation — drop it."  In preserve mode, honour the user's
        // request to keep the original character instead of silently
        // discarding it.
        let is_mapped = match mapped.as_deref() {
            Some(s) if !s.is_empty() => true,
            Some(_) => error_mode != ErrorMode::Preserve, // empty → preserve keeps original
            None => false,
        };

        if is_mapped {
            let s = mapped.as_deref().unwrap();
            if is_cjk && prev_class != ScriptClass::None && needs_cjk_space(prev_class, char_class)
            {
                if let Some(last) = last_appended {
                    if last.is_alphanumeric() {
                        result.push(' ');
                        last_appended = Some(' ');
                    }
                }
            }
            result.push_str(s);
            // Track last char of the appended transliteration string
            if let Some(c) = s.chars().next_back() {
                last_appended = Some(c);
            }
            prev_class = char_class;
        } else {
            // Cold path (#235 item 5): NFKC recovery + error handling are rare
            // relative to the mapped path, so they live in a `#[cold]`/
            // `#[inline(never)]` helper to keep the common loop body in the µop
            // cache.
            let genuinely_untranslatable = handle_unmapped(
                ch,
                byte_offset,
                &mut result,
                &mut last_appended,
                &mut prev_class,
                untranslatable.as_deref_mut(),
                lang,
                error_mode,
                replace_with,
                strict_iso9,
                gost7034,
                tones,
            );
            // #240: strict mode stops at the first untranslatable character —
            // single pass, O(1) extra space. The partial `result` is discarded
            // by the caller (it returns an error in that case).
            if stop_on_first && genuinely_untranslatable {
                break;
            }
        }
    }

    Cow::Owned(result)
}

/// Handle a character with no table mapping: attempt NFKC compatibility
/// recovery, otherwise apply the error mode. Split out and marked `#[cold]` so
/// the hot mapped path stays tight (#235 item 5).
///
/// Returns `true` when the character is **genuinely untranslatable** (no table
/// entry and no NFKC recovery — the single point that defines the untranslatable
/// set, #184), `false` when NFKC recovery handled it. The caller uses this to
/// early-exit the strict single-pass on the first offender (#240).
#[cold]
#[inline(never)]
#[allow(clippy::too_many_arguments)]
fn handle_unmapped(
    ch: char,
    byte_offset: usize,
    result: &mut String,
    last_appended: &mut Option<char>,
    prev_class: &mut ScriptClass,
    mut untranslatable: Option<&mut Vec<(char, usize)>>,
    lang: Option<&str>,
    error_mode: ErrorMode,
    replace_with: &str,
    strict_iso9: bool,
    gost7034: bool,
    tones: bool,
) -> bool {
    // #81: before the error fallback, try NFKC compatibility decomposition.
    // Mathematical Alphanumerics (𝕳→H) and presentation ligatures (ﬁ→fi) are
    // pure-Latin content NFKC folds to ASCII — both unidecode and anyascii
    // recover them, and they are a real filter-evasion vector. A char whose NFKC
    // form is itself falls straight through to the error handler below.
    //
    // #235 item 6: single-scalar NFKC is bounded (≤18 scalars, U+FDFA), so encode
    // it into a small stack buffer instead of allocating a heap `String` per
    // unmapped char. The heap fallback only triggers on the Unicode-impossible
    // case of the expansion overflowing the buffer.
    const NFKC_STACK_BYTES: usize = 80; // ≥ 18 scalars × 4 bytes
    let mut buf = [0u8; NFKC_STACK_BYTES];
    let mut blen = 0usize;
    let mut overflow = false;
    for d in ch.nfkc() {
        if blen + d.len_utf8() > buf.len() {
            overflow = true;
            break;
        }
        blen += d.encode_utf8(&mut buf[blen..]).len();
    }
    let heap: String;
    let decomposed: &str = if overflow {
        heap = ch.nfkc().collect();
        heap.as_str()
    } else {
        std::str::from_utf8(&buf[..blen]).expect("nfkc output is valid utf8")
    };

    // #110: derive nfkc_unchanged by comparing the decomposition against the
    // original char, avoiding a second decomposition pass.
    let nfkc_unchanged = decomposed.len() == ch.len_utf8() && decomposed.starts_with(ch);
    if !nfkc_unchanged {
        let sub = transliterate_impl(
            decomposed,
            lang,
            error_mode,
            replace_with,
            strict_iso9,
            gost7034,
            tones,
        );
        if !sub.is_empty() {
            result.push_str(&sub);
            *last_appended = sub.chars().next_back();
            *prev_class = ScriptClass::Latin;
            return false; // NFKC-recovered → translatable
        }
    }

    // The character is genuinely untranslatable (no table entry, no NFKC
    // recovery): this is the single point that defines the set (#184).
    if let Some(v) = untranslatable.as_mut() {
        v.push((ch, byte_offset));
    }
    match error_mode {
        ErrorMode::Replace => {
            // An empty replace_with is intentionally equivalent to
            // ErrorMode::Ignore — the char is silently dropped. This matches
            // Unidecode's default behaviour and is used by the unidecode() shim.
            result.push_str(replace_with);
            *last_appended = replace_with.chars().next_back();
        }
        ErrorMode::Ignore => {}
        ErrorMode::Preserve => {
            result.push(ch);
            *last_appended = Some(ch);
        }
    }
    *prev_class = ScriptClass::Other;
    true // genuinely untranslatable
}

/// Number of leading characters sampled to estimate output expansion.
///
/// Bounds the scan so a multi-megabyte input is not walked end-to-end just to
/// size a buffer (#235 item 8): the old `filter(!is_ascii).take(5)` traversed
/// the *entire* string whenever it held fewer than five non-ASCII characters.
const CAPACITY_SAMPLE_CHARS: usize = 256;
/// Extra output bytes reserved per expanding (CJK/Hangul) input byte: each such
/// character romanizes to a multi-letter syllable plus a separator (~4× total).
const CJK_EXTRA_BYTES_PER_BYTE: usize = 3;

fn estimate_capacity(text: &str) -> usize {
    // Sample a bounded prefix and measure what fraction of it is CJK/Hangul,
    // which expand ~4× to pinyin/romaji syllables; everything else is ~1:1.
    // We then weight the reservation by that *sampled fraction* rather than
    // applying 4× to the whole length, so "Hello 北京" followed by megabytes of
    // ASCII no longer reserves 4× the input (#235 item 8). Capacity-only — an
    // under-estimate just costs at most one reallocation, never wrong output.
    let mut sampled = 0usize;
    let mut expanding = 0usize;
    for c in text.chars().take(CAPACITY_SAMPLE_CHARS) {
        sampled += 1;
        let cp = c as u32;
        if ur::CJK_CAPACITY_RANGE.contains(&cp)
            || ur::HANGUL_SYLLABLES.contains(&cp)
            || ur::CJK_COMPAT.contains(&cp)
        {
            expanding += 1;
        }
    }
    if expanding == 0 {
        return text.len().min(MAX_CAPACITY_HINT);
    }
    // extra ≈ len × (expanding/sampled) × 3. Pure-CJK input still reserves ~4×
    // (expanding == sampled); sparse CJK reserves close to 1×.
    let extra = text
        .len()
        .saturating_mul(CJK_EXTRA_BYTES_PER_BYTE)
        .saturating_mul(expanding)
        / sampled.max(1);
    text.len().saturating_add(extra).min(MAX_CAPACITY_HINT)
}

/// Lowest / highest code point any `classify_char` script range covers
/// (`INDIC.start()` … `KATAKANA_HALFWIDTH.end()`). A code point outside
/// `[CLASSIFY_LO, CLASSIFY_HI]` is `Other` with no table probe — one comparison
/// pair replaces the whole range-check tree for the common Latin-supplement,
/// punctuation, and SMP input that dominates real text (#235 item 2).
const CLASSIFY_LO: u32 = *ur::INDIC.start();
const CLASSIFY_HI: u32 = *ur::KATAKANA_HALFWIDTH.end();

/// Per-256-codepoint-block script class, indexed by `cp >> 8`. A block that
/// holds more than one class (e.g. 0x30xx: Kana + Hangul-compat-jamo;
/// 0xFFxx: half-width Kana + Other) is `Mixed` and defers to the range chain.
#[derive(Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
enum BlockClass {
    Other,
    Ideograph,
    Hangul,
    Kana,
    Indic,
    Mixed,
}

const fn in_r(cp: u32, r: &std::ops::RangeInclusive<u32>) -> bool {
    cp >= *r.start() && cp <= *r.end()
}

/// `classify_char`, as a `const fn` over a raw code point, so [`BLOCK_CLASS`] is
/// generated at compile time from the **same** range constants the runtime
/// chain (`is_cjk_ideograph` … `is_indic`) uses. The two therefore cannot drift;
/// the exhaustive `classify_char_matches_slow` test enforces it regardless.
const fn class_of_cp_const(cp: u32) -> BlockClass {
    if in_r(cp, &ur::CJK_UNIFIED) || in_r(cp, &ur::CJK_EXT_A) || in_r(cp, &ur::CJK_COMPAT) {
        BlockClass::Ideograph
    } else if in_r(cp, &ur::HANGUL_SYLLABLES) || in_r(cp, &ur::HANGUL_COMPAT_JAMO) {
        BlockClass::Hangul
    } else if in_r(cp, &ur::HIRAGANA)
        || in_r(cp, &ur::KATAKANA)
        || in_r(cp, &ur::KATAKANA_HALFWIDTH)
    {
        BlockClass::Kana
    } else if in_r(cp, &ur::INDIC)
        || in_r(cp, &ur::TIBETAN)
        || in_r(cp, &ur::MYANMAR)
        || in_r(cp, &ur::KHMER)
        || in_r(cp, &ur::BALINESE)
        || in_r(cp, &ur::JAVANESE)
        || in_r(cp, &ur::SUNDANESE)
        || in_r(cp, &ur::TAI_THAM)
        || in_r(cp, &ur::CHAM)
        || in_r(cp, &ur::BATAK)
        || in_r(cp, &ur::BUGINESE)
        || in_r(cp, &ur::TAGALOG)
        || in_r(cp, &ur::HANUNOO)
        || in_r(cp, &ur::BUHID)
        || in_r(cp, &ur::TAGBANWA)
        || in_r(cp, &ur::MEETEI_MAYEK)
        || in_r(cp, &ur::MEETEI_MAYEK_EXT)
    {
        BlockClass::Indic
    } else {
        BlockClass::Other
    }
}

const BLOCK_CLASS: [BlockClass; 256] = {
    let mut t = [BlockClass::Other; 256];
    let mut b = 0usize;
    while b < 256 {
        let base = (b as u32) << 8;
        let first = class_of_cp_const(base);
        let mut off = 1u32;
        let mut mixed = false;
        while off < 256 {
            if class_of_cp_const(base | off) as u8 != first as u8 {
                mixed = true;
                break;
            }
            off += 1;
        }
        t[b] = if mixed { BlockClass::Mixed } else { first };
        b += 1;
    }
    t
};

/// Guardrail (#235 item 2): every classified range lies within
/// `[CLASSIFY_LO, CLASSIFY_HI]`, so the early-exit cannot drop a classified
/// code point. Adding a script range outside the bound (e.g. SMP Brahmi
/// U+11000) fails an assertion and breaks the build instead of silently
/// misclassifying. New ranges in `class_of_cp_const` must add a line here.
const _: () = {
    macro_rules! within {
        ($r:expr) => {
            assert!(*$r.start() >= CLASSIFY_LO && *$r.end() <= CLASSIFY_HI);
        };
    }
    within!(ur::CJK_UNIFIED);
    within!(ur::CJK_EXT_A);
    within!(ur::CJK_COMPAT);
    within!(ur::HANGUL_SYLLABLES);
    within!(ur::HANGUL_COMPAT_JAMO);
    within!(ur::HIRAGANA);
    within!(ur::KATAKANA);
    within!(ur::KATAKANA_HALFWIDTH);
    within!(ur::INDIC);
    within!(ur::TIBETAN);
    within!(ur::MYANMAR);
    within!(ur::KHMER);
    within!(ur::BALINESE);
    within!(ur::JAVANESE);
    within!(ur::SUNDANESE);
    within!(ur::TAI_THAM);
    within!(ur::CHAM);
    within!(ur::BATAK);
    within!(ur::BUGINESE);
    within!(ur::TAGALOG);
    within!(ur::HANUNOO);
    within!(ur::BUHID);
    within!(ur::TAGBANWA);
    within!(ur::MEETEI_MAYEK);
    within!(ur::MEETEI_MAYEK_EXT);
};

/// Classify a non-ASCII character into a script class for spacing decisions.
///
/// One data-dependent `BLOCK_CLASS` load replaces the up-to-25 chained range
/// checks for the ~99% of input whose block is uniform; only the handful of
/// `Mixed` blocks fall through to [`classify_char_slow`] (#235 item 2).
#[inline]
fn classify_char(ch: char) -> ScriptClass {
    let cp = ch as u32;
    if !(CLASSIFY_LO..=CLASSIFY_HI).contains(&cp) {
        return ScriptClass::Other;
    }
    match BLOCK_CLASS[(cp >> 8) as usize] {
        BlockClass::Ideograph => ScriptClass::Ideograph,
        BlockClass::Hangul => ScriptClass::Hangul,
        BlockClass::Kana => ScriptClass::Kana,
        BlockClass::Indic => ScriptClass::Indic,
        BlockClass::Other => ScriptClass::Other,
        BlockClass::Mixed => classify_char_slow(ch),
    }
}

/// The original per-range classification chain, used for `Mixed` blocks and as
/// the reference oracle for the exhaustive equivalence test.
#[inline]
fn classify_char_slow(ch: char) -> ScriptClass {
    if is_cjk_ideograph(ch) {
        ScriptClass::Ideograph
    } else if is_hangul(ch) {
        ScriptClass::Hangul
    } else if is_kana(ch) {
        ScriptClass::Kana
    } else if is_indic(ch) {
        ScriptClass::Indic
    } else {
        ScriptClass::Other
    }
}

/// Determine whether a space should be inserted between two adjacent CJK
/// transliterations, given their script classes.
///
/// Spaces are inserted:
/// - Between consecutive ideographs (each is a word): 北京 → "bei jing"
/// - Between consecutive Hangul syllables: 서울 → "seo ul"
/// - At ideograph↔kana boundaries: 東京タワー → "dong jing tawa-"
/// - After Latin/Other before any CJK: "hello東京" → "hello dong jing"
///
/// NOT inserted between consecutive kana (they concatenate to form words).
///
/// Note: this function is only called when `curr` is a CJK class
/// (Ideograph | Hangul | Kana), guarded by the `is_cjk` check at the
/// call site. The last arm is explicitly enumerated to match that
/// constraint rather than using a wildcard.
#[inline]
fn needs_cjk_space(prev: ScriptClass, curr: ScriptClass) -> bool {
    use ScriptClass::{Hangul, Ideograph, Indic, Kana, Latin, Other};
    matches!(
        (prev, curr),
        (Ideograph | Kana | Hangul, Ideograph | Hangul)
            | (Ideograph | Hangul, Kana)
            | (Latin | Other | Indic, Ideograph | Hangul | Kana)
    )
}

/// Check if a character is a CJK Unified Ideograph (Han character).
#[inline]
fn is_cjk_ideograph(ch: char) -> bool {
    let cp = ch as u32;
    ur::CJK_UNIFIED.contains(&cp) || ur::CJK_EXT_A.contains(&cp) || ur::CJK_COMPAT.contains(&cp)
}

/// Check if a character is a Hangul syllable or jamo.
#[inline]
fn is_hangul(ch: char) -> bool {
    let cp = ch as u32;
    ur::HANGUL_SYLLABLES.contains(&cp) || ur::HANGUL_COMPAT_JAMO.contains(&cp)
}

/// Check if a character is in any Brahmic abugida range (Indic, Tibetan, Myanmar, Khmer, etc.).
#[inline]
fn is_indic(ch: char) -> bool {
    let cp = ch as u32;
    ur::INDIC.contains(&cp)
        || ur::TIBETAN.contains(&cp)
        || ur::MYANMAR.contains(&cp)
        || ur::KHMER.contains(&cp)
        || ur::BALINESE.contains(&cp)
        || ur::JAVANESE.contains(&cp)
        || ur::SUNDANESE.contains(&cp)
        || ur::TAI_THAM.contains(&cp)
        || ur::CHAM.contains(&cp)
        || ur::BATAK.contains(&cp)
        || ur::BUGINESE.contains(&cp)
        || ur::TAGALOG.contains(&cp)
        || ur::HANUNOO.contains(&cp)
        || ur::BUHID.contains(&cp)
        || ur::TAGBANWA.contains(&cp)
        || ur::MEETEI_MAYEK.contains(&cp)
        || ur::MEETEI_MAYEK_EXT.contains(&cp)
}

/// Role of an Indic character for virama/mātrā context handling.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IndicRole {
    /// Not a special Indic role (independent vowel, modifier, digit, etc.)
    None,
    /// Consonant (carries inherent "a" in the transliteration table).
    Consonant,
    /// Dependent vowel sign (mātrā) — replaces the inherent "a".
    DependentVowel,
    /// Virama (halant) — suppresses the inherent "a".
    Virama,
}

/// Classify a Brahmic codepoint's role for virama/mātrā context handling.
///
/// Dispatches on the `cp >> 8` block byte (#235 item 2 addition): the common
/// scripts — Devanagari…Malayalam (the shared core layout), Tibetan, Myanmar,
/// Javanese, Meetei Mayek — resolve in one jump instead of walking the rare
/// scripts first via the old ordered `if` chain. Blocks shared by more than one
/// script (0x0D Malayalam+Sinhala, 0x17 Khmer+Philippine, 0x1A Buginese+Tai Tham,
/// 0x1B Balinese+Sundanese+Batak, 0xAA Cham+Meetei-Ext) keep the chain. Output
/// is identical to the chain for every code point, enforced exhaustively by
/// `indic_role_matches_chain`.
#[inline]
pub fn indic_char_role(cp: u32) -> IndicRole {
    match cp >> 8 {
        0x09..=0x0C => core_indic_role(cp),
        0x0F => tibetan_char_role(cp),
        0x10 => myanmar_char_role(cp),
        0xA9 => javanese_char_role(cp),
        0xAB => meetei_mayek_char_role(cp),
        _ => indic_char_role_chain(cp),
    }
}

/// Role by offset within the shared core Indic layout (Devanagari…Malayalam,
/// U+0900–U+0D7F), where consonants, mātrās, and virama sit at consistent
/// offsets modulo 0x80.
#[inline]
fn core_indic_role(cp: u32) -> IndicRole {
    match cp & 0x7F {
        0x15..=0x39 | 0x58..=0x5F => IndicRole::Consonant,
        0x3E..=0x4C => IndicRole::DependentVowel,
        0x4D => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// The original ordered range chain. Retained as the fallback for `Mixed`/shared
/// blocks and as the reference oracle for the exhaustive equivalence test.
#[inline]
fn indic_char_role_chain(cp: u32) -> IndicRole {
    if (0x0D80..=0x0DFF).contains(&cp) {
        return sinhala_char_role(cp);
    }
    if (0x0F00..=0x0FFF).contains(&cp) {
        return tibetan_char_role(cp);
    }
    if (0x1000..=0x109F).contains(&cp) {
        return myanmar_char_role(cp);
    }
    if (0x1780..=0x17FF).contains(&cp) {
        return khmer_char_role(cp);
    }
    if (0x1B00..=0x1B7F).contains(&cp) {
        return balinese_char_role(cp);
    }
    if (0xA980..=0xA9DF).contains(&cp) {
        return javanese_char_role(cp);
    }
    if ur::SUNDANESE.contains(&cp) {
        return sundanese_char_role(cp);
    }
    if ur::TAI_THAM.contains(&cp) {
        return tai_tham_char_role(cp);
    }
    if ur::CHAM.contains(&cp) {
        return cham_char_role(cp);
    }
    if ur::BATAK.contains(&cp) {
        return batak_char_role(cp);
    }
    if ur::BUGINESE.contains(&cp) {
        return buginese_char_role(cp);
    }
    if ur::TAGALOG.contains(&cp) {
        return tagalog_char_role(cp);
    }
    if ur::HANUNOO.contains(&cp) {
        return hanunoo_char_role(cp);
    }
    if ur::BUHID.contains(&cp) {
        return buhid_char_role(cp);
    }
    if ur::TAGBANWA.contains(&cp) {
        return tagbanwa_char_role(cp);
    }
    if ur::MEETEI_MAYEK.contains(&cp) || ur::MEETEI_MAYEK_EXT.contains(&cp) {
        return meetei_mayek_char_role(cp);
    }
    if !(0x0900..=0x0D7F).contains(&cp) {
        return IndicRole::None;
    }
    core_indic_role(cp)
}

/// Classify a Sinhala codepoint's role. Sinhala consonants, dependent vowels,
/// and virama (al-lakuna) occupy different offsets from the other Indic scripts.
#[inline]
pub fn sinhala_char_role(cp: u32) -> IndicRole {
    match cp {
        0x0D9A..=0x0DC6 => IndicRole::Consonant,
        0x0DCF..=0x0DDF | 0x0DF2..=0x0DF3 => IndicRole::DependentVowel,
        0x0DCA => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Tibetan codepoint's role.
///
/// Tibetan consonants (U+0F40–U+0F69) and subjoined consonants (U+0F90–U+0FBC)
/// carry an inherent 'a'. Vowel signs (U+0F71–U+0F7D) replace it.
/// The halanta mark (U+0F84) suppresses it.
#[inline]
pub fn tibetan_char_role(cp: u32) -> IndicRole {
    match cp {
        0x0F40..=0x0F69 | 0x0F90..=0x0FBC => IndicRole::Consonant,
        0x0F71..=0x0F7D => IndicRole::DependentVowel,
        0x0F84 => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Myanmar codepoint's role.
///
/// Myanmar consonants (U+1000–U+1021) carry an inherent 'a'.
/// Dependent vowels (U+102B–U+1035) and medial consonants (U+103B–U+103E) replace it.
/// Virama (U+1039) and asat (U+103A) suppress it.
#[inline]
pub fn myanmar_char_role(cp: u32) -> IndicRole {
    match cp {
        0x1000..=0x1021 => IndicRole::Consonant,
        0x102B..=0x1035 | 0x103B..=0x103E => IndicRole::DependentVowel,
        0x1039 | 0x103A => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Khmer codepoint's role.
///
/// Khmer consonants (U+1780–U+17A2) carry an inherent vowel.
/// Dependent vowels (U+17B6–U+17C5) replace it.
/// The coeng mark (U+17D2) stacks consonants (virama equivalent).
#[inline]
pub fn khmer_char_role(cp: u32) -> IndicRole {
    match cp {
        0x1780..=0x17A2 => IndicRole::Consonant,
        0x17B6..=0x17C5 => IndicRole::DependentVowel,
        0x17D2 => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Balinese codepoint's role. Balinese is a Brahmic abugida with
/// consonants carrying inherent 'a', dependent vowels, and adeg-adeg (virama).
#[inline]
pub fn balinese_char_role(cp: u32) -> IndicRole {
    match cp {
        0x1B13..=0x1B33 => IndicRole::Consonant,
        0x1B35..=0x1B43 => IndicRole::DependentVowel,
        0x1B44 => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Javanese codepoint's role. Javanese is a Brahmic abugida with
/// consonants carrying inherent 'a', dependent vowels, and pangkon (virama).
#[inline]
pub fn javanese_char_role(cp: u32) -> IndicRole {
    match cp {
        0xA990..=0xA9B2 => IndicRole::Consonant,
        0xA9B4..=0xA9BC => IndicRole::DependentVowel,
        0xA9C0 => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Sundanese codepoint's role. Sundanese consonants carry
/// inherent 'a', with dependent vowels and virama (U+1BAB).
#[inline]
pub fn sundanese_char_role(cp: u32) -> IndicRole {
    match cp {
        0x1B8A..=0x1BA0 => IndicRole::Consonant,
        0x1BA1..=0x1BA9 => IndicRole::DependentVowel,
        0x1BAB => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Tai Tham (Lanna) codepoint's role. Consonants carry
/// inherent 'a', with sakot (U+1A60) as virama.
#[inline]
pub fn tai_tham_char_role(cp: u32) -> IndicRole {
    match cp {
        0x1A20..=0x1A54 => IndicRole::Consonant,
        0x1A55..=0x1A5E | 0x1A61..=0x1A72 => IndicRole::DependentVowel,
        0x1A60 => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Cham codepoint's role. Consonants carry inherent 'a',
/// with virama at U+AA4D.
#[inline]
pub fn cham_char_role(cp: u32) -> IndicRole {
    match cp {
        0xAA00..=0xAA28 => IndicRole::Consonant,
        0xAA29..=0xAA36 => IndicRole::DependentVowel,
        0xAA4D => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Batak codepoint's role. Consonants carry inherent 'a',
/// with pangolat virama at U+1BF2–U+1BF3.
#[inline]
pub fn batak_char_role(cp: u32) -> IndicRole {
    match cp {
        0x1BC0..=0x1BE3 => IndicRole::Consonant,
        0x1BE7..=0x1BEE => IndicRole::DependentVowel,
        0x1BF2 | 0x1BF3 => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Buginese (Lontara) codepoint's role. Consonants carry
/// inherent 'a', with vowel killers at U+1A17–U+1A18.
#[inline]
pub fn buginese_char_role(cp: u32) -> IndicRole {
    match cp {
        0x1A00..=0x1A16 => IndicRole::Consonant,
        0x1A17..=0x1A1B => IndicRole::DependentVowel,
        _ => IndicRole::None,
    }
}

/// Classify a Tagalog codepoint's role. Consonants carry inherent 'a',
/// with virama at U+1714.
#[inline]
pub fn tagalog_char_role(cp: u32) -> IndicRole {
    match cp {
        0x1703..=0x1711 | 0x171F => IndicRole::Consonant,
        0x1712 | 0x1713 => IndicRole::DependentVowel,
        0x1714 => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Hanunoo codepoint's role. Consonants carry inherent 'a',
/// with virama at U+1734.
#[inline]
pub fn hanunoo_char_role(cp: u32) -> IndicRole {
    match cp {
        0x1723..=0x1731 => IndicRole::Consonant,
        0x1732 | 0x1733 => IndicRole::DependentVowel,
        0x1734 => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Buhid codepoint's role. Consonants carry inherent 'a',
/// with virama at U+1753.
#[inline]
pub fn buhid_char_role(cp: u32) -> IndicRole {
    match cp {
        0x1743..=0x1751 => IndicRole::Consonant,
        0x1752 => IndicRole::DependentVowel,
        0x1753 => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Tagbanwa codepoint's role. Consonants carry inherent 'a',
/// with virama at U+1773.
#[inline]
pub fn tagbanwa_char_role(cp: u32) -> IndicRole {
    match cp {
        0x1763..=0x1770 => IndicRole::Consonant,
        0x1772 => IndicRole::DependentVowel,
        0x1773 => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Classify a Meetei Mayek codepoint's role. Consonants carry inherent 'a',
/// with apun iyek (virama) at U+ABED.
#[inline]
pub fn meetei_mayek_char_role(cp: u32) -> IndicRole {
    match cp {
        0xABC0..=0xABE2 => IndicRole::Consonant,
        0xABE3..=0xABEA => IndicRole::DependentVowel,
        0xABED => IndicRole::Virama,
        _ => IndicRole::None,
    }
}

/// Check if a character is Hiragana or Katakana.
/// Used for spacing: kanji→kana and kana→kanji transitions get spaces.
#[inline]
fn is_kana(ch: char) -> bool {
    let cp = ch as u32;
    ur::HIRAGANA.contains(&cp) || ur::KATAKANA.contains(&cp) || ur::KATAKANA_HALFWIDTH.contains(&cp)
}

/// Remove diacritical marks while preserving base characters.
/// NFD decompose → strip combining marks → NFC recompose.
pub(crate) fn strip_accents(text: &str) -> String {
    let mut out = String::new();
    strip_accents_into(text, &mut out);
    out
}

/// In-place form of [`strip_accents`] writing into `out` (cleared first), so
/// the pipeline can reuse one buffer across steps (#236 item 7).
pub fn strip_accents_into(text: &str, out: &mut String) {
    use unicode_normalization::UnicodeNormalization;

    out.clear();
    // ASCII has no combining marks, so NFD→strip→NFC is the identity — skip the
    // normalization passes entirely (#236 item 6, matching `_strip_accents_batch`).
    if text.is_ascii() {
        out.push_str(text);
        return;
    }

    out.extend(
        text.nfd()
            .filter(|c| !unicode_normalization::char::is_combining_mark(*c))
            .nfc(),
    );
}

/// Reject a registration mutation once the tables have been sealed (#64).
/// `pub(crate)` so sibling modules (e.g. the emoji provider setter, #104) can
/// enforce the same latch.
pub(crate) fn check_not_sealed(op: &str) -> Result<(), crate::ErrorRepr> {
    if tables::registrations_sealed() {
        return Err(crate::ErrorRepr::Sealed { op: op.to_owned() });
    }
    Ok(())
}

/// Register or override a transliteration mapping for a language code (#38).
///
/// Pure Layer-1 core of the `_register_lang` shim: enforces the seal latch and
/// the registered-language cap, then delegates to `tables::register_lang`,
/// returning the native [`crate::ErrorRepr`]. The PyO3 wrapper lives in
/// `crate::py::transliterate`.
pub(crate) fn register_lang(
    code: &str,
    mappings: HashMap<String, String>,
) -> Result<(), crate::ErrorRepr> {
    check_not_sealed("register_lang")?;
    // Guard against unbounded growth of the global language table.
    let current = tables::registered_lang_count();
    if current >= tables::MAX_REGISTERED_LANGS {
        // Re-registering an existing code is always allowed (overwrite, not grow).
        if !tables::has_registered_lang(code) {
            return Err(crate::ErrorRepr::RegisterLangLimit {
                max: tables::MAX_REGISTERED_LANGS,
            });
        }
    }
    tables::register_lang(code, mappings).map_err(|bad_keys| {
        crate::ErrorRepr::RegisterLangBadKeys {
            keys: bad_keys
                .iter()
                .map(|k| format!("{k:?}"))
                .collect::<Vec<_>>()
                .join(", "),
        }
    })
}

/// Register global pre-transliteration replacements (#38).
///
/// Pure Layer-1 core of the `_register_replacements` shim.
pub(crate) fn register_replacements(
    replacements: HashMap<String, String>,
) -> Result<(), crate::ErrorRepr> {
    check_not_sealed("register_replacements")?;
    tables::register_replacements(replacements).map_err(|projected| {
        crate::ErrorRepr::RegisterReplacementsLimit {
            max: tables::MAX_REPLACEMENTS,
            projected,
        }
    })
}

/// Remove a single global pre-transliteration replacement by key (#38).
///
/// Returns `Ok(true)` if the key was present, `Ok(false)` otherwise. Pure
/// Layer-1 core of the `_remove_replacement` shim.
pub(crate) fn remove_replacement(key: &str) -> Result<bool, crate::ErrorRepr> {
    check_not_sealed("remove_replacement")?;
    Ok(tables::remove_replacement(key))
}

/// Clear all global pre-transliteration replacements (#38).
///
/// Pure Layer-1 core of the `_clear_replacements` shim.
pub(crate) fn clear_replacements() -> Result<(), crate::ErrorRepr> {
    check_not_sealed("clear_replacements")?;
    tables::clear_replacements();
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// #240 — the single-pass strict transliteration must (a) succeed with the
    /// Ignore-mode output when everything is translatable, and (b) error on the
    /// exact first untranslatable character that `find_untranslatable_impl`
    /// reports, never running the engine twice.
    #[test]
    fn strict_single_pass_matches_reference() {
        // All-translatable input: strict succeeds with the normal output.
        assert_eq!(
            transliterate_strict("café Москва", None, false, false, false).unwrap(),
            transliterate_impl(
                "café Москва",
                None,
                ErrorMode::Ignore,
                "",
                false,
                false,
                false
            )
            .into_owned()
        );

        // Inputs containing untranslatable characters: whatever
        // `find_untranslatable_impl` reports first, strict must report identically
        // (same char and byte offset), and agree on the translatable case. U+E000
        // is in the Private Use Area — guaranteed to have no transliteration and
        // no NFKC recovery, ever — so the error branch is definitely exercised
        // (U+1F980 also reaches it: the emoji tables drive `demojize`, not
        // `transliterate`).
        let mut hit_error_branch = false;
        for s in [
            "a\u{E000}b\u{E000}",
            "café\u{E000}",
            "\u{1F980}x",
            "abc",
            "Привет",
        ] {
            let reference = find_untranslatable_impl(s, None, false, false, false)
                .into_iter()
                .next();
            match (
                transliterate_strict(s, None, false, false, false),
                reference,
            ) {
                (Err(crate::ErrorRepr::Untranslatable { ch, byte_offset }), Some((ech, eoff))) => {
                    assert_eq!(
                        (ch, byte_offset),
                        (ech, eoff),
                        "strict first-untranslatable mismatch for {s:?}"
                    );
                    hit_error_branch = true;
                }
                (Ok(_), None) => {} // both agree the whole input is translatable
                (got, exp) => panic!("strict/reference disagree for {s:?}: {got:?} vs {exp:?}"),
            }
        }
        assert!(
            hit_error_branch,
            "test never exercised the strict Error::Untranslatable branch"
        );
    }

    /// #235 item 2 — the `BLOCK_CLASS` early-exit/table path must agree with the
    /// original per-range chain for **every** scalar value. Exhaustive over the
    /// whole Unicode scalar space; the block table cannot misclassify silently.
    #[test]
    fn classify_char_matches_slow() {
        for cp in 0u32..=0x10_FFFF {
            if let Some(ch) = char::from_u32(cp) {
                assert_eq!(
                    classify_char(ch),
                    classify_char_slow(ch),
                    "classify_char disagrees with chain at U+{cp:04X}"
                );
            }
        }
    }

    /// #235 item 2 (Indic addition) — the block-dispatch `indic_char_role` must
    /// agree with the original ordered chain for every scalar value.
    #[test]
    fn indic_role_matches_chain() {
        for cp in 0u32..=0x10_FFFF {
            assert_eq!(
                indic_char_role(cp),
                indic_char_role_chain(cp),
                "indic_char_role disagrees with chain at U+{cp:04X}"
            );
        }
    }

    // #231: the conflict matrix now lives in the core. These exercise the pure
    // validator so the contract holds regardless of the (Python) binding, and
    // without needing an initialized Python interpreter in the test build.
    fn validate(
        lang: Option<&str>,
        target: Option<&str>,
        errors: &str,
        replace_with: &str,
        strict_iso9: bool,
        gost7034: bool,
        tones: bool,
        context: bool,
    ) -> Result<(), crate::ErrorRepr> {
        validate_transliterate_args(
            lang,
            target,
            errors,
            replace_with,
            strict_iso9,
            gost7034,
            tones,
            context,
        )
    }

    fn err_msg(r: Result<(), crate::ErrorRepr>) -> String {
        r.unwrap_err().to_string()
    }

    #[test]
    fn validate_accepts_defaults() {
        assert!(validate(None, None, "replace", "[?]", false, false, false, false).is_ok());
        assert!(validate(
            Some("ru"),
            None,
            "replace",
            "[?]",
            false,
            false,
            false,
            false
        )
        .is_ok());
        // target= with every forward-only param at its default is fine.
        assert!(validate(
            None,
            Some("ru"),
            "replace",
            "[?]",
            false,
            false,
            false,
            false
        )
        .is_ok());
    }

    #[test]
    fn validate_rejects_lang_and_target() {
        let r = validate(
            Some("ru"),
            Some("ru"),
            "replace",
            "[?]",
            false,
            false,
            false,
            false,
        );
        assert!(err_msg(r).contains("'lang' and 'target' are mutually exclusive"));
    }

    #[test]
    fn validate_rejects_context_with_target() {
        let r = validate(
            None,
            Some("ar"),
            "replace",
            "[?]",
            false,
            false,
            false,
            true,
        );
        assert!(err_msg(r).contains("'context' and 'target' are mutually exclusive"));
    }

    #[test]
    fn validate_rejects_tones_with_context() {
        let r = validate(None, None, "replace", "[?]", false, false, true, true);
        assert!(err_msg(r).contains("'tones' cannot be used with 'context'"));
    }

    #[test]
    fn validate_rejects_strict_with_context() {
        let r = validate(None, None, "strict", "[?]", false, false, false, true);
        assert!(err_msg(r).contains("errors='strict' cannot be used with 'context'"));
    }

    #[test]
    fn validate_rejects_forward_only_with_target_sorted() {
        // tones + gost7034 + errors set alongside target: names rendered sorted.
        let r = validate(None, Some("ru"), "ignore", "[?]", false, true, true, false);
        let msg = err_msg(r);
        assert!(msg.contains(
            "forward-only parameters (errors, gost7034, tones) cannot be used with 'target'"
        ));
    }

    #[test]
    fn validate_rejects_replace_with_override_with_target() {
        let r = validate(None, Some("ru"), "replace", "X", false, false, false, false);
        assert!(err_msg(r)
            .contains("forward-only parameters (replace_with) cannot be used with 'target'"));
    }

    #[test]
    fn test_ascii_passthrough() {
        let result = transliterate_impl(
            "hello",
            None,
            ErrorMode::Replace,
            "[?]",
            false,
            false,
            false,
        );
        assert_eq!(result, "hello");
    }

    #[test]
    fn test_is_ascii() {
        assert!("hello".is_ascii());
        assert!(!"héllo".is_ascii());
    }

    mod proptest_properties {
        use super::*;
        use proptest::prelude::*;

        proptest! {
            #![proptest_config(ProptestConfig::with_cases(1000))]

            /// With ErrorMode::Ignore, output is always pure ASCII.
            #[test]
            fn transliterate_ignore_is_ascii(s in "\\PC*") {
                let result = transliterate_impl(&s, None, ErrorMode::Ignore, "", false, false, false);
                prop_assert!(
                    result.is_ascii(),
                    "Non-ASCII in Ignore output: {:?}",
                    result.chars().filter(|c: &char| !c.is_ascii()).collect::<Vec<_>>()
                );
            }

            /// With ErrorMode::Preserve, non-empty printable input produces
            /// non-empty output (every char either maps or is kept verbatim).
            /// Excludes combining marks (\p{M}) which legitimately map to empty
            /// when not attached to a base character.
            #[test]
            fn transliterate_preserve_nonempty(s in "[^\\s\\p{M}]{1,50}") {
                let result = transliterate_impl(&s, None, ErrorMode::Preserve, "", false, false, false);
                prop_assert!(!result.is_empty());
            }

            /// strip_accents is idempotent.
            #[test]
            fn strip_accents_idempotent(s in "\\PC*") {
                let once = strip_accents(&s);
                let twice = strip_accents(&once);
                prop_assert_eq!(&once, &twice);
            }

            /// strip_accents output is always NFC (docstring: NFD → filter → NFC).
            #[test]
            fn strip_accents_output_is_nfc(s in "\\PC*") {
                let result = strip_accents(&s);
                prop_assert!(
                    unicode_normalization::is_nfc(&result),
                    "strip_accents output not NFC"
                );
            }

            /// ASCII input passes through transliterate unchanged.
            #[test]
            fn transliterate_ascii_passthrough(s in "[a-zA-Z0-9 ]{0,100}") {
                let result = transliterate_impl(&s, None, ErrorMode::Replace, "[?]", false, false, false);
                prop_assert_eq!(&result, &s);
            }
        }
    }
}
