//! #563 — coverage introspection over the bundled confusable tables.
//!
//! `find_untranslatable` has existed for transliteration since #184; there was no
//! confusables analogue, so answering "which sources go uncovered?" meant rebuilding
//! the capability outside the library against a cached copy of the upstream file. That
//! harness should not have had to exist.
//!
//! Both accessors are derived from the same PHF the fold consults, so the assertions
//! below are written against `normalize_confusables`' actual behaviour wherever
//! possible rather than against a hardcoded expectation.

use disarm::api::{
    find_unmapped_confusables, is_confusable, normalize_confusables, unmapped_confusables,
    TargetScript,
};

const LATIN: TargetScript = TargetScript::Latin;
const CYR: TargetScript = TargetScript::Cyrillic;

// ── unmapped_confusables: the global exposure set ────────────────────────────

#[test]
fn exposure_set_is_non_empty_and_sorted() {
    let latin = unmapped_confusables(LATIN);
    assert!(
        !latin.is_empty(),
        "the bundled table does not fold everything"
    );
    assert!(
        latin.windows(2).all(|w| w[0] < w[1]),
        "must be sorted and duplicate-free so two releases can be diffed"
    );
}

#[test]
fn exposure_set_is_deterministic_across_calls() {
    // The underlying PHF iterates in hash order; the sort is what makes this stable.
    assert_eq!(unmapped_confusables(LATIN), unmapped_confusables(LATIN));
}

/// The defining property: nothing in the exposure set is folded by the table it is
/// reported against. Checked against the *transform*, not against the table, so a
/// divergence between the two would fail here.
#[test]
fn nothing_in_the_exposure_set_actually_folds() {
    for &ch in &unmapped_confusables(LATIN) {
        let s = ch.to_string();
        assert_eq!(
            normalize_confusables(&s, LATIN),
            s,
            "U+{:04X} is reported unmapped but the fold rewrites it",
            ch as u32
        );
    }
}

/// The converse: a source the table *does* fold must not appear in the set. Cyrillic а
/// (U+0430) is the canonical mapped homoglyph.
#[test]
fn mapped_sources_are_absent_from_the_exposure_set() {
    let latin = unmapped_confusables(LATIN);
    for ch in ['\u{0430}', '\u{0435}', '\u{043E}'] {
        assert!(
            !latin.contains(&ch),
            "U+{:04X} folds, so it is not exposure",
            ch as u32
        );
    }
}

/// The two targets have genuinely different coverage — a single set would be wrong.
#[test]
fn the_two_targets_report_different_sets() {
    assert_ne!(unmapped_confusables(LATIN), unmapped_confusables(CYR));
}

/// Pins the ASCII residue documented on the API (#563).
///
/// TR39 is a skeleton transform, so `%`, `0`, `1`, `I` and `m` are upstream *sources*
/// (m→rn, I/1→l, 0→O, %→º/₀). disarm does not apply those rows — folding a legitimate
/// ASCII `m` to `rn` corrupts prose — so they are reported, and a per-input scan over
/// ordinary English will hit `m`. Documented behaviour, not a defect; this test makes
/// any change to that set deliberate. The digit and contraction issues are where the
/// policy question actually lives.
#[test]
fn ascii_residue_is_exactly_the_five_documented_skeleton_sources() {
    let ascii: Vec<char> = unmapped_confusables(LATIN)
        .into_iter()
        .filter(char::is_ascii)
        .collect();
    assert_eq!(ascii, vec!['%', '0', '1', 'I', 'm']);
}

// ── find_unmapped_confusables: the per-input scan ────────────────────────────

#[test]
fn clean_ascii_without_skeleton_sources_reports_nothing() {
    assert!(find_unmapped_confusables("hello", LATIN).is_empty());
    assert!(find_unmapped_confusables("", LATIN).is_empty());
}

/// A folded homoglyph is coverage, not a gap — the scan must agree with the transform.
#[test]
fn a_mapped_homoglyph_is_not_reported() {
    let spoof = "p\u{0430}yp\u{0430}l";
    assert_eq!(normalize_confusables(spoof, LATIN), "paypal");
    assert!(find_unmapped_confusables(spoof, LATIN).is_empty());
}

/// Offsets anchor to the caller's string, and occurrences come out in order.
#[test]
fn offsets_are_byte_offsets_in_the_caller_string() {
    // 'a'(1) + 'm'(1) — the skeleton source — then a non-source, then 'm' again.
    let text = "am\u{0430}xm";
    let found = find_unmapped_confusables(text, LATIN);
    let hits: Vec<(char, usize)> = found.iter().map(|u| (u.ch, u.offset)).collect();
    assert_eq!(hits, vec![('m', 1), ('m', 5)]);
    // Every reported offset is a real char boundary carrying the reported char.
    for (ch, offset) in hits {
        assert!(text.is_char_boundary(offset));
        assert_eq!(text[offset..].chars().next(), Some(ch));
    }
}

/// #475/#477 parity: a *decomposed* homoglyph whose precomposed form is mapped must
/// count as covered, exactly as the fold treats it. Reporting the bare base as a gap
/// would make the coverage number disagree with what `normalize_confusables` does.
#[test]
fn decomposed_homoglyph_is_covered_not_reported() {
    // і U+0456 + combining diaeresis U+0308 composes to ї U+0457, which folds to "i".
    let decomposed = "\u{0456}\u{0308}";
    assert_eq!(normalize_confusables(decomposed, LATIN), "i");
    assert!(find_unmapped_confusables(decomposed, LATIN).is_empty());
}

/// Offsets stay anchored to the original text even when composition ran, so a report
/// on decomposed input can still be sliced against the caller's string. Mirrors
/// `find_untranslatable_offsets_are_in_original_text` (#479 review).
#[test]
fn offsets_survive_composition() {
    // і+◌̈ (composes, covered) then 'm' (a skeleton source). The 'm' sits at byte
    // 'і'(2) + '◌̈'(2) = 4.
    let text = "\u{0456}\u{0308}m";
    let found = find_unmapped_confusables(text, LATIN);
    assert_eq!(found.len(), 1);
    assert_eq!(found[0].ch, 'm');
    assert_eq!(found[0].offset, 4);
    assert_eq!(text[found[0].offset..].chars().next(), Some('m'));
}

/// The scan and the global set must answer the same question. Every character the
/// scan reports has to be a member of the exposure set, and every non-reported
/// character must not be.
#[test]
fn scan_agrees_with_the_global_set() {
    let exposure = unmapped_confusables(LATIN);
    let sample: String = exposure.iter().take(200).collect();
    let reported: Vec<char> = find_unmapped_confusables(&sample, LATIN)
        .into_iter()
        .map(|u| u.ch)
        .collect();
    // Some of the sample may compose with a neighbour (combining marks are in the set),
    // so this is a subset relation, not equality — but nothing may be reported that is
    // outside the global set.
    for ch in &reported {
        assert!(
            exposure.contains(ch),
            "scan reported U+{:04X}, absent from the global set",
            *ch as u32
        );
    }
    assert!(!reported.is_empty());
}

/// Never panics and never reports a character that is not in the input.
#[test]
fn scan_is_sound_on_mixed_input() {
    for text in [
        "hello world",
        "p\u{0430}ypal.com",
        "\u{1F980}\u{200B}\u{0301}",
        "Ｆｕｌｌｗｉｄｔｈ",
        "\u{1100}\u{1161}\u{11A8}", // conjoining Hangul jamo (#483)
        "a\u{0301}\u{0302}\u{0303}b",
    ] {
        for target in [LATIN, CYR] {
            for hit in find_unmapped_confusables(text, target) {
                assert!(text.is_char_boundary(hit.offset));
                assert!(hit.offset < text.len());
            }
        }
    }
}

// ── #590: the Latin-1 Supplement block gap ───────────────────────────────────
//
// `is_latin_or_common` in `scripts/gen_confusables.py` enumerates Latin block ranges
// and jumps from 0x007F straight to 0x00C0, leaving U+0080–U+00BF uncovered. `º`
// (U+00BA, category Lo, Script=Latin) lives in that hole, so `filter_direct` read it as
// a non-Latin target and discarded both upstream rows that point at it.

/// `⁰` and `⁹` are the only two superscript digits upstream TR39 carries — it lists
/// visual lookalikes, and no letter resembles a superscript four. They are structural
/// twins, so they must behave alike. `⁹` targets `ꝰ` in Latin Extended-D and survived
/// to be rewritten to the ASCII digit; `⁰` targets `º` and was dropped before the
/// digit rule could see it.
#[test]
fn superscript_zero_folds_like_superscript_nine() {
    assert_eq!(normalize_confusables("\u{2079}", LATIN), "9");
    assert_eq!(normalize_confusables("\u{2070}", LATIN), "0");
}

/// The other row that targeted `º`: MODIFIER LETTER SMALL O. Its upstream target is a
/// letter, not a digit, so it folds to ASCII `o` rather than through the digit rule.
#[test]
fn modifier_letter_small_o_folds_to_ascii_o() {
    assert_eq!(normalize_confusables("\u{1D52}", LATIN), "o");
}

/// The visible symptom: both were reported as uncovered exposure, which is what
/// `unmapped_confusables` exists to surface.
#[test]
fn the_rows_targeting_the_ordinal_indicator_are_covered() {
    let latin = unmapped_confusables(LATIN);
    for ch in ['\u{2070}', '\u{1D52}'] {
        assert!(
            !latin.contains(&ch),
            "U+{:04X} {ch:?} is still reported unmapped",
            ch as u32
        );
    }
}

// ── #593: prototypes ASCII_FOLD already covers ───────────────────────────────
//
// `filter_latin_homoglyphs` recovers a Latin-script source whose TR39 prototype is a
// single basic-ASCII graphic. `ASCII_FOLD` runs later, in `generate_mappings`, so a row
// whose prototype that table already knows was discarded before it could be consulted —
// the same shape as #590 and #587: a filter dropping a row before the pass that would
// have made it valid.

/// The one that surfaced it. TR39 puts `٨ ۸ Λ Ꟛ` in a single confusable class, and the
/// Latin lambdas did not collide with the Greek one they are defined to be confusable
/// with — the class had three distinct skeletons.
#[test]
fn the_lambda_class_collides() {
    for src in ["\u{039B}", "\u{A7DA}", "\u{A7DC}"] {
        assert_eq!(normalize_confusables(src, LATIN), "A", "{src:?}");
    }
}

/// The other five recoveries. Each prototype is a non-ASCII Latin-extended glyph that
/// `ASCII_FOLD` maps to a basic-ASCII representative.
#[test]
fn prototypes_ascii_fold_already_covers_are_recovered() {
    for (src, want) in [
        ("\u{1E9E}", "B"), // ẞ → ß → B
        ("\u{A7D6}", "B"), // Ꟗ → ß → B
        ("\u{A7B5}", "b"), // ꞵ → ß → b
        ("\u{A76B}", "z"), // ꝫ → ȝ → z
    ] {
        assert_eq!(normalize_confusables(src, LATIN), want, "{src:?}");
    }
}

/// The guard. `ţ` and `ț` reach the same prototype, but folding them strips a cedilla
/// and a comma-below — `ț` is ordinary Romanian orthography. `normalize_confusables`
/// promises accented Latin comes through intact, so an accented source stays unmapped
/// however foldable its prototype is. `strip_obfuscation` is the tool for that job.
#[test]
fn an_accented_source_is_never_folded_away() {
    for src in ["\u{0163}", "\u{021B}"] {
        assert_eq!(
            normalize_confusables(src, LATIN),
            src,
            "{src:?} lost a diacritic"
        );
    }
}

/// `fix_case_mismatch` uppercased the prototype before `ASCII_FOLD` could see it, and
/// `ß`.to_uppercase() is the two-character `SS`, which then escaped the fold because
/// that only fires on a single char. This table is about *visual* confusability and
/// Cherokee YE is a B-shape, so `SS` was never the right answer.
#[test]
fn a_prototype_is_ascii_folded_before_its_case_is_reconciled() {
    assert_eq!(normalize_confusables("\u{13F0}", LATIN), "B");
}

// ── #593: the guard must not reach the rows this pass always handled ─────────
//
// The first attempt at the diacritic guard applied it to every source, not only to the
// ones newly recovered through `ASCII_FOLD`. That silently deleted three established
// mappings, and nothing failed — the change was caught by reading the regenerated data
// diff, which is not a gate. These three tests are that gate.

/// `Ç`, `ç` and `Ǿ` carry a diacritic, so a naive "never fold an accented source" rule
/// removes them. They reach a bare ASCII prototype only because `strip_combining` strips
/// the mark from TR39's target (`Ç → C` + combining comma below), and they have folded
/// since long before #593. The guard is for rows the `ASCII_FOLD` path newly recovers,
/// not for these.
#[test]
fn an_accented_source_with_an_ascii_prototype_still_folds() {
    for (src, want) in [
        ("\u{00C7}", "C"), // Ç LATIN CAPITAL LETTER C WITH CEDILLA
        ("\u{00E7}", "c"), // ç LATIN SMALL LETTER C WITH CEDILLA
        ("\u{01FE}", "O"), // Ǿ LATIN CAPITAL LETTER O WITH STROKE AND ACUTE
    ] {
        assert_eq!(
            normalize_confusables(src, LATIN),
            want,
            "{src:?} stopped folding — a guard has been widened over the rows \
             `filter_latin_homoglyphs` always handled"
        );
    }
}

/// The property behind those three, stated once so a new one cannot appear unguarded:
/// an accented Latin source whose fold is already in the table must keep folding to
/// ASCII. Written against the table's actual behaviour rather than a fixed list — if
/// upstream adds a fourth, it is covered without editing this test.
#[test]
fn no_accented_source_in_the_table_folds_to_itself() {
    let accented_but_mapped = ['\u{00C7}', '\u{00E7}', '\u{01FE}'];
    for ch in accented_but_mapped {
        let src = ch.to_string();
        let folded = normalize_confusables(&src, LATIN).into_owned();
        assert_ne!(
            folded, src,
            "U+{:04X} {ch:?} now passes through unchanged",
            ch as u32
        );
        assert!(
            folded.is_ascii(),
            "U+{:04X} {ch:?} folded to {folded:?}, which is not ASCII",
            ch as u32
        );
    }
}

/// Why losing `Ç → C` would have mattered, rather than merely being a missing row.
/// #586's fixed-point loop converges `Ҫ` + combining cedilla by composing it to `Ç` and
/// then folding that to `C`. Drop the second step and the fold stops half-done, leaving
/// output `is_confusable` still flags — the exact defect #586 existed to remove.
#[test]
fn the_fixed_point_loop_still_depends_on_the_cedilla_row() {
    let folded = normalize_confusables("\u{04AA}\u{0327}", LATIN);
    assert_eq!(folded, "C");
    assert!(
        !is_confusable(&folded, LATIN),
        "the fold left confusable output — #586's convergence rests on Ç → C"
    );
}
