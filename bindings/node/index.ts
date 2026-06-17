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
import { Lexicon } from './binding'
import type {
  Untranslatable,
  AutoLangInspection,
  Finding as NativeFinding,
  AnomalyReport as NativeAnomalyReport,
} from './binding'

export type { Untranslatable, AutoLangInspection }

/**
 * A reusable, opaque lexicon handle (HAI-SDLC 6.1). `hasAnomalies` /
 * `inspectAnomalies` rebuild an internal set from the caller's word array on
 * every call; constructing a `Lexicon` once (`new Lexicon([...])`) and passing
 * it instead builds that set a single time and reuses it across calls.
 */
export { Lexicon }

/** The anomaly branch that fired for a finding. */
export type AnomalyKind = 'invisible' | 'bidi' | 'zalgo' | 'mixed_script' | 'leet' | 'segmentation'

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
  options: { target?: TargetScript } = {},
): string {
  return call(() => native.normalizeConfusables(text, options.target ?? 'latin'))
}

/** Whether `text` contains a character confusable with `target` (default `'latin'`). */
export function isConfusable(text: string, options: { target?: TargetScript } = {}): boolean {
  return call(() => native.isConfusable(text, options.target ?? 'latin'))
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

export interface CollapseWhitespaceOptions {
  /** Also strip C0/C1 control characters (default `true`). */
  stripControl?: boolean
  /** Also strip zero-width characters (default `true`). */
  stripZeroWidth?: boolean
}

/** Collapse Unicode whitespace runs to single ASCII spaces and trim the ends. */
export function collapseWhitespace(text: string, options: CollapseWhitespaceOptions = {}): string {
  return native.collapseWhitespace(text, options.stripControl ?? true, options.stripZeroWidth ?? true)
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

/** Cap combining marks per base character at `maxMarks` (default `2`). */
export function stripZalgo(text: string, options: { maxMarks?: number } = {}): string {
  return call(() => native.stripZalgo(text, options.maxMarks ?? 2))
}

/** Whether any base character carries more than `threshold` (default `3`) combining marks. */
export function isZalgo(text: string, options: { threshold?: number } = {}): boolean {
  return call(() => native.isZalgo(text, options.threshold ?? 3))
}

// ── Deobfuscation & security presets ────────────────────────────────────────

/** Remove obfuscation (zero-width, bidi, combining-mark abuse, homoglyphs) while keeping legible content. */
export function stripObfuscation(text: string): string {
  return call(() => native.stripObfuscation(text))
}

/** Aggressive security cleaning: NFKC → confusables → strip bidi → collapse → path-safety. */
export function securityClean(text: string): string {
  return call(() => native.securityClean(text))
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

/** The Unicode scripts present, in first-appearance order (Common/Inherited excluded). */
export function detectScripts(text: string): string[] {
  return native.detectScripts(text)
}

/** Whether `text` mixes characters from more than one script. */
export function isMixedScript(text: string): boolean {
  return native.isMixedScript(text)
}

/** Explain how `lang: 'auto'` detection resolves `text`. */
export function inspectAutoLang(text: string): AutoLangInspection {
  return native.inspectAutoLang(text)
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
