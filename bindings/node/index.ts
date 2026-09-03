/**
 * disarm for Node.js — Unicode confusable/text-security building blocks, powered
 * by a pure-Rust core (#44).
 *
 * This is the idiomatic TypeScript layer over the raw napi binding (`./binding`):
 * it adds options objects with sensible defaults, string-union token types, and a
 * native {@link DisarmError} class. The behaviour is defined once in the Rust core
 * and inherited here — see https://docs.disarm.dev for the language-neutral guides.
 */
import * as native from './binding'
import { Lexicon, Pipeline } from './binding'
import type {
  Untranslatable,
  UnmappedConfusable,
  AutoLangInspection,
  KeyCollision,
  LangMeta,
  ScriptMeta,
  Finding as NativeFinding,
  AnomalyReport as NativeAnomalyReport,
  HostnameAnalysis as NativeHostnameAnalysis,
} from './binding'

export type {
  Untranslatable,
  UnmappedConfusable,
  AutoLangInspection,
  KeyCollision,
  LangMeta,
  ScriptMeta,
}

/** Findings from {@link analyzeHostname}. `suspicious` is a maximally
 * conservative screen, not a precise verdict (#549). */
export type HostnameAnalysis = NativeHostnameAnalysis

/**
 * A reusable, opaque lexicon handle (HAI-SDLC 6.1). `hasAnomalies` /
 * `inspectAnomalies` rebuild an internal set from the caller's word array on
 * every call; constructing a `Lexicon` once (`new Lexicon([...])`) and passing
 * it instead builds that set a single time and reuses it across calls.
 */
export { Lexicon }

/**
 * A reusable, opaque named-policy-profile pipeline handle (#404). Build it once
 * with {@link getPipeline} for a named profile, then apply it to any number of
 * inputs via `.process(text)` — the profile's steps are validated and compiled
 * a single time and reused across calls, rather than re-resolved each call.
 *
 * ```ts
 * const pipe = getPipeline('search_index') // build once
 * pipe.process('Café')   // → 'cafe'
 * pipe.process('Москва') // → 'moskva'   (same handle, many inputs)
 * ```
 */
export { Pipeline }

/** The anomaly branch that fired for a finding. */
export type AnomalyKind = 'invisible' | 'bidi' | 'bidi_mixed' | 'zalgo' | 'mixed_script' | 'leet' | 'segmentation' | 'control' | 'compat_fold' | 'confusable' | 'enclosing_mark' | 'mixed_numbers' | 'duplicate_mark' | 'deletion' | 'smuggled'

/**
 * One reason a token is anomalous. Re-typed over the generated {@link NativeFinding}
 * so `kind` is the {@link AnomalyKind} string-union rather than a bare `string`.
 */
export type Finding = Omit<NativeFinding, 'kind'> & { kind: AnomalyKind }

/** Structured anomaly report, with {@link Finding}s carrying a typed `kind`. */
export type AnomalyReport = Omit<NativeAnomalyReport, 'findings'> & { findings: Finding[] }

// ── Errors ──────────────────────────────────────────────────────────────────

/** Base class for every error disarm raises, so callers can `catch (e) { if (e instanceof DisarmError) … }`. */
export class DisarmError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'DisarmError'
  }
}

/** An invalid argument — an unknown scheme/target/form/platform token, etc. */
export class DisarmInvalidArgument extends DisarmError {
  constructor(message: string) {
    super(message)
    this.name = 'DisarmInvalidArgument'
  }
}

const INVALID_ARG_TAG = 'DisarmInvalidArgument: '
const ERROR_TAG = 'DisarmError: '

/**
 * Run a native call, re-raising its tagged napi error as the matching
 * `DisarmError` subclass. The native shim prefixes fallible messages with
 * `"DisarmInvalidArgument: "` or `"DisarmError: "`; we strip the matched tag
 * cleanly. Any other throw — an untagged `Error`, or a non-`Error` value — is
 * still wrapped as a `DisarmError` so nothing leaks out unwrapped.
 */
function call<T>(fn: () => T): T {
  try {
    return fn()
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    if (msg.startsWith(INVALID_ARG_TAG)) {
      throw new DisarmInvalidArgument(msg.slice(INVALID_ARG_TAG.length))
    }
    if (msg.startsWith(ERROR_TAG)) {
      throw new DisarmError(msg.slice(ERROR_TAG.length))
    }
    throw new DisarmError(msg)
  }
}

// ── Token types ─────────────────────────────────────────────────────────────

/** Transliteration scheme: the general-purpose default, ISO 9-style ASCII, or GOST R 7.0.34. */
export type Scheme = 'default' | 'strict_iso9' | 'gost7034'
/** Confusable-folding target script. */
export type TargetScript = 'latin' | 'cyrillic'

/**
 * How the fold treats non-Latin digits.
 *
 * `'numeric'` (default) sends them to the ASCII digit — `०` becomes `0` — which is right
 * for prose. `'tr39'` uses upstream's targets, which send most of them to a Latin letter
 * (`०` → `o`), and that is what an identifier *skeleton* wants. The two differ on 45 rows.
 *
 * Three of those rows do not land on a letter: `٠` and `۰` fold to `.`, and `𑣣` folds to
 * the two characters `rn`. A skeleton feeding a label- or path-shaped key has to allow
 * for that extra `.`.
 *
 * Scoped to `target: 'latin'`: the override rows are generated from the Latin table and
 * carry TR39's Latin-script targets, so with `target: 'cyrillic'` the option is a no-op.
 *
 * `'preserve'` leaves the digit alone (#648). The other two both rewrite a non-Latin
 * numeral and neither keeps the script — `२०२४` becomes `२0२४` or `२o२४`, both
 * mixed-script. This one applies under every target script.
 */
export type DigitPolicy = 'numeric' | 'tr39' | 'preserve'
/** Unicode normalization form. */
export type NormalizationForm = 'NFC' | 'NFD' | 'NFKC' | 'NFKD'
/** Filename-safety platform ruleset. */
export type Platform = 'universal' | 'windows' | 'posix'
/** Reverse-transliteration target language. */
export type ReverseLang = 'el' | 'ru' | 'uk'

// ── Transliteration ─────────────────────────────────────────────────────────

export interface TransliterateOptions {
  /** The scheme (default: `'default'`). */
  scheme?: Scheme
  /** A language profile applied on top of the scheme (e.g. `'uk'`, `'de'`, or `'auto'`). */
  lang?: string
}

/** Romanize Unicode text to ASCII. */
export function transliterate(text: string, options: TransliterateOptions = {}): string {
  const { scheme = 'default', lang } = options
  if (scheme === 'default' && lang == null) {
    return native.transliterate(text)
  }
  return call(() => native.transliterateOpts(text, scheme, lang ?? undefined))
}

/** Reverse-transliterate Latin back to a native script (`'el'`, `'ru'`, or `'uk'`). */
export function reverseTransliterate(text: string, options: { lang: ReverseLang }): string {
  return call(() => native.reverseTransliterate(text, options.lang))
}

/** Every character in `text` with no romanization, as `{ char, offset }` (byte offset), in order. */
export function findUntranslatable(
  text: string,
  options: TransliterateOptions = {},
): Untranslatable[] {
  const { scheme = 'default', lang } = options
  return call(() => native.findUntranslatable(text, scheme, lang ?? undefined))
}

// ── Confusables (TR39) ──────────────────────────────────────────────────────

/** Fold cross-script confusables toward `target` (default `'latin'`). */
export function normalizeConfusables(
  text: string,
  options: { target?: TargetScript; digitPolicy?: DigitPolicy } = {},
): string {
  return call(() =>
    native.normalizeConfusables(text, options.target ?? 'latin', options.digitPolicy ?? 'numeric'),
  )
}

/** Whether `text` contains a character confusable with `target` (default `'latin'`). */
export function isConfusable(text: string, options: { target?: TargetScript } = {}): boolean {
  return call(() => native.isConfusable(text, options.target ?? 'latin'))
}

/**
 * Every upstream confusable source the bundled `target` table does not fold.
 *
 * Read as exposure, not as a score — this is where an adaptive attacker goes when the
 * mapped sources stop working. Note it includes five ASCII characters (`%`, `0`, `1`,
 * `I`, `m`): TR39 is a skeleton transform, and disarm deliberately does not apply those
 * rows because folding a legitimate `m` to `rn` corrupts prose.
 */
export function unmappedConfusables(options: { target?: TargetScript } = {}): Set<string> {
  return new Set(call(() => native.unmappedConfusables(options.target ?? 'latin')))
}

/**
 * Confusable sources in `text` the bundled `target` table does not fold, as
 * `{ char, offset }` (byte offset), in order — the confusables analogue of
 * {@link findUntranslatable}.
 */
export function findUnmappedConfusables(
  text: string,
  options: { target?: TargetScript } = {},
): UnmappedConfusable[] {
  return call(() => native.findUnmappedConfusables(text, options.target ?? 'latin'))
}

// ── Slugs ───────────────────────────────────────────────────────────────────

export interface SlugifyOptions {
  separator?: string
  lowercase?: boolean
  maxLength?: number
  wordBoundary?: boolean
  saveOrder?: boolean
  stopwords?: string[]
  allowUnicode?: boolean
  lang?: string
  entities?: boolean
  decimal?: boolean
  hexadecimal?: boolean
  safeChars?: string
}

/** Generate a URL-safe slug. Mirrors the core's `SlugConfig` defaults. */
export function slugify(text: string, options: SlugifyOptions = {}): string {
  return call(() =>
    native.slugify(text, {
      separator: options.separator ?? '-',
      lowercase: options.lowercase ?? true,
      maxLength: options.maxLength ?? 0,
      wordBoundary: options.wordBoundary ?? false,
      saveOrder: options.saveOrder ?? false,
      stopwords: options.stopwords ?? [],
      allowUnicode: options.allowUnicode ?? false,
      lang: options.lang,
      entities: options.entities ?? true,
      decimal: options.decimal ?? true,
      hexadecimal: options.hexadecimal ?? true,
      safeChars: options.safeChars ?? '',
    }),
  )
}

// ── Canonicalization primitives ─────────────────────────────────────────────

/** Strip diacritics (`"café"` → `"cafe"`). */
export function stripAccents(text: string): string {
  return native.stripAccents(text)
}

/** Full Unicode case fold — more aggressive than `String.toLowerCase()`. */
export function foldCase(text: string): string {
  return native.foldCase(text)
}

/**
 * Whether `text` is a stable identity key under case folding — that is, whether
 * {@link foldCase} and `String.toLowerCase()` agree on it (#619).
 *
 * `false` means some *other* string folds to the same value, so a table keyed on
 * this one can collide: `'groß.txt'` and `'gross.txt'` are the pair node-tar
 * collided on (CVE-2026-23950). It is a fact about the string and not an
 * accusation — `groß` is an ordinary German word — so it is deliberately not
 * folded into {@link hasAnomalies}.
 */
export function isCaseFoldStable(text: string): boolean {
  return native.isCaseFoldStable(text)
}

/** Which reducer {@link findKeyCollisions} builds its keys with. No default: the
 * choice is the policy. */
export type CollisionKey =
  | 'fold_case'
  | 'search_key'
  | 'catalog_key'
  | 'canonicalize'
  | 'canonicalize_strict'
  | 'normalize_confusables'

/**
 * Which of `values` are the same name under `key` (#620).
 *
 * Every other disarm detector is a single-string predicate, and a collision is not
 * a property of a single string — `groß.txt` is an ordinary German filename, and
 * `аdmin` is only a problem next to `admin`. This is the set-shaped question that
 * node-tar's `PathReservations` guard failed to ask before extracting two paths in
 * parallel (CVE-2026-23950).
 *
 * A stronger `key` finds more collisions, including ones nobody attacked:
 * `search_key` collides `Muller` with `Müller`. That is the cost of the key you
 * chose, not a false positive. A group is reported only when two or more *distinct*
 * inputs share a key; the same name twice is the same name twice.
 *
 * `options.lang` reaches `search_key` and `catalog_key` and is ignored by the rest.
 */
export function findKeyCollisions(
  values: string[],
  key: CollisionKey,
  options: { lang?: string } = {},
): KeyCollision[] {
  return call(() => native.findKeyCollisions(values, key, options.lang))
}

/** Replace emoji with their plain names. `stripModifiers` drops skin-tone/variation marks. */
export function demojize(text: string, options: { stripModifiers?: boolean } = {}): string {
  return native.demojize(text, options.stripModifiers ?? false)
}

// ── Normalization ───────────────────────────────────────────────────────────

/** Apply a Unicode normalization `form` (default `'NFC'`). */
export function normalize(text: string, options: { form?: NormalizationForm } = {}): string {
  return call(() => native.normalize(text, options.form ?? 'NFC'))
}

/** Whether `text` is already in normalization `form` (default `'NFC'`). */
export function isNormalized(text: string, options: { form?: NormalizationForm } = {}): boolean {
  return call(() => native.isNormalized(text, options.form ?? 'NFC'))
}

// ── Text cleaning ───────────────────────────────────────────────────────────

/**
 * Fold Unicode whitespace runs to single ASCII spaces and trim the ends (#433).
 *
 * Folds whitespace ONLY — the line controls (TAB/LF/VT/FF/CR), the information
 * separators (U+001C–U+001F), NEL, the Zs/Zl/Zp spaces, and the blank-rendering
 * set (Braille blank, Hangul fillers) each fold to a single space. It does NOT
 * delete control or zero-width characters — use `stripControlChars` /
 * `stripZeroWidthChars` for that. Folding the line controls (rather than
 * deleting them) means `a\rb` → `a b`, never `ab`.
 */
export function collapseWhitespace(text: string): string {
  return native.collapseWhitespace(text)
}

/** Remove C0/C1 control characters (except tab/newline). */
export function stripControlChars(text: string): string {
  return native.stripControlChars(text)
}

/** Remove zero-width characters (ZWSP/ZWNJ/ZWJ/word-joiner). */
export function stripZeroWidthChars(text: string): string {
  return native.stripZeroWidthChars(text)
}

/** Remove Unicode bidirectional control characters. */
export function stripBidi(text: string): string {
  return native.stripBidi(text)
}

/** Strip the Unicode Tags block (U+E0000–U+E007F), preserving valid emoji flag sequences (#413). */
export function stripTags(text: string): string {
  return native.stripTags(text)
}

/** Strip every variation selector (VS1–VS256) (#413). */
export function stripVariationSelectors(text: string): string {
  return native.stripVariationSelectors(text)
}

/** Strip every Unicode noncharacter (#413). */
export function stripNoncharacters(text: string): string {
  return native.stripNoncharacters(text)
}

/** Strip every Private Use Area code point (#413). */
export function stripPua(text: string): string {
  return native.stripPua(text)
}

/** Cap combining marks per base character at `maxMarks` (default `2`). */
export function stripZalgo(text: string, options: { maxMarks?: number } = {}): string {
  return call(() => native.stripZalgo(text, options.maxMarks ?? 2))
}

/** Whether any base character carries more than `threshold` (default `3`) combining marks. */
export function isZalgo(text: string, options: { threshold?: number } = {}): boolean {
  return call(() => native.isZalgo(text, options.threshold ?? 3))
}

// ── Deobfuscation & security presets ────────────────────────────────────────

/**
 * Canonicalize, but throw rather than silently normalize a structural difference away —
 * the half of the pair that lets a caller reject input instead of comparing a value the
 * sender never wrote.
 */
export function canonicalizeStrict(text: string): string {
  return call(() => native.canonicalizeStrict(text))
}

/**
 * Strip the non-interchange and invisible classes while KEEPING the script.
 *
 * Unlike {@link canonicalize} it folds no confusables, so non-Latin text survives as
 * itself. It cannot be rebuilt from the seven universal `strip*` functions, and the
 * difference runs both ways: this preserves the Private Use Area (icon fonts) and keeps
 * the VS15/VS16 presentation selectors after a base, which the naive chain deletes, and
 * it collapses TAB/LF to a space, which the primitives leave alone. Infallible.
 */
export function stripFormat(text: string): string {
  return native.stripFormat(text)
}

/** Remove obfuscation (zero-width, bidi, combining-mark abuse, homoglyphs) while keeping legible content. */
export function stripObfuscation(text: string): string {
  return call(() => native.stripObfuscation(text))
}

/**
 * Canonicalize text for security-sensitive comparison: NFKC → strip bidi/format
 * → strip invisible classes (#413) → strip control → strip zero-width → collapse
 * whitespace → cap combining marks (anti-zalgo) → NFC → confusables → NFC
 * (confusables sandwiched between NFC passes for idempotency).
 *
 * The name describes the mechanism (Unicode canonicalization for matching), not
 * a safety guarantee — this is not an output sanitizer; encode at the sink.
 */
export function canonicalize(text: string): string {
  return call(() => native.canonicalize(text))
}

/**
 * @deprecated Renamed to {@link canonicalize} in 0.11 (the `*Clean` name
 * overpromised safety); removed in 1.0.
 */
export function securityClean(text: string): string {
  return canonicalize(text)
}

/**
 * Build a reusable {@link Pipeline} handle for a named policy profile (#404).
 * Resolve and compile the profile's steps once here, then call `.process(text)`
 * on the returned handle for each input — the per-call cost is just running the
 * already-compiled steps, not re-resolving the profile (mirrors {@link Lexicon}).
 *
 * An unknown `profile` throws {@link DisarmInvalidArgument} (naming the
 * available profiles).
 */
export function getPipeline(profile: string): Pipeline {
  return call(() => native.getPipeline(profile))
}

export interface SanitizeFilenameOptions {
  separator?: string
  maxLength?: number
  platform?: Platform
  lang?: string
  preserveExtension?: boolean
}

/** Turn arbitrary text into a filesystem-safe filename. */
export function sanitizeFilename(text: string, options: SanitizeFilenameOptions = {}): string {
  return call(() =>
    native.sanitizeFilename(
      text,
      options.separator ?? '_',
      options.maxLength ?? 255,
      options.platform ?? 'universal',
      options.lang ?? undefined,
      options.preserveExtension ?? true,
    ),
  )
}

// ── Key-derivation presets ──────────────────────────────────────────────────

/**
 * Case/accent/script-insensitive search lookup key (like {@link catalogKey}
 * without confusable folding). `lang` selects the transliteration table.
 */
export function searchKey(text: string, options: { lang?: string } = {}): string {
  return call(() => native.searchKey(text, options.lang ?? undefined))
}

/**
 * Collation sort key — like {@link searchKey} but preserves base accented
 * characters for correct ordering. `lang` selects the transliteration table.
 */
export function sortKey(text: string, options: { lang?: string } = {}): string {
  return call(() => native.sortKey(text, options.lang ?? undefined))
}

/**
 * Library catalog deduplication key — like {@link searchKey} plus confusable
 * folding. `lang` selects the transliteration table; `strictIso9` (default
 * `false`) picks the ISO 9:1995 Cyrillic scheme.
 */
export function catalogKey(
  text: string,
  options: { lang?: string; strictIso9?: boolean } = {},
): string {
  return call(() => native.catalogKey(text, options.lang ?? undefined, options.strictIso9 ?? false))
}

/** Options for {@link mlNormalize}. */
export interface MlNormalizeOptions {
  /** Language code selecting the transliteration table; omit for none. */
  lang?: string
  /** `'cldr'` (default) expands emoji to CLDR short names; `'none'` leaves them. */
  emojiStyle?: 'cldr' | 'none'
  /**
   * Apply Unicode case folding (default `true`).
   *
   * Pass `false` in front of a **cased** model: folding is destructive, cannot be undone
   * downstream, and an uncased evaluation harness cannot measure what it cost. It
   * restores case, not diacritics — accents are still stripped.
   */
  foldCase?: boolean
}

/**
 * ML/NLP normalization: NFKC → emoji→text → transliterate → strip accents →
 * [case fold] → strip control → strip zero-width → collapse whitespace.
 *
 * Note this folds no confusables — it is not a homoglyph defence at any setting. Put
 * {@link normalizeConfusables} in front of it when a model needs both.
 */
export function mlNormalize(text: string, options: MlNormalizeOptions = {}): string {
  return call(() =>
    native.mlNormalize(
      text,
      options.lang ?? undefined,
      options.emojiStyle ?? 'cldr',
      options.foldCase ?? true,
    ),
  )
}

// ── Grapheme clusters ───────────────────────────────────────────────────────

/** Number of grapheme clusters (user-perceived characters). */
export function graphemeLen(text: string): number {
  return native.graphemeLen(text)
}

/** Split `text` into grapheme-cluster strings. */
export function graphemeSplit(text: string): string[] {
  return native.graphemeSplit(text)
}

/** Truncate to at most `maxGraphemes` clusters, never cutting through one. */
export function graphemeTruncate(text: string, maxGraphemes: number): string {
  return call(() => native.graphemeTruncate(text, maxGraphemes))
}

/** Display width (terminal columns) of a single grapheme `cluster` by East Asian Width. */
export function graphemeWidth(cluster: string, options: { ambiguousWide?: boolean } = {}): number {
  return native.graphemeWidth(cluster, options.ambiguousWide ?? false)
}

/** Total display width (terminal columns) of `text`. */
export function terminalWidth(text: string, options: { ambiguousWide?: boolean } = {}): number {
  return native.terminalWidth(text, options.ambiguousWide ?? false)
}

// ── Hostname / script analysis ──────────────────────────────────────────────

/** Whether the hostname looks like a mixed-script / confusable IDN spoof (a `false` is not a safety guarantee). */
export function isSuspiciousHostname(host: string): boolean {
  return native.isSuspiciousHostname(host)
}

/**
 * Analyze a hostname for Unicode homoglyph spoofing, returning the full
 * {@link HostnameAnalysis} (verdict + granular signals). `isSuspiciousHostname`
 * is the boolean shorthand for `.suspicious`.
 */
export function analyzeHostname(
  host: string,
  options: { contractions?: boolean } = {},
): HostnameAnalysis {
  return call(() => native.analyzeHostname(host, options.contractions ?? false))
}

/** The Unicode scripts present, in first-appearance order (Common/Inherited excluded). */
export function detectScripts(text: string): string[] {
  return native.detectScripts(text)
}

/** Whether `text` mixes characters from more than one script. */
export function isMixedScript(text: string): boolean {
  return native.isMixedScript(text)
}

/**
 * All twelve UAX #9 explicit formatting characters, uncontexted.
 *
 * The counterpart to {@link hasBidiConflict}, which reads strong-direction letters and is
 * blind to these; the two are disjoint. The anomaly detector's `bidi` kind reports nine of
 * the twelve, holding back LRM, RLM and ALM because a lone directional mark is ordinary in
 * right-to-left text.
 */
export function hasBidiControl(text: string): boolean {
  return native.hasBidiControl(text)
}

/**
 * Whether `text` mixes strong left-to-right and strong right-to-left characters
 * — the precondition for Bidi display-reordering ("BiDi Swap", #412). Fires on
 * the real letters (no `U+202x` override); a `false` result is not a safety
 * guarantee.
 */
export function hasBidiConflict(text: string): boolean {
  return native.hasBidiConflict(text)
}

/** Explain how `lang: 'auto'` detection resolves `text`. */
export function inspectAutoLang(text: string): AutoLangInspection {
  return native.inspectAutoLang(text)
}

// ── Metadata introspection (#404) ───────────────────────────────────────────

/**
 * Static facts about a language `code` — its English name, primary script,
 * region, and context-awareness. An unknown code throws
 * {@link DisarmInvalidArgument}.
 */
export function langInfo(code: string): LangMeta {
  return call(() => native.langInfo(code))
}

/**
 * Static facts about a script by `name` — its default language code (if any),
 * an example string, and whether its transliteration is context-aware. An
 * unknown name throws {@link DisarmInvalidArgument}.
 */
export function scriptInfo(name: string): ScriptMeta {
  return call(() => native.scriptInfo(name))
}

/**
 * The UCD release disarm's normalizer implements. Not a library-wide Unicode version —
 * the bundled tables track different releases. This is the one integrators ask about,
 * because it decides whether disarm's normalization agrees with the host platform's.
 */
export function unicodeVersion(): string {
  return native.unicodeVersion()
}

/**
 * Whether a key stored under an earlier release still compares equal. A monotonic
 * counter, not a version — two artifacts reporting the same value produce the same key
 * for the same input. Meaningless in isolation, by design.
 */
export function keySchemaVersion(): number {
  return native.keySchemaVersion()
}

/**
 * The Unicode `confusables.txt` release the bundled confusable tables were folded
 * from, e.g. `"17.0.0"`.
 *
 * Not a Unicode version for the library as a whole — disarm's case-folding and width
 * tables track different releases (see docs/provenance.md). Use this to answer "is my
 * confusables fold stale?" without inferring it from behaviour.
 */
export function confusablesVersion(): string {
  return native.confusablesVersion()
}

/** Every Unicode script name known to the transliteration tables. */
export function listScripts(): string[] {
  return native.listScripts()
}

/** Every language code that has a context-aware transliteration profile. */
export function listContextLangs(): string[] {
  return native.listContextLangs()
}

// ── Anomaly detection ───────────────────────────────────────────────────────

/**
 * Whether any whitespace token carries out-of-place characters that disguise a
 * real word — a cross-script homoglyph, leet, segmentation, a zero-width / bidi
 * control, or zalgo. Reports a technical fact and leaves the malicious-or-not
 * judgement to the caller. `lexicon` is a common-word collection (a `Set` or
 * array) — or a prebuilt {@link Lexicon} handle, which avoids rebuilding the
 * internal set on every call — used only by the leet and segmentation branches.
 */
export function hasAnomalies(
  text: string,
  lexicon: Iterable<string> | Lexicon = [],
): boolean {
  if (lexicon instanceof Lexicon) {
    return native.hasAnomalies(text, lexicon)
  }
  return native.hasAnomalies(text, Array.isArray(lexicon) ? lexicon : [...lexicon])
}

/**
 * Full anomaly analysis: an `AnomalyReport` with `anomalous`, `kinds` (in
 * first-appearance order), `findings` (each `{ kind, token, start, end, detail,
 * reason }`, with byte offsets), and `reason` (the first finding's reason).
 * `lexicon` may be a `Set`/array of words or a prebuilt {@link Lexicon} handle.
 */
export function inspectAnomalies(
  text: string,
  lexicon: Iterable<string> | Lexicon = [],
): AnomalyReport {
  if (lexicon instanceof Lexicon) {
    return native.inspectAnomalies(text, lexicon) as AnomalyReport
  }
  const words = Array.isArray(lexicon) ? lexicon : [...lexicon]
  return native.inspectAnomalies(text, words) as AnomalyReport
}
