# translit for Security-Conscious Technologists

A guide to using translit for defending against Unicode-based attacks:
homoglyph phishing, invisible character injection, filename traversal,
WAF/filter bypass via encoding tricks, and input canonicalization.

Unicode's 150,000+ characters create a vast attack surface. Characters
that look identical can have different codepoints. Characters that are
invisible can be inserted between visible ones. Characters in one script
can masquerade as characters in another. translit provides compiled Rust
tools for detecting and neutralizing these threats.

---

## Homoglyph and IDN Phishing Detection

The most common Unicode attack: substituting visually identical characters
from a different script to create deceptive domain names, usernames, or
display text. Cyrillic а (U+0430) is pixel-identical to Latin a (U+0061)
in most fonts.

### Detecting the Attack

```python
from translit import is_confusable, is_mixed_script, detect_scripts

# "раypal.com" — Cyrillic р and а mixed with Latin
is_confusable("раypal.com")           # True
is_mixed_script("раypal.com")         # True
[s.value for s in detect_scripts("раypal.com")]
# ['Cyrillic', 'Latin']

# "gооgle.com" — Cyrillic о substituted for Latin o
is_confusable("gооgle.com")           # True
is_mixed_script("gооgle.com")         # True
[s.value for s in detect_scripts("gооgle.com")]
# ['Latin', 'Cyrillic']

# Legitimate single-script text
is_confusable("paypal.com")           # False
is_mixed_script("paypal.com")         # False
```

### Normalizing Confusables

Replace cross-script lookalikes with their Latin equivalents using the
Unicode TR39 confusables table:

```python
from translit import normalize_confusables

normalize_confusables("раypal.com")    # → "paypal.com"
normalize_confusables("gооgle.com")    # → "google.com"
```

### Domain Validation Pattern

```python
from translit import is_mixed_script, is_confusable, normalize_confusables

def validate_domain(domain: str) -> tuple[bool, str]:
    """Check domain for homoglyph attacks.

    Returns (is_safe, canonical_form).
    """
    if is_mixed_script(domain):
        canonical = normalize_confusables(domain)
        if canonical != domain:
            return False, canonical
    return True, domain

safe, canonical = validate_domain("раypal.com")
# safe=False, canonical="paypal.com"

safe, canonical = validate_domain("paypal.com")
# safe=True, canonical="paypal.com"
```

### Username / Display Name Validation

The same technique applies to user-facing text anywhere untrusted input
is displayed:

```python
from translit import is_mixed_script, detect_scripts

def flag_suspicious_username(username: str) -> dict:
    """Flag usernames with mixed scripts for review."""
    scripts = [s.value for s in detect_scripts(username)]
    return {
        "username": username,
        "scripts": scripts,
        "mixed": is_mixed_script(username),
        "script_count": len(scripts),
    }
```

translit detects 39 Unicode scripts, including all the ones commonly used
in homoglyph attacks: Latin, Cyrillic, Greek, Armenian, Georgian, Cherokee,
and various mathematical symbol blocks.

---

## Invisible Character Injection

Zero-width characters, bidirectional overrides, and other invisible
codepoints can be inserted into text to bypass filters, break parsers,
or create visually misleading output.

### What collapse_whitespace Strips

The `collapse_whitespace` function (with its default `strip_zero_width=True`)
removes these invisible characters:

| Character | Codepoint | Name | Stripped? |
|-----------|-----------|------|-----------|
| `\u200B`  | U+200B    | Zero Width Space | Yes |
| `\u200C`  | U+200C    | Zero Width Non-Joiner | Yes |
| `\u200D`  | U+200D    | Zero Width Joiner | Yes |
| `\uFEFF`  | U+FEFF    | Byte Order Mark / ZWNBSP | Yes |
| `\u2060`  | U+2060    | Word Joiner | Yes |

```python
from translit import collapse_whitespace

collapse_whitespace("admin\u200Buser")     # → "adminuser"
collapse_whitespace("admin\u200Cuser")     # → "adminuser"
collapse_whitespace("admin\u200Duser")     # → "adminuser"
collapse_whitespace("admin\uFEFFuser")     # → "adminuser"
collapse_whitespace("admin\u2060user")     # → "adminuser"
```

### What strip_control Strips

The `strip_control` step strips C0 control characters
(U+0000–U+001F except tab/newline/carriage-return)
and DEL (U+007F). It is automatically enabled when `collapse_whitespace=True`
(the default behavior), but can also be used independently:

```python
from translit import TextPipeline

pipe = TextPipeline(collapse_whitespace=True)

pipe("hello\x00world")    # → "helloworld"  (null byte stripped)
pipe("hello\x01world")    # → "helloworld"  (SOH stripped)
pipe("hello\x7Fworld")    # → "helloworld"  (DEL stripped)
```

### Characters That Require Additional Handling

Some potentially dangerous invisible characters are not stripped by the
default pipeline. If your threat model includes these, add explicit
filtering:

| Character | Codepoint | Name | In default pipeline? |
|-----------|-----------|------|---------------------|
| `\u00AD`  | U+00AD    | Soft Hyphen | No — NFKC preserves it |
| `\u202E`  | U+202E    | Right-to-Left Override | No |
| `\u202D`  | U+202D    | Left-to-Right Override | No |
| `\u200E`  | U+200E    | Left-to-Right Mark | No |
| `\u200F`  | U+200F    | Right-to-Left Mark | No |
| `\u2066`–`\u2069` | | Isolate controls | No |

translit provides `security_clean()` as a precompiled pipeline that handles
the full threat surface in a single call:

```python
from translit import security_clean

security_clean("admin\u202Euser")     # → "adminuser"
security_clean("pass\u00ADword")      # → "password"
security_clean("\u0440\u0430ypal")    # → "paypal"  (Cyrillic homoglyphs → Latin)
security_clean("\ufb01lter")          # → "filter"  (ligature bypass collapsed)
security_clean("admin\u200Buser")     # → "adminuser"  (ZWSP stripped)
```

### What `security_clean` Does Internally

The function executes a fixed four-stage Rust pipeline:

1. **NFKC normalization** — collapses fullwidth characters, ligatures,
   superscripts, and other compatibility variants to their canonical forms.
2. **Confusable normalization** — replaces cross-script homoglyphs with
   their Latin equivalents using Unicode TR39 tables.
3. **Strip bidi/format** — removes soft hyphens (U+00AD), LRM/RLM,
   bidi embeddings/overrides (U+202A–U+202E), and bidi isolates
   (U+2066–U+2069).
4. **Collapse whitespace** — merges runs of whitespace to single spaces,
   strips zero-width characters (ZWSP, ZWNJ, ZWJ, BOM, word joiner)
   and control characters.

This is the recommended entry point for any input validation or
canonicalization context. If you need a custom pipeline, you can still
assemble one with `TextPipeline` + `strip_bidi()`:

```python
from translit import TextPipeline, strip_bidi

pipe = TextPipeline(
    normalize="NFKC",
    confusables=True,
    collapse_whitespace=True,
)
result = strip_bidi(pipe(text))  # equivalent to security_clean(text)
```

---

## Filename Sanitization

User-uploaded filenames are a classic injection vector: path traversal,
null bytes, Windows reserved names, and overlong names.

### What sanitize_filename Handles

```python
from translit import sanitize_filename

# Path traversal
sanitize_filename("../../etc/passwd")     # → ".etcpasswd"
sanitize_filename("foo/../bar.txt")       # → "foo_._bar.txt"

# Null byte injection
sanitize_filename("file\x00name.txt")     # → "file_name.txt"

# Windows reserved names
sanitize_filename("CON")                  # → "_CON"
sanitize_filename("NUL.txt")             # → "_NUL.txt"
sanitize_filename("LPT1")               # → "_LPT1"
sanitize_filename("aux.pdf")            # → "_aux.pdf"

# Control characters and newlines
sanitize_filename("hello\nworld.txt")    # → "hello_world.txt"
sanitize_filename("hello\tworld.txt")    # → "hello_world.txt"

# Zero-width characters
sanitize_filename("file\u200B\u200Bname.txt")  # → "filename.txt"

# Empty / whitespace-only
sanitize_filename("")                    # → ""
sanitize_filename("   ")                 # → "_"
sanitize_filename("...")                 # → "_"

# Non-ASCII: transliterated to ASCII
sanitize_filename("résumé.pdf")          # → "resume.pdf"
```

### Cross-Platform Safety

The `platform="universal"` default applies the union of Linux, macOS, and
Windows filename restrictions. This ensures filenames are safe regardless
of where they end up:

```python
sanitize_filename("file:name.txt")       # → "file_name.txt"  (colon illegal on Windows)
sanitize_filename("file<name>.txt")      # → "file_name.txt"  (angle brackets illegal on Windows)
```

### NFC Normalization: The macOS/Linux/Windows Mismatch

`sanitize_filename()` applies NFC normalization as its very first step,
before transliteration or any other processing. This addresses a subtle
but real cross-platform bug.

macOS APFS stores filenames in NFD (decomposed) form internally. A file
created on macOS as `café.txt` is stored as `cafe\u0301.txt` (base `e` +
combining acute accent). Linux ext4 and Windows NTFS store whatever bytes
they receive — typically NFC (`caf\u00e9.txt`, precomposed é). The two
representations are semantically identical Unicode but differ as byte
sequences:

```python
from translit import sanitize_filename

# NFD input (as macOS APFS would produce internally)
sanitize_filename("caf\u0065\u0301.txt")   # → "cafe.txt"

# NFC input (as Linux/Windows would produce)
sanitize_filename("caf\u00e9.txt")         # → "cafe.txt"

# Both produce identical output — NFC normalization runs first
```

Without NFC normalization, a file synced from macOS to Linux via
Dropbox, rsync, or git could fail equality checks, break deduplication,
or create "phantom duplicates" that look identical in a directory listing
but differ at the byte level. By normalizing to NFC before
transliteration, `sanitize_filename()` guarantees that the same
human-readable filename always produces the same output, regardless of
which OS originally created it.

The same applies to any text with combining characters. German umlauts,
for instance, can be represented as a single precomposed codepoint
(NFC: ü = U+00FC) or as a base letter plus combining diaeresis
(NFD: u + U+0308). Without NFC normalization, these would take
different code paths through transliteration:

```python
# NFC: precomposed ü (single codepoint U+00FC)
sanitize_filename("M\u00fcnchen.txt")              # → "Munchen.txt"

# NFD: u + combining diaeresis (two codepoints)
sanitize_filename("Mu\u0308nchen.txt")             # → "Munchen.txt"

# Identical output — NFC normalization recomposes before transliterating
```

This matters in practice when files traverse cloud sync services
(Dropbox, iCloud, OneDrive), version control (git), or backup tools
(rsync, tar) that may silently convert between NFC and NFD. Without
normalization, the same human-readable filename could produce different
sanitized outputs depending on which OS it passed through — a subtle
source of deduplication failures and broken file references.

### Length Limits

The 255-byte limit is enforced by default, with extension-aware
truncation:

```python
sanitize_filename("a" * 300 + ".pdf", max_length=255)
# Truncates the stem, preserves the .pdf extension
```

---

## WAF and Filter Bypass via Unicode Encoding

Attackers use Unicode encoding tricks to bypass Web Application Firewalls,
input filters, and blocklists. NFKC normalization collapses these back to
their canonical forms before your filter runs.

### Fullwidth Character Bypass

Fullwidth Latin characters (U+FF01–U+FF5E) are visually similar to standard
ASCII but have different codepoints, bypassing naive string matching:

```python
from translit import normalize

# Bypass attempt: fullwidth "<script>"
normalize("＜script＞", form="NFKC")          # → "<script>"

# Bypass attempt: fullwidth SQL injection
normalize("ＳＥＬＥＣＴＦＲＯＭusers", form="NFKC")   # → "SELECTFROMusers"

# Bypass attempt: fullwidth path traversal
normalize("..／..／etc", form="NFKC")          # → "../../etc"
```

**Defense pattern:** NFKC-normalize all input before passing it to your
WAF or filter rules:

```python
from translit import TextPipeline

# Normalize before filtering
sanitize = TextPipeline(normalize="NFKC")

user_input = "..／..／etc／passwd"    # fullwidth slashes
normalized = sanitize(user_input)     # → "../../etc/passwd"
# Now your path-traversal filter catches it
```

### Ligature Bypass

The fi ligature (U+FB01) is a single codepoint that looks like "fi." An
attacker can use it to bypass a filter that blocks the literal string
"filter":

```python
normalize("ﬁlter", form="NFKC")     # → "filter"
```

### Superscript/Subscript Bypass

Numeric superscripts and subscripts normalize to standard digits:

```python
normalize("¹²³", form="NFKC")        # → "123"
normalize("H₂O", form="NFKC")        # → "H2O"
```

---

## Combining Character Abuse (Zalgo Text)

"Zalgo text" stacks dozens of combining diacritical marks on each
character, creating visual noise that can break layouts, overwhelm parsers,
or bypass content filters.

### Detection

```python
from translit import is_zalgo

is_zalgo("café")                   # False (1 combining mark — normal)
is_zalgo("Việt Nam")               # False (2 marks — normal)
is_zalgo("ḧ̸̡̢̧̛̗̱́̑̾̊̿̏̒̓̕ě̵̢̧̛̗̱̈́̑̾̊̿̏̒̓̕l̸̡̢̧̛̗̱̈́̑̾̊̿̏̒̓̕l̸̡̢̧̛̗̱̈́̑̾̊̿̏̒̓̕o")   # True
```

The `threshold` parameter (default: 3) controls how many consecutive
combining marks per base character are tolerated before flagging as zalgo.
Vietnamese `ệ` has 2 marks in NFD — the default is safe for all
legitimate scripts.

### Stripping (preserving legitimate diacritics)

```python
from translit import strip_zalgo

# Caps combining marks at max_marks per base character (default: 2)
strip_zalgo("café")                # → "café"  (1 mark — preserved)
strip_zalgo("Việt Nam")            # → "Việt Nam"  (2 marks — preserved)
# Zalgo stacking stripped to max 2 marks per base character
```

Unlike `strip_accents()` which removes **all** combining marks,
`strip_zalgo()` preserves legitimate diacritics and only removes the
excess.  Use `strip_accents()` when you want a fully ASCII-compatible
result; use `strip_zalgo()` when you want to preserve the original script
while neutralizing abuse.

### Nuclear option

```python
from translit import strip_accents

# Removes ALL combining marks — appropriate for search keys, not display
strip_accents("h̵e̵l̵l̵o̵")       # → "hello"
```

---

## Input Canonicalization Pipeline

For user-submitted input that must be stored and displayed safely, use
the precompiled `sanitize_user_input()` pipeline. It preserves the
original script while neutralizing common attack vectors:

```python
from translit import sanitize_user_input

sanitize_user_input("раypal")              # → "paypal" (homoglyph neutralized)
sanitize_user_input("admin\u200Buser")     # → "adminuser" (zero-width stripped)
sanitize_user_input("admin\u202Euser")     # → "adminuser" (bidi override stripped)
sanitize_user_input("ﬁlter")              # → "filter" (NFKC normalized)
```

Pipeline: `NFKC → strip_zalgo → confusables → strip_bidi → collapse_whitespace`

For security-critical contexts where you need even more control, use
`security_clean()` (which skips zalgo stripping but otherwise follows
the same pattern) or build a custom pipeline:

```python
from translit import TextPipeline

security_pipe = TextPipeline(
    normalize="NFKC",         # Collapse encoding tricks
    confusables=True,         # Neutralize homoglyphs
    collapse_whitespace=True, # Strip invisible chars + normalize spaces
)

security_pipe("раypal")              # → "paypal"
security_pipe("admin\u200Buser")     # → "adminuser"
security_pipe("ﬁlter")              # → "filter"
```

### Recommended Pipeline Configurations by Context

**Username / display name validation:**
```python
from translit import sanitize_user_input

# Handles zalgo, homoglyphs, bidi, zero-width, and control chars
clean_name = sanitize_user_input(raw_input)
```

**Search query sanitization:**
```python
from translit import search_key

# NFKC → transliterate → strip_accents → fold_case → collapse_ws
normalized = search_key(query)
```

**Log entry canonicalization:**
```python
pipe = TextPipeline(
    normalize="NFKC",
    collapse_whitespace=True,
)
```

**Pre-WAF input normalization:**
```python
pipe = TextPipeline(
    normalize="NFKC",
)
```

---

## Comparison: is_ascii as a Quick Gate

Before running expensive normalization, `is_ascii()` provides an O(n)
check that short-circuits processing for ASCII-only input:

```python
from translit import is_ascii

def process_input(text: str) -> str:
    if is_ascii(text):
        return text  # No Unicode tricks possible
    return security_pipe(text)
```

Note: this is a performance optimization only. ASCII-only text can still
contain injection attacks via control characters (null bytes, newlines),
which `is_ascii` does not check for.

---

## Script-Based Threat Classification

translit's script detection provides a foundation for risk scoring based on
the Unicode scripts present in input text:

```python
from translit import detect_scripts, is_mixed_script

def assess_unicode_risk(text: str) -> dict:
    scripts = [s.value for s in detect_scripts(text)]
    mixed = is_mixed_script(text)

    # Single-script text in common scripts is low risk
    # Mixed-script text is suspicious
    # Certain script combinations are high risk (Cyrillic+Latin, Greek+Latin)
    HIGH_RISK_COMBOS = [
        {"Cyrillic", "Latin"},
        {"Greek", "Latin"},
    ]

    risk = "low"
    if mixed:
        risk = "medium"
        script_set = set(scripts)
        if any(combo.issubset(script_set) for combo in HIGH_RISK_COMBOS):
            risk = "high"

    return {
        "scripts": scripts,
        "mixed": mixed,
        "risk": risk,
    }

assess_unicode_risk("paypal.com")
# {'scripts': ['Latin'], 'mixed': False, 'risk': 'low'}

assess_unicode_risk("раypal.com")
# {'scripts': ['Cyrillic', 'Latin'], 'mixed': True, 'risk': 'high'}
```

### Hostname Validation: `is_safe_hostname()`

For domain/hostname validation specifically, translit provides a dedicated
function that combines mixed-script detection, confusable checking, and
canonical form generation:

```python
from translit import is_safe_hostname

safe, details = is_safe_hostname("paypal.com")
# safe=True, details.scripts=['Latin'], details.canonical='paypal.com'

safe, details = is_safe_hostname("\u0440\u0430ypal.com")
# safe=False, details.has_confusables=True, details.canonical='paypal.com'

safe, details = is_safe_hostname("g\u043e\u043egle.com")
# safe=False, details.canonical='google.com'
```

The `details` object exposes `.safe`, `.scripts`, `.mixed_script`,
`.has_confusables`, and `.canonical` — enough to decide whether to block,
warn, or log the input.

---

## Grapheme-Safe Length Limits

When enforcing character limits on usernames, display names, or form
fields, byte-level or codepoint-level truncation can corrupt emoji,
combining sequences, or Hangul syllables. Use `grapheme_truncate()`:

```python
from translit import grapheme_len, grapheme_truncate

# A family emoji is 1 user-perceived character but 7 codepoints / 25 bytes
family = "\U0001F469\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466"
grapheme_len(family)                     # → 1
grapheme_truncate(family + " hi", 3)     # → "👩‍👩‍👧‍👦 h" (keeps the emoji intact)

# NFD-decomposed text with combining accents
grapheme_len("cafe\u0301")              # → 4 (not 5)
grapheme_truncate("cafe\u0301s", 4)     # → "café" (combining accent kept with e)
```

This prevents the class of bugs where a field limit of "32 characters"
rejects valid usernames containing emoji or combining characters.

---

## What translit Does NOT Handle

translit is a text normalization library, not a complete security solution.
It does not address:

- **SQL injection, XSS, or command injection** — use parameterized queries,
  output encoding, and input validation appropriate to your framework.
  translit's NFKC normalization ensures your filter rules see canonical
  forms, but it does not implement the filter rules themselves.
- **Punycode / IDN resolution** — translit operates on Unicode text. For
  domain validation, decode Punycode (ACE) labels to Unicode first, then
  apply translit's `is_safe_hostname()` for confusable detection.
- **WTF-8 / unpaired surrogates** — NTFS allows filenames with unpaired
  UTF-16 surrogates that cannot be represented in valid UTF-8. Rust (and
  therefore translit) enforces valid UTF-8 strings. If you need to process
  Windows filenames with invalid surrogates, use `decode_to_utf8()` with
  lossy conversion before passing to translit.
- **Rate limiting, authentication, or authorization** — translit normalizes
  text; access control is a separate concern.

---

## Performance

All operations are compiled Rust with O(1) PHF (perfect hash function)
lookups. There is no regex compilation, no runtime data loading, and no
Python-level per-character iteration. The `TextPipeline` pre-compiles its
step configuration at construction time.

For security-critical paths (authentication, logging, WAF preprocessing),
translit adds negligible latency compared to the I/O it sits behind.

---

## Installation

```bash
pip install translit-rs
```

Single wheel per platform (abi3). No Rust toolchain required. No runtime
data downloads. No network calls during import. No native dependencies
beyond libc.
