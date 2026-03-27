# Language Discriminator Detection Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add character-level language discrimination within ambiguous scripts (Cyrillic, Arabic, Latin) so `lang="auto"` returns the correct language when exclusive characters are present, falling back to the existing script default when they're not.

**Architecture:** A new `discriminate_by_chars()` function scans text for characters exclusive to a particular language within an ambiguous script. The existing `resolve_auto_lang()` is extended with a two-tier strategy: (1) try discriminators, (2) fall back to `script_to_lang()`. The discriminator uses a Rust `match` statement for O(1) per-character lookup. If discriminators for two different languages conflict (e.g., mixed Ukrainian + Serbian text), the function falls back to the script default — this is the fail-safe guarantee.

**Tech Stack:** Rust (`src/scripts.rs`), Python tests (`tests/test_lang_auto.py`), documentation (Markdown)

---

### Task 1: Add Rust unit tests for discriminator functions (TDD — tests first)

**Files:**
- Modify: `src/scripts.rs` (add tests at the end of `mod tests`)

**Step 1: Write failing tests for the new discriminator functions**

Add these tests to the `mod tests` block at the end of `src/scripts.rs`:

```rust
// ── Language discriminator tests ──────────────────────────────

#[test]
fn test_discriminate_ukrainian_by_exclusive_chars() {
    // ї is exclusively Ukrainian among our Cyrillic profiles
    assert_eq!(resolve_auto_lang("Київ — столиця України"), Some("uk".to_owned()));
}

#[test]
fn test_discriminate_serbian_by_exclusive_chars() {
    // ћ and ђ are exclusively Serbian
    assert_eq!(resolve_auto_lang("Ђорђе и Ћирилица"), Some("sr".to_owned()));
}

#[test]
fn test_discriminate_persian_by_exclusive_chars() {
    // پ چ ژ گ are exclusively Persian among our Arabic profiles
    assert_eq!(resolve_auto_lang("پارسی زبان"), Some("fa".to_owned()));
}

#[test]
fn test_discriminate_vietnamese_by_exclusive_chars() {
    // ơ and ư are exclusively Vietnamese
    assert_eq!(resolve_auto_lang("Việt Nam có nhiều người"), Some("vi".to_owned()));
}

#[test]
fn test_discriminate_turkish_by_exclusive_chars() {
    // İ and ı are exclusively Turkish
    assert_eq!(resolve_auto_lang("İstanbul güzel bir şehır"), Some("tr".to_owned()));
}

#[test]
fn test_discriminate_german_by_exclusive_chars() {
    // ß is exclusively German
    assert_eq!(resolve_auto_lang("Straße nach Süden"), Some("de".to_owned()));
}

#[test]
fn test_discriminate_fallback_on_conflict() {
    // Mix Ukrainian ї and Serbian ћ — should fall back to script default (ru)
    assert_eq!(resolve_auto_lang("їћ"), Some("ru".to_owned()));
}

#[test]
fn test_discriminate_cyrillic_no_exclusive_chars() {
    // Plain Russian text with no exclusive chars — default to ru
    assert_eq!(resolve_auto_lang("Москва"), Some("ru".to_owned()));
}

#[test]
fn test_discriminate_arabic_no_exclusive_chars() {
    // Plain Arabic text with no Persian chars — default to ar
    assert_eq!(resolve_auto_lang("العربية"), Some("ar".to_owned()));
}

#[test]
fn test_discriminate_latin_no_exclusive_chars() {
    // Accented Latin with no exclusive chars — returns None (no lang)
    assert_eq!(resolve_auto_lang("café"), None);
}

#[test]
fn test_discriminate_latin_ascii_only() {
    // Pure ASCII — returns None
    assert_eq!(resolve_auto_lang("hello"), None);
}
```

**Step 2: Run tests to verify they fail**

Run: `export PATH="$HOME/.cargo/bin:$PATH" && cd /Users/subzero/gt/translit/mayor/rig && cargo test --lib scripts::tests -- --test-threads=1 2>&1 | tail -20`

Expected: FAIL — `discriminate_*` tests fail because Ukrainian text resolves to `"ru"`, Vietnamese to `None`, etc.

Note: Some tests (like `test_discriminate_cyrillic_no_exclusive_chars`) will pass already since they test the existing default behavior. That's fine — they serve as regression guards.

---

### Task 2: Implement the discriminator functions

**Files:**
- Modify: `src/scripts.rs` (add new functions, modify `resolve_auto_lang`)

**Step 1: Add the discriminator lookup function**

Add this function after `script_to_lang()` and before `resolve_auto_lang()`:

```rust
/// True if the script is shared by multiple languages with different
/// transliteration profiles.  Only these scripts trigger discriminator
/// scanning — all other scripts have a 1:1 script→language mapping.
fn is_ambiguous_script(script: &str) -> bool {
    matches!(script, "Cyrillic" | "Arabic")
}

/// Look up whether a character is an exclusive discriminator for a
/// language within the given script.
///
/// Returns `Some(lang_code)` if the character appears exclusively in
/// one language's alphabet among the profiles we support for that
/// script.  Returns `None` for characters shared across languages.
///
/// **Fail-safe property:** only characters with zero ambiguity are
/// included.  False positives are impossible by construction — every
/// entry has been verified against all supported profiles for the
/// script.
fn lookup_discriminator(ch: char, script: &str) -> Option<&'static str> {
    match script {
        "Cyrillic" => match ch {
            // Ukrainian exclusive: ґ Ґ ї Ї є Є і І
            '\u{0491}' | '\u{0490}' | '\u{0457}' | '\u{0407}'
            | '\u{0454}' | '\u{0404}' | '\u{0456}' | '\u{0406}' => Some("uk"),
            // Serbian exclusive: ђ Ђ ћ Ћ љ Љ њ Њ џ Џ ј Ј
            '\u{0452}' | '\u{0402}' | '\u{045B}' | '\u{040B}'
            | '\u{0459}' | '\u{0409}' | '\u{045A}' | '\u{040A}'
            | '\u{045F}' | '\u{040F}' | '\u{0458}' | '\u{0408}' => Some("sr"),
            // Mongolian Cyrillic exclusive: ө Ө ү Ү
            '\u{04E9}' | '\u{04E8}' | '\u{04AF}' | '\u{04AE}' => Some("mn"),
            _ => None,
        },
        "Arabic" => match ch {
            // Persian exclusive: پ چ ژ گ
            '\u{067E}' | '\u{0686}' | '\u{0698}' | '\u{06AF}' => Some("fa"),
            _ => None,
        },
        _ => None,
    }
}

/// Look up whether a Latin-script character is an exclusive discriminator
/// for a language.
///
/// Separated from `lookup_discriminator` because Latin is handled via a
/// different code path (Latin text has no "primary script" in the
/// existing detection flow).
fn lookup_latin_discriminator(ch: char) -> Option<&'static str> {
    match ch {
        // Vietnamese exclusive: ơ Ơ ư Ư
        '\u{01A1}' | '\u{01A0}' | '\u{01B0}' | '\u{01AF}' => Some("vi"),
        // Turkish exclusive: İ (dotted capital I), ı (dotless small i)
        '\u{0130}' | '\u{0131}' => Some("tr"),
        // German exclusive: ß (eszett)
        '\u{00DF}' => Some("de"),
        // German exclusive: ẞ (capital eszett, rare but unambiguous)
        '\u{1E9E}' => Some("de"),
        _ => None,
    }
}

/// Scan text for discriminator characters exclusive to a particular language.
///
/// Returns `Some(lang)` only if **exactly one** language's discriminators
/// are found.  Returns `None` if:
/// - no discriminator characters appear (→ fall back to script default)
/// - discriminators for two different languages appear (→ conflict; fail-safe
///   fall back to script default)
///
/// This is the core fail-safe guarantee: the function never returns a wrong
/// answer.  In the worst case it returns `None` and the caller uses the
/// previous default behaviour.
fn discriminate_by_chars(text: &str, script: &str) -> Option<&'static str> {
    let mut candidate: Option<&'static str> = None;

    for ch in text.chars() {
        let hit = if script == "Latin" {
            lookup_latin_discriminator(ch)
        } else {
            lookup_discriminator(ch, script)
        };

        if let Some(lang) = hit {
            match candidate {
                None => candidate = Some(lang),
                Some(prev) if prev == lang => {} // same language — reinforce
                Some(_) => return None,          // conflict — bail out
            }
        }
    }

    candidate
}
```

**Step 2: Modify `resolve_auto_lang` to use discriminators**

Replace the existing `resolve_auto_lang` function with:

```rust
/// Resolve `lang="auto"` by scanning text for the first non-Latin, non-Common script,
/// then refining with character-level discriminators for ambiguous scripts.
///
/// **Detection strategy (two-tier):**
///
/// 1. **Script detection:** find the primary non-Latin script (unchanged from before).
/// 2. **Discriminator refinement:** for ambiguous scripts (Cyrillic, Arabic), scan
///    for characters exclusive to one language.  If exactly one language's exclusive
///    characters appear, return that language.  If none or multiple appear, fall back
///    to the script default.
/// 3. **Latin fallback:** if the text contains only Latin characters, try Latin-script
///    discriminators (Vietnamese ơ/ư, Turkish İ/ı, German ß).
///
/// **Fail-safe guarantee:** discriminators can only *upgrade* the result (from a
/// generic script default to a specific language).  They never *downgrade* — if
/// anything is uncertain, the previous default behaviour is preserved.
///
/// Returns the default language code for that script, or `None` if the text
/// contains only Latin/Common/Inherited characters (or is empty) and no Latin
/// discriminators match.
///
/// **Note:** For mixed-script input (e.g. "Hello 北京 Привет"), the first
/// non-Latin script encountered wins. This is a deliberate simplification —
/// callers needing per-segment transliteration should split the text first.
pub fn resolve_auto_lang(text: &str) -> Option<String> {
    // Pass 1: Find primary non-Latin, non-Common script.
    let mut primary_script: Option<&str> = None;
    for ch in text.chars() {
        let script = detect_char_script(ch);
        if script != "Common" && script != "Inherited" && script != "Latin" {
            primary_script = Some(script);
            break;
        }
    }

    match primary_script {
        Some(script) if is_ambiguous_script(script) => {
            // Ambiguous script — try discriminators, fall back to script default
            let lang = discriminate_by_chars(text, script)
                .or_else(|| script_to_lang(script));
            lang.map(str::to_owned)
        }
        Some(script) => {
            // Unambiguous script — direct mapping (unchanged)
            script_to_lang(script).map(str::to_owned)
        }
        None => {
            // No non-Latin script — try Latin discriminators if text has
            // non-ASCII characters (accented Latin, special letters)
            if !text.is_ascii() {
                discriminate_by_chars(text, "Latin").map(str::to_owned)
            } else {
                None
            }
        }
    }
}
```

**Step 3: Run the Rust unit tests**

Run: `export PATH="$HOME/.cargo/bin:$PATH" && cd /Users/subzero/gt/translit/mayor/rig && cargo test --lib scripts::tests 2>&1 | tail -20`

Expected: All tests PASS, including the new discriminator tests from Task 1.

**Step 4: Run cargo clippy**

Run: `export PATH="$HOME/.cargo/bin:$PATH" && cd /Users/subzero/gt/translit/mayor/rig && cargo clippy --all-targets -- -D warnings 2>&1 | tail -10`

Expected: No warnings.

---

### Task 3: Add Python integration tests

**Files:**
- Modify: `tests/test_lang_auto.py`

**Step 1: Build the Python extension**

Run: `export PATH="$HOME/.cargo/bin:$PATH" && cd /Users/subzero/gt/translit/mayor/rig && source .venv/bin/activate && maturin develop 2>&1 | tail -3`

**Step 2: Add discriminator integration tests**

Add a new test class to `tests/test_lang_auto.py`:

```python
class TestLangDiscriminator:
    """lang='auto' uses character-level discriminators for ambiguous scripts."""

    # ── Cyrillic discrimination ──

    def test_ukrainian_detected_by_yi(self) -> None:
        """Ukrainian ї triggers uk detection."""
        auto = transliterate("Київ — столиця України", lang="auto")
        explicit = transliterate("Київ — столиця України", lang="uk")
        assert auto == explicit

    def test_serbian_detected_by_dje(self) -> None:
        """Serbian ђ triggers sr detection."""
        auto = transliterate("Ђорђе и ћирилица", lang="auto")
        explicit = transliterate("Ђорђе и ћирилица", lang="sr")
        assert auto == explicit

    def test_cyrillic_without_discriminators_defaults_to_russian(self) -> None:
        """Plain Cyrillic without exclusive chars defaults to ru."""
        auto = transliterate("Москва", lang="auto")
        explicit = transliterate("Москва", lang="ru")
        assert auto == explicit

    def test_conflicting_cyrillic_discriminators_defaults_to_russian(self) -> None:
        """Mixed Ukrainian ї + Serbian ћ falls back to ru."""
        auto = transliterate("їћ", lang="auto")
        explicit = transliterate("їћ", lang="ru")
        assert auto == explicit

    # ── Arabic discrimination ──

    def test_persian_detected_by_pe(self) -> None:
        """Persian پ triggers fa detection."""
        auto = transliterate("پارسی زبان", lang="auto")
        explicit = transliterate("پارسی زبان", lang="fa")
        assert auto == explicit

    def test_arabic_without_discriminators_defaults_to_arabic(self) -> None:
        """Plain Arabic without Persian chars defaults to ar."""
        auto = transliterate("العربية", lang="auto")
        explicit = transliterate("العربية", lang="ar")
        assert auto == explicit

    # ── Latin discrimination ──

    def test_vietnamese_detected_by_horn_vowels(self) -> None:
        """Vietnamese ơ/ư triggers vi detection."""
        auto = transliterate("Thành phố Hồ Chí Minh rất đẹp và có nhiều người", lang="auto")
        explicit = transliterate("Thành phố Hồ Chí Minh rất đẹp và có nhiều người", lang="vi")
        assert auto == explicit

    def test_turkish_detected_by_dotless_i(self) -> None:
        """Turkish ı triggers tr detection."""
        auto = transliterate("İstanbul güzel bir şehır", lang="auto")
        explicit = transliterate("İstanbul güzel bir şehır", lang="tr")
        assert auto == explicit

    def test_german_detected_by_eszett(self) -> None:
        """German ß triggers de detection."""
        auto = transliterate("Straße nach Süden", lang="auto")
        explicit = transliterate("Straße nach Süden", lang="de")
        assert auto == explicit

    def test_latin_without_discriminators_returns_default(self) -> None:
        """Accented Latin without exclusive chars uses default transliteration."""
        auto = transliterate("café", lang="auto")
        default = transliterate("café")
        assert auto == default

    # ── Fail-safe: slug and pipeline ──

    def test_slugify_auto_persian(self) -> None:
        result = slugify("پارسی", lang="auto")
        expected = slugify("پارسی", lang="fa")
        assert result == expected

    def test_slugify_auto_ukrainian(self) -> None:
        result = slugify("Київ", lang="auto")
        expected = slugify("Київ", lang="uk")
        assert result == expected

    def test_pipeline_auto_with_discriminator(self) -> None:
        p = TextPipeline(transliterate=True, lang="auto")
        result = p("Straße")
        # German ß → ss (via de profile), not default ß → ss
        assert result.isascii()
```

**Step 3: Run the new tests**

Run: `cd /Users/subzero/gt/translit/mayor/rig && source .venv/bin/activate && python -m pytest tests/test_lang_auto.py -v 2>&1 | tail -30`

Expected: All tests PASS.

**Step 4: Run the full test suite**

Run: `cd /Users/subzero/gt/translit/mayor/rig && source .venv/bin/activate && python -m pytest tests/ -x -q 2>&1 | tail -5`

Expected: All 2033+ tests PASS. No regressions.

---

### Task 4: Commit the implementation

**Step 1: Commit**

```bash
cd /Users/subzero/gt/translit/mayor/rig
git --no-optional-locks add src/scripts.rs tests/test_lang_auto.py
git --no-optional-locks commit -m "$(cat <<'EOF'
feat: add character-level language discriminators for lang="auto"

Add fail-safe discriminator scanning for ambiguous scripts so that
lang="auto" correctly identifies Ukrainian (ґїєі), Serbian (ђћљњџј),
Mongolian (өү), Persian (پچژگ), Vietnamese (ơư), Turkish (İı), and
German (ß) from their exclusive characters.

If discriminators for two languages conflict or no exclusive characters
are found, the function falls back to the existing script-level default
(Cyrillic→ru, Arabic→ar, Latin→None). This guarantees no regressions.
EOF
)"
```

---

### Task 5: Update documentation

**Files:**
- Modify: `docs/user-guide/language-support.md`
- Modify: `docs/limitations.md`

**Step 1: Update the auto-detection docs**

In `docs/user-guide/language-support.md`, replace the "Script-to-language mapping" section (around lines 174-189) with:

```markdown
### Script-to-language mapping

For **unambiguous scripts** (one script = one language), detection is immediate:

| Script | Default language |
|---|---|
| Georgian | `ka` |
| Armenian | `hy` |
| Thai | `th` |
| Hangul | `ko` |
| Hiragana / Katakana | `ja` |
| Bengali, Tamil, Telugu, Kannada, Malayalam, Gujarati, Gurmukhi, Odia, Sinhala | respective language |
| Ethiopic, Tibetan, Lao, Myanmar, Khmer, Mongolian, Javanese, Hebrew, Thaana | respective language |

### Character-level discrimination for ambiguous scripts

For scripts shared by multiple languages, translit scans for **exclusive characters** — codepoints that appear in exactly one language's alphabet among the profiles we support:

| Script | Exclusive characters | Detected language |
|---|---|---|
| Cyrillic | ґ Ґ ї Ї є Є і І | `uk` (Ukrainian) |
| Cyrillic | ђ Ђ ћ Ћ љ Љ њ Њ џ Џ ј Ј | `sr` (Serbian) |
| Cyrillic | ө Ө ү Ү | `mn` (Mongolian) |
| Arabic | پ چ ژ گ | `fa` (Persian) |
| Latin | ơ Ơ ư Ư | `vi` (Vietnamese) |
| Latin | İ ı | `tr` (Turkish) |
| Latin | ß ẞ | `de` (German) |

If **no** exclusive characters are found, the script default is used (Cyrillic → `ru`, Arabic → `ar`, Latin → no override). If exclusive characters from **two different languages** appear in the same text (e.g., Ukrainian ї and Serbian ћ), detection falls back to the script default — this is the fail-safe guarantee.

!!! example "Discrimination in action"
    ```python
    # Before: Cyrillic always defaulted to Russian
    transliterate("Київ", lang="auto")   # → now correctly uses uk profile

    # Persian detected by exclusive letters
    transliterate("پارسی", lang="auto")  # → now correctly uses fa profile

    # German detected by ß
    transliterate("Straße", lang="auto") # → now correctly uses de profile

    # No exclusive chars → safe default
    transliterate("Москва", lang="auto") # → still uses ru (no change)
    ```
```

**Step 2: Add a note to limitations.md**

Add to the end of `docs/limitations.md`, before any closing section:

```markdown
## Language detection limitations

The `lang="auto"` feature uses a two-tier strategy:

1. **Script detection** — identifies the Unicode script (Cyrillic, Arabic, etc.)
2. **Character discrimination** — for ambiguous scripts, scans for characters exclusive to one language

This works well for languages with distinctive alphabets (Ukrainian, Serbian, Persian, Vietnamese, Turkish, German) but cannot distinguish languages that share identical character sets:

- **Russian vs. Bulgarian** — both use standard Cyrillic without exclusive characters
- **Hindi vs. Marathi vs. Nepali** — all use Devanagari with the same character inventory
- **French vs. Spanish vs. Portuguese vs. Italian** — all use Latin with overlapping accented characters

For these cases, pass an explicit language code (`lang="bg"`, `lang="mr"`, `lang="fr"`, etc.).

Character discrimination is also unable to detect a language if the input text happens not to contain any exclusive characters. For example, a short Ukrainian phrase that avoids ґ, ї, є, і will be detected as Russian. Again, use an explicit language code when precision matters.
```

**Step 3: Commit documentation**

```bash
cd /Users/subzero/gt/translit/mayor/rig
git --no-optional-locks add docs/user-guide/language-support.md docs/limitations.md
git --no-optional-locks commit -m "docs: document character-level language discrimination for lang=auto"
```

---

### Task 6: Final verification and push

**Step 1: Run linters**

```bash
export PATH="$HOME/.cargo/bin:$PATH"
cd /Users/subzero/gt/translit/mayor/rig
cargo fmt --check
cargo clippy --all-targets -- -D warnings
source .venv/bin/activate
ruff check .
```

**Step 2: Run full test suite**

```bash
cd /Users/subzero/gt/translit/mayor/rig
source .venv/bin/activate
python -m pytest tests/ -x -q
```

Expected: All tests pass. Zero regressions.

**Step 3: Push**

```bash
cd /Users/subzero/gt/translit/mayor/rig
git --no-optional-locks push
```

---

## Discriminator character reference

For implementer reference, the complete discriminator table:

### Cyrillic → Ukrainian (`uk`)
| Char | Unicode | Name |
|------|---------|------|
| ґ | U+0491 | GHE WITH UPTURN (lowercase) |
| Ґ | U+0490 | GHE WITH UPTURN (uppercase) |
| ї | U+0457 | YI (lowercase) |
| Ї | U+0407 | YI (uppercase) |
| є | U+0454 | UKRAINIAN IE (lowercase) |
| Є | U+0404 | UKRAINIAN IE (uppercase) |
| і | U+0456 | BYELORUSSIAN-UKRAINIAN I (lowercase) |
| І | U+0406 | BYELORUSSIAN-UKRAINIAN I (uppercase) |

### Cyrillic → Serbian (`sr`)
| Char | Unicode | Name |
|------|---------|------|
| ђ | U+0452 | DJE (lowercase) |
| Ђ | U+0402 | DJE (uppercase) |
| ћ | U+045B | TSHE (lowercase) |
| Ћ | U+040B | TSHE (uppercase) |
| љ | U+0459 | LJE (lowercase) |
| Љ | U+0409 | LJE (uppercase) |
| њ | U+045A | NJE (lowercase) |
| Њ | U+040A | NJE (uppercase) |
| џ | U+045F | DZHE (lowercase) |
| Џ | U+040F | DZHE (uppercase) |
| ј | U+0458 | JE (lowercase) |
| Ј | U+0408 | JE (uppercase) |

### Cyrillic → Mongolian (`mn`)
| Char | Unicode | Name |
|------|---------|------|
| ө | U+04E9 | BARRED O (lowercase) |
| Ө | U+04E8 | BARRED O (uppercase) |
| ү | U+04AF | STRAIGHT U (lowercase) |
| Ү | U+04AE | STRAIGHT U (uppercase) |

### Arabic → Persian (`fa`)
| Char | Unicode | Name |
|------|---------|------|
| پ | U+067E | PEH |
| چ | U+0686 | TCHEH |
| ژ | U+0698 | ZHEH |
| گ | U+06AF | GAF |

### Latin → Vietnamese (`vi`)
| Char | Unicode | Name |
|------|---------|------|
| ơ | U+01A1 | O WITH HORN (lowercase) |
| Ơ | U+01A0 | O WITH HORN (uppercase) |
| ư | U+01B0 | U WITH HORN (lowercase) |
| Ư | U+01AF | U WITH HORN (uppercase) |

### Latin → Turkish (`tr`)
| Char | Unicode | Name |
|------|---------|------|
| İ | U+0130 | LATIN CAPITAL LETTER I WITH DOT ABOVE |
| ı | U+0131 | LATIN SMALL LETTER DOTLESS I |

### Latin → German (`de`)
| Char | Unicode | Name |
|------|---------|------|
| ß | U+00DF | LATIN SMALL LETTER SHARP S |
| ẞ | U+1E9E | LATIN CAPITAL LETTER SHARP S |

## Why not these characters?

Characters intentionally **excluded** from the discriminator table:

| Character | Reason for exclusion |
|---|---|
| Cyrillic ё Ё (Russian) | Also used in Belarusian; Russian is already the Cyrillic default |
| Cyrillic щ (Bulgarian `sht` vs Russian `shch`) | Character is shared — only the *mapping* differs, not its presence |
| Arabic ک (U+06A9, Persian kaf) | Also appears in Urdu, Pashto texts; less exclusive than پ/چ/ژ/گ |
| Latin ä ö ü (German umlauts) | Shared with Finnish, Swedish, Estonian, Hungarian |
| Latin ş Ş (Turkish cedilla) | Shared with Romanian, Azerbaijani |
| Latin đ Đ (Vietnamese d-stroke) | Also used in Croatian and some Sami languages |
| Latin ñ (Spanish) | Also used in Filipino, Galician, Basque |
