# Node API reference

The surface is a set of named exports from the `disarm` package plus the
[`DisarmError`](#errors) class hierarchy. Every function is a thin, idiomatic
TypeScript wrapper over the pure-Rust core (no Python): options are passed as an
object with the core's defaults, scheme/target tokens are typed string unions,
and bad input throws `DisarmInvalidArgument`. The binding is a deliberate
**subset** of the core — `mlNormalize` and the fluent `Text` builder are not
surfaced yet (the `canonicalize` / `stripObfuscation` presets and the
`getPipeline` policy registry are; see [Stability](#stability)).

For install and a five-line tour, start with
[disarm for Node.js](getting-started.md). The shared, language-neutral
explanation of *what* each operation does lives under **Concepts** and **Guide**
in the sidebar — this page is the call surface.

```ts
import * as disarm from 'disarm'
// or: import { transliterate, normalizeConfusables, … } from 'disarm'
```

Every example below is executed against the built addon in CI (the Node doc
gate), so the documented outputs cannot rot.

## Transliteration

### `transliterate(text, options?)`

Romanize Unicode text to ASCII. `options.scheme` is `'default'` (general-purpose),
`'strict_iso9'` (ISO 9:1995-style ASCII), or `'gost7034'` (GOST R 7.0.34).
`options.lang` applies a language profile on top of the scheme (`'uk'`, `'de'`,
…, or `'auto'` to detect). This is **phonetic romanization for legibility, not a
security control** — use [`normalizeConfusables`](#confusable-folding) for
homoglyph defence.

```ts
transliterate('café') // => 'cafe'
transliterate('Москва') // => 'Moskva'
transliterate('Київ', { lang: 'uk' }) // => 'Kyiv'
transliterate('Юрий', { scheme: 'strict_iso9' }) // => 'Jurij'
transliterate('Київ', { lang: 'auto' }) // => 'Kyiv'
```

## Indexing keys

### `searchKey(text, options?)` · `sortKey(text, options?)` · `catalogKey(text, options?)`

Derive stable lookup keys for search, ordering, and deduplication.
`searchKey` is a case/accent/script-insensitive search key; `sortKey` is a
collation key that **preserves base accented characters** (`café` stays `café`,
unlike `searchKey`'s folded `cafe`) while still folding non-Latin scripts to
Latin; `catalogKey` is a library-catalog dedup key (`searchKey` plus confusable
folding). `options.lang` selects the transliteration table (`'ru'`, `'de'`, …);
`catalogKey` also takes `options.strictIso9` to pick the ISO 9:1995 Cyrillic
scheme.

```ts
searchKey('Köln') // => 'koln'
searchKey('Москва', { lang: 'ru' }) // => 'moskva'
searchKey('café') // => 'cafe'
sortKey('café') // => 'café'
catalogKey('Толстой', { lang: 'ru' }) // => 'tolstoy'
```

## Confusable folding

### `normalizeConfusables(text, options?)`

Fold cross-script confusables toward `options.target` (`'latin'` default, or
`'cyrillic'`) using the TR39 visual mapping — the homoglyph defence.

```ts
normalizeConfusables('раypal') // => 'paypal'
```

### `isConfusable(text, options?)`

Whether `text` contains any character confusable with `options.target` (default
`'latin'`). A `false` asserts only that none of the bundled confusables were
found, not that the text is safe.

```ts
isConfusable('pаypal') // => true
isConfusable('paypal') // => false
```

## Slugs

### `slugify(text, options?)`

Generate a URL-safe slug. Mirrors the core's `SlugConfig` defaults; every option
is optional (`separator`, `lowercase`, `maxLength`, `wordBoundary`, `saveOrder`,
`stopwords`, `allowUnicode`, `lang`, `entities`, `decimal`, `hexadecimal`,
`safeChars`).

```ts
slugify('Héllo Wörld') // => 'hello-world'
slugify('café au lait') // => 'cafe-au-lait'
```

## Canonicalization primitives

### `stripAccents(text)` · `foldCase(text)` · `demojize(text, options?)`

Strip diacritics; full Unicode case fold (more aggressive than
`String.toLowerCase()`); and replace emoji with their plain names
(`options.stripModifiers` drops skin-tone/variation marks).

```ts
stripAccents('café') // => 'cafe'
foldCase('Straße') // => 'strasse'
demojize('Café ☕') // => 'Café hot beverage'
```

## Normalization

### `normalize(text, options?)` · `isNormalized(text, options?)`

Apply / test a Unicode normalization form. `options.form` is `'NFC'` (default),
`'NFD'`, `'NFKC'`, or `'NFKD'`.

```ts
normalize('ﬁ') // => 'ﬁ'
normalize('ﬁnance', { form: 'NFKC' }) // => 'finance'
normalize('2²', { form: 'NFKC' }) // => '22'
isNormalized('café', { form: 'NFC' }) // => true
isNormalized('ﬁ', { form: 'NFKC' }) // => false
```

## Text cleaning

### `collapseWhitespace(text)`

Collapse every run of Unicode whitespace to a single ASCII space and trim
leading/trailing whitespace. Folds **whitespace only** — the line controls
(TAB/LF/VT/FF/CR), the information separators (`U+001C`–`U+001F`), NEL, the
`Zs`/`Zl`/`Zp` spaces, and the blank-rendering set (Braille blank, the Hangul
fillers) each fold to a single space. It does **not** delete control or
zero-width characters — use `stripControlChars` / `stripZeroWidthChars` for that.
Folding (not deleting) the line controls means `'a\rb'` becomes `'a b'`, never
`'ab'`.

```ts
collapseWhitespace('  a   b ') // => 'a b'
```

### `stripControlChars(text)` · `stripZeroWidthChars(text)` · `stripBidi(text)`

Remove, respectively, C0/C1 control characters (except tab/newline), zero-width
characters (ZWSP/ZWNJ/ZWJ/word-joiner), and Unicode bidirectional controls — the
invisible characters used to obfuscate or spoof text.

```ts
stripControlChars('a\u0007b') // => 'ab'
stripZeroWidthChars('a\u200Bb') // => 'ab'
stripBidi('a\u202Eb') // => 'ab'
```

### `stripTags(text)` · `stripVariationSelectors(text)` · `stripNoncharacters(text)` · `stripPua(text)`

Strip the invisible / non-interchange code-point classes weaponized for "ASCII
smuggling" into LLMs and adjacent hygiene (#413): the Unicode **Tags** block
(preserving valid emoji flag sequences), every **variation selector**, every
**noncharacter**, and the **Private Use Area**. These are the composable
primitives behind the security presets, which strip them automatically.

```ts
stripTags('a\u{E0001}b') // => 'ab'
stripVariationSelectors('g\u{FE01}data') // => 'gdata'
stripNoncharacters('a\u{FFFE}b') // => 'ab'
stripPua('a\u{E000}b') // => 'ab'
```

### `stripZalgo(text, options?)` · `isZalgo(text, options?)`

`isZalgo` flags "zalgo" — combining marks stacked past `options.threshold` (3) on
a base character; `stripZalgo` caps each base at `options.maxMarks` (2).

```ts
isZalgo('Z\u0301\u0301\u0301\u0301') // => true
isZalgo(stripZalgo('Z\u0301\u0301\u0301\u0301')) // => false
```

## Deobfuscation & security presets

### `stripObfuscation(text)` · `canonicalize(text)`

`stripObfuscation` removes obfuscation (zero-width, bidi, combining-mark abuse,
homoglyphs) while keeping legible content — it does **not** transliterate.
`canonicalize` is the aggressive NFKC → strip-bidi → strip-invisibles →
strip-control/zero-width → collapse → cap-marks → NFC → confusables → NFC preset
(confusables sandwiched between NFC passes for idempotency).

```ts
stripObfuscation('рroduсt') // => 'product'
canonicalize('ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥') // => 'Real text'
```

### `sanitizeFilename(text, options?)`

Turn arbitrary text into a filesystem-safe filename. `options.platform` is
`'universal'` (default), `'windows'`, or `'posix'`; `options.preserveExtension`
(`true`) keeps the final extension when truncating to `options.maxLength`.

```ts
sanitizeFilename('My: report*.txt') // => 'My_report.txt'
sanitizeFilename('CON', { platform: 'windows' }) // => '_CON'
sanitizeFilename('Ärger.txt', { lang: 'de' }) // => 'Aerger.txt'
```

## Grapheme clusters

Operate on **user-perceived characters** rather than code points — an emoji, a
flag, or a base-plus-combining-mark counts as one.

### `graphemeLen(text)` · `graphemeSplit(text)` · `graphemeTruncate(text, maxGraphemes)`

```ts
graphemeLen('a👍b') // => 3
graphemeLen('🇬🇧') // => 1
graphemeSplit('a👍') // => ['a', '👍']
graphemeTruncate('héllo', 3) // => 'hél'
```

### `graphemeWidth(cluster, options?)` · `terminalWidth(text, options?)`

Display width in terminal columns by East Asian Width. Pass
`options.ambiguousWide: true` to count ambiguous-width characters as two columns.

```ts
graphemeWidth('👍') // => 2
terminalWidth('a👍') // => 3
terminalWidth('¡', { ambiguousWide: true }) // => 2
```

## Reverse transliteration & untranslatable scan

### `reverseTransliterate(text, options)`

Reverse-transliterate Latin back to a native script. `options.lang` is `'el'`
(Greek), `'ru'` (Russian), or `'uk'` (Ukrainian).

```ts
reverseTransliterate('Moskva', { lang: 'ru' }) // => 'Москва'
reverseTransliterate('Athina', { lang: 'el' }) // => 'Αθηνα'
```

### `findUntranslatable(text, options?)`

Every character with no romanization — the ones `transliterate` would replace —
as `{ char, offset }` objects (byte offset), in order. `options.scheme`/`lang`
mirror `transliterate`.

```ts
findUntranslatable('a\u{1F70A}') // => [{ char: '\u{1F70A}', offset: 1 }]
findUntranslatable('café') // => []
```

## Script analysis

### `detectScripts(text)` · `isMixedScript(text)` · `hasBidiConflict(text)`

The Unicode scripts present (first-appearance order, Common/Inherited excluded),
whether more than one is present, and whether the text mixes strong
left-to-right and strong right-to-left characters — the "BiDi Swap"
display-reorder precondition (fires on real letters, no `U+202x` override).

```ts
detectScripts('aМ') // => ['Latin', 'Cyrillic']
isMixedScript('aМ') // => true
hasBidiConflict('helloא') // => true   (Latin + Hebrew)
hasBidiConflict('helloМ') // => false  (Latin + Cyrillic, both LTR)
```

### `isSuspiciousHostname(host)`

Whether the hostname looks like a mixed-script / confusable / bidi-reorder IDN
spoof. Flags a mixed-script label, a Latin confusable, or a bidi-direction
conflict (the "BiDi Swap" precondition — an LTR brand label stacked on an RTL
domain). A `false` is not a safety guarantee — see the
[Threat Model](../THREAT_MODEL.md).

```ts
isSuspiciousHostname('pаypal.com') // => true
isSuspiciousHostname('varonis.com.ו.קום') // => true   (BiDi Swap)
isSuspiciousHostname('example.com') // => false
```

### `inspectAutoLang(text)`

Explain how `lang: 'auto'` detection resolves `text` — an object with `script` and
`chosenLang` (both `undefined` if undetected), the `reason`, and any
`discriminatorsHit`.

```ts
inspectAutoLang('Москва') // => { script: 'Cyrillic', chosenLang: 'ru', reason: 'script_default', discriminatorsHit: [] }
inspectAutoLang('Київ') // => { script: 'Cyrillic', chosenLang: 'uk', reason: 'discriminator', discriminatorsHit: ['ї'] }
```

### `langInfo(code)` · `scriptInfo(name)`

Look up static facts about a language profile or a Unicode script. `langInfo`
returns a `LangMeta` (`name`, `script`, `region`, `context`); `scriptInfo`
returns a `ScriptMeta` (`name`, `defaultLang`, `example`, `contextAware`). An
unknown `code`/`name` throws `DisarmInvalidArgument`.

```ts
langInfo('de').name // => 'German'
langInfo('ru').script // => 'Cyrillic'
scriptInfo('Cyrillic').defaultLang // => 'ru'
scriptInfo('Greek').example // => 'Ελληνικά'
```

### `listScripts()` · `listContextLangs()`

Enumerate, respectively, every Unicode script name known to the transliteration
tables and every language code that has a context-aware transliteration profile.

```ts
listScripts().includes('Latin') // => true
listContextLangs() // => ['ar', 'fa', 'he']
```

## Anomaly detection

### `hasAnomalies(text, lexicon?)` · `inspectAnomalies(text, lexicon?)`

Flag text carrying out-of-place characters that disguise a real word — a
cross-script homoglyph, leet, segmentation, a zero-width / bidi control, or zalgo.
Reports a technical fact, not intent. `lexicon` is a `Set` or array of common
words (used only by the leet and segmentation branches). `inspectAnomalies`
returns an `AnomalyReport` (`anomalous`, `kinds`, `findings` — each `{ kind,
token, start, end, detail, reason }` — and `reason`). See
[Anomaly Detection](../user-guide/anomaly-detection.md) for the detected classes.

```ts
hasAnomalies('get fr33 now', ['free'])       // => true
inspectAnomalies('paypаl', ['paypal']).kinds // => ['mixed_script']
```

## Errors

Everything disarm throws is a `DisarmError` (a subclass of `Error`), so a single
`instanceof DisarmError` catches the whole surface. Bad input — an unknown
scheme/target/form/platform token, etc. — throws the more specific
`DisarmInvalidArgument`.

| Class | Thrown for |
| --- | --- |
| `DisarmError` | Base class — `instanceof` this to catch everything. |
| `DisarmInvalidArgument` | An invalid argument (bad scheme/target/form/platform token). |

```ts
import { transliterate, DisarmError, DisarmInvalidArgument } from 'disarm'

try {
  transliterate('x', { scheme: 'klingon' })
} catch (e) {
  if (e instanceof DisarmInvalidArgument) console.warn(e.message)
}
```

## Policy pipelines

### `getPipeline(profile)` · `Pipeline#process`

Build a reusable, precompiled pipeline handle for a named policy profile, then
apply it to any number of inputs — the profile's steps are resolved and compiled
once with `getPipeline`, so each `pipe.process(...)` call only runs the
transforms. An unknown profile name throws `DisarmInvalidArgument`.

```ts
import { getPipeline } from 'disarm'

// Build the handle once, then reuse it across inputs:
//   const pipe = getPipeline('search_index')
//   pipe.process(input)
getPipeline('search_index').process('Café') // => 'cafe'
getPipeline('search_index').process('Москва') // => 'moskva'
```

## Malformed input (lone surrogates / invalid UTF-16)

Every text entry point sanitizes malformed input at the boundary with a uniform,
defined contract (shared with the Python and Ruby bindings) — see the
[Threat Model](../THREAT_MODEL.md#malformed-unicode-input-at-the-binding-boundary-469). A JS string with
broken UTF-16 (lone surrogates) is interpreted as **WTF-8 → UTF-8**: a well-formed
high+low pair recombines into its astral scalar, and each genuinely lone surrogate code
unit becomes exactly one `U+FFFD`. No call throws an encoding error on this input, and the
result equals the same call on the sanitized string.

The substituted `U+FFFD` is **terminal** — it neutralizes the malformed unit, it does
**not** recover the original bytes, so a token a surrogate was splitting stays split.
Valid input, astral characters included, is unaffected.

```ts
// a lone high surrogate becomes one U+FFFD (the call does not throw)
foldCase('a\uD800b') // => 'a�b'
// a well-formed high+low pair is read as its one astral scalar, not two U+FFFD
foldCase('😀') // => '\u{1F600}'
```

## Stability

The npm package version tracks the Rust crate and the Python/Ruby packages. The
binding inherits the core's behavioural guarantees and limits verbatim — read the
[Threat Model](../THREAT_MODEL.md) before relying on it in a security context, and
note that transliteration **output** is data-driven (Unicode tables, romanization
standards) and can change across releases without being treated as a breaking
change.

Not yet surfaced (compose the primitives, or reach for another binding): the
`mlNormalize` / `stripFormat` presets, the fluent `Text` builder, and the output
encoders / encoding family (`escapeHtml`, `percentEncode`, `stripLogInjection`,
`detectEncoding`, `decodeToUtf8`). In particular `stripLogInjection` — a
security-relevant control — is **not** available here; neutralize log-injection
at the sink, or use the Python binding. The `canonicalize` / `stripObfuscation`
presets and the `getPipeline` policy-profile registry **are** exposed — see
[Policy pipelines](#policy-pipelines).
