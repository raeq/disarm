import { test, expect, describe } from 'vitest'
import * as disarm from '../index.js'
import { DisarmError, DisarmInvalidArgument, Lexicon, Pipeline } from '../index.js'

describe('transliterate', () => {
  test('default scheme', () => {
    expect(disarm.transliterate('Москва')).toBe('Moskva')
    expect(disarm.transliterate('café')).toBe('cafe')
  })
  test('language profile', () => {
    expect(disarm.transliterate('Київ', { lang: 'uk' })).toBe('Kyiv')
  })
  test('named scheme', () => {
    expect(disarm.transliterate('Юрий', { scheme: 'strict_iso9' })).toBe('Jurij')
  })
  test('auto language detection', () => {
    expect(disarm.transliterate('Київ', { lang: 'auto' })).toBe('Kyiv')
  })
  test('throws DisarmInvalidArgument on an unknown scheme', () => {
    expect(() => disarm.transliterate('x', { scheme: 'klingon' })).toThrow(DisarmInvalidArgument)
    expect(() => disarm.transliterate('x', { scheme: 'klingon' })).toThrow(DisarmError)
  })
})

describe('digitPolicy on the key builders (#896)', () => {
  // U+0A66 GURMUKHI ZERO standing in for "o": a digit by default, the letter under tr39.
  const spoof = 'g\u0A66ogle'
  test('reaches every builder, and the default is the plain call', () => {
    const builders = [
      disarm.canonicalize,
      disarm.canonicalizeStrict,
      disarm.stripObfuscation,
      disarm.searchKey,
      disarm.sortKey,
      disarm.catalogKey,
    ]
    for (const build of builders) {
      expect(build(spoof, { digitPolicy: 'numeric' })).toBe(build(spoof))
    }
    expect(disarm.canonicalize(spoof)).toBe('g0ogle')
    expect(disarm.canonicalize(spoof, { digitPolicy: 'tr39' })).toBe('google')
    expect(disarm.catalogKey(spoof, { digitPolicy: 'tr39' })).toBe('google')
  })
  test('preserve keeps a numeral where the builder owns a fold; transliteration still romanizes it', () => {
    const numeral = 'amount-\u0661'
    expect(disarm.canonicalize(numeral, { digitPolicy: 'preserve' })).toBe(numeral)
    expect(disarm.searchKey(numeral, { digitPolicy: 'preserve' })).toBe('amount-1')
  })
  test('a bad token is refused by name', () => {
    expect(() => disarm.canonicalize('x', { digitPolicy: 'loose' })).toThrow(DisarmInvalidArgument)
  })
})

describe('skeletonKey (#650)', () => {
  test('merges the capital-I family, and the digit half on request', () => {
    expect(disarm.skeletonKey('paypaI')).toBe(disarm.skeletonKey('paypal'))
    expect(disarm.skeletonKey('SKU-1O0', { digitPolicy: 'tr39' })).toBe(disarm.skeletonKey('SKU-100', { digitPolicy: 'tr39' }))
    expect(disarm.skeletonKey('SKU-1O0')).not.toBe(disarm.skeletonKey('SKU-100'))
  })
})

describe('editDistance and nearestMatch (#894)', () => {
  test('measures in characters', () => {
    expect(disarm.editDistance('paypa1', 'paypal')).toBe(1)
    expect(disarm.editDistance('stripe', 'stripe')).toBe(0)
  })
  test('reports the closest candidate, an exact match at 0, and null beyond the threshold', () => {
    const reserved = ['paypal', 'stripe', 'admin']
    expect(disarm.nearestMatch('paypa1', reserved)).toEqual({ value: 'paypal', distance: 1 })
    expect(disarm.nearestMatch('admin', reserved)).toEqual({ value: 'admin', distance: 0 })
    expect(disarm.nearestMatch('something-else', reserved)).toBeNull()
    expect(disarm.nearestMatch('paypa11', reserved, { maxDistance: 2 })).toEqual({ value: 'paypal', distance: 2 })
  })
  test('a negative maxDistance is rejected, not read as exact-match-only', () => {
    expect(() => disarm.nearestMatch('x', ['y'], { maxDistance: -1 })).toThrow(DisarmInvalidArgument)
  })
})

describe('Pipeline.withDigitPolicy (#646)', () => {
  test('folds under the policy, and refuses one the profile cannot run', () => {
    const spoof = 'g\u0A66ogle'
    expect(disarm.getPipeline('llm_guardrail').process(spoof)).toBe('g0ogle')
    expect(disarm.getPipeline('llm_guardrail').withDigitPolicy('tr39').process(spoof)).toBe('google')
    expect(() => disarm.getPipeline('rag_ingest').withDigitPolicy('tr39')).toThrow(/confusables/)
  })
})

describe('confusables', () => {
  test('normalizeConfusables folds to latin by default', () => {
    expect(disarm.normalizeConfusables('раypal')).toBe('paypal')
  })
  test('isConfusable', () => {
    expect(disarm.isConfusable('pаypal')).toBe(true)
    expect(disarm.isConfusable('paypal')).toBe(false)
  })
  // #586: the fold iterates to a fixed point rather than stopping after one pass.
  // Every non-Python binding reaches the core through the same Rust entry point, so a
  // single pass made this call answer differently from Python for the same input.
  test('normalizeConfusables reaches a fixed point', () => {
    // A fold exposes a composition: ¥ + ◌̀ folds to Y + ◌̀, which composes to Ỳ.
    expect(disarm.normalizeConfusables('\u00A5\u0300')).toBe('\u1EF2')
    // A composition exposes a fold: Ҫ + ◌̧ composes to Ç, itself a confusable → C.
    expect(disarm.normalizeConfusables('\u04AA\u0327')).toBe('C')
  })
  test('normalizeConfusables output is never itself confusable', () => {
    for (const input of ['\u04AA\u0327', '\u00A5\u0300', 'p\u0430ypal']) {
      expect(disarm.isConfusable(disarm.normalizeConfusables(input))).toBe(false)
    }
  })
})

describe('slugify', () => {
  test('sensible defaults', () => {
    expect(disarm.slugify('Héllo, World!')).toBe('hello-world')
  })
  test('separator option', () => {
    expect(disarm.slugify('a b c', { separator: '_' })).toBe('a_b_c')
  })
  test('maxLength with word boundary', () => {
    expect(disarm.slugify('Very Long Title Here', { maxLength: 10, wordBoundary: true })).toBe('very-long')
  })
})

describe('canonicalization', () => {
  test('stripAccents', () => expect(disarm.stripAccents('café')).toBe('cafe'))
  test('foldCase', () => expect(disarm.foldCase('HELLO')).toBe('hello'))
  test('isCaseFoldStable', () => {
    expect(disarm.isCaseFoldStable('gross.txt')).toBe(true)
    // The pair node-tar collided on: both sides reduce to gross.txt.
    expect(disarm.isCaseFoldStable('groß.txt')).toBe(false)
    // Greek final sigma — the whole-string answer, not a per-character one.
    expect(disarm.isCaseFoldStable('ΟΔΟΣ')).toBe(false)
    expect(disarm.isCaseFoldStable('ΣΑΒΒΑΤΟ')).toBe(true)
  })
  test('demojize', () => expect(disarm.demojize('hi 👍')).toBe('hi thumbs up'))
})

describe('key collisions (#620)', () => {
  test('the node-tar pair is reported', () => {
    const found = disarm.findKeyCollisions(['groß.txt', 'gross.txt', 'other.txt'], 'fold_case')
    expect(found).toHaveLength(1)
    expect(found[0].key).toBe('gross.txt')
    expect(found[0].values).toEqual(['groß.txt', 'gross.txt'])
    expect(found[0].indices).toEqual([0, 1])
  })
  test('a clean set reports nothing, and one name twice is not a collision', () => {
    expect(disarm.findKeyCollisions(['a.txt', 'b.txt'], 'fold_case')).toEqual([])
    expect(disarm.findKeyCollisions(['a.txt', 'a.txt'], 'fold_case')).toEqual([])
  })
  test('the reducer is the policy', () => {
    const names = ['groß', 'gross', 'admin', 'аdmin']
    expect(disarm.findKeyCollisions(names, 'fold_case')[0].values).toEqual(['groß', 'gross'])
    expect(disarm.findKeyCollisions(names, 'canonicalize')[0].values).toEqual(['admin', 'аdmin'])
    expect(disarm.findKeyCollisions(names, 'search_key')).toHaveLength(2)
  })
  test('lang reaches the keys that take one', () => {
    expect(
      disarm.findKeyCollisions(['Müller', 'Mueller'], 'search_key', { lang: 'de' }),
    ).toHaveLength(1)
    expect(disarm.findKeyCollisions(['Müller', 'Mueller'], 'search_key')).toEqual([])
  })
  test('an unknown key is refused rather than defaulted', () => {
    expect(() => disarm.findKeyCollisions(['a'], 'lower')).toThrow()
  })
})

describe('normalization', () => {
  test('default NFC leaves the ligature; NFKC decomposes it', () => {
    expect(disarm.normalize('ﬁ')).toBe('ﬁ')
    expect(disarm.normalize('ﬁnance', { form: 'NFKC' })).toBe('finance')
    expect(disarm.normalize('2²', { form: 'NFKC' })).toBe('22')
  })
  test('isNormalized', () => {
    expect(disarm.isNormalized('café', { form: 'NFC' })).toBe(true)
    expect(disarm.isNormalized('ﬁ', { form: 'NFKC' })).toBe(false)
  })
  test('throws on unknown form', () => {
    expect(() => disarm.normalize('x', { form: 'NFZ' })).toThrow(DisarmInvalidArgument)
  })
})

describe('text cleaning', () => {
  test('collapseWhitespace collapses and trims', () => {
    expect(disarm.collapseWhitespace('  a   b ')).toBe('a b')
  })
  test('collapseWhitespace folds line controls + blank-render to a space (#433)', () => {
    // Line controls fold to a space rather than being deleted (no token join).
    expect(disarm.collapseWhitespace('a\rb')).toBe('a b') // CR
    expect(disarm.collapseWhitespace('a\x0Bb')).toBe('a b') // VT
    expect(disarm.collapseWhitespace('a\x85b')).toBe('a b') // NEL
    expect(disarm.collapseWhitespace('a\x1Cb')).toBe('a b') // FS
    expect(disarm.collapseWhitespace('a\x1Fb')).toBe('a b') // US
    // Blank-rendering code points fold too.
    expect(disarm.collapseWhitespace('a⠀b')).toBe('a b') // Braille blank
    expect(disarm.collapseWhitespace('aㅤb')).toBe('a b') // Hangul filler
  })
  test('collapseWhitespace folds whitespace only — preserves controls/zero-width (#433)', () => {
    // It no longer accepts strip options and does not delete anything: a
    // non-whitespace control (NUL) and a zero-width space pass through.
    expect(disarm.collapseWhitespace('a\x00b')).toBe('a\x00b')
    expect(disarm.collapseWhitespace('a\u200bb')).toBe('a\u200bb')
  })
  test('strip control / zero-width / bidi', () => {
    expect(disarm.stripControlChars('a\u0007b')).toBe('ab')
    expect(disarm.stripZeroWidthChars('a\u200bb')).toBe('ab')
    expect(disarm.stripBidi('a\u202eb')).toBe('ab')
  })
  test('zalgo detection and stripping', () => {
    const zalgo = `Z${'́'.repeat(8)}`
    expect(disarm.isZalgo(zalgo)).toBe(true)
    expect(disarm.isZalgo(disarm.stripZalgo(zalgo))).toBe(false)
  })
})

describe('deobfuscation & security', () => {
  test('stripObfuscation', () => expect(disarm.stripObfuscation('рroduсt')).toBe('product'))
  test('canonicalize', () => expect(disarm.canonicalize('ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥')).toBe('Real text'))
  // #698: stripFormat KEEPS the script; canonicalize folds it. The same input each way
  // is the whole reason the preset is not composable from the universal strip* calls.
  test('stripFormat keeps the script', () =>
    expect(disarm.stripFormat('ар\u200dр')).toBe('арр'))
  test('canonicalize folds the same input to Latin', () =>
    expect(disarm.canonicalize('ар\u200dр')).toBe('app'))
  test('canonicalizeStrict is reachable', () =>
    expect(disarm.canonicalizeStrict('Hello')).toBe(disarm.canonicalize('Hello')))
  // #430: securityClean is a deprecated alias for canonicalize (removed in 1.0).
  test('securityClean (deprecated alias)', () =>
    expect(disarm.securityClean('ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥')).toBe(disarm.canonicalize('ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥')))
})

describe('filenames', () => {
  test('safe filename', () => {
    expect(disarm.sanitizeFilename('My: report*.txt')).toBe('My_report.txt')
  })
  test('platform rules', () => {
    expect(disarm.sanitizeFilename('CON', { platform: 'windows' })).toBe('_CON')
  })
  test('throws on unknown platform', () => {
    expect(() => disarm.sanitizeFilename('x', { platform: 'amiga' })).toThrow(DisarmInvalidArgument)
  })
})

describe('key-derivation presets', () => {
  const asciiKey = /^[\x20-\x7e]+$/

  test('searchKey yields a non-empty ASCII key', () => {
    const key = disarm.searchKey('Köln')
    expect(key.length).toBeGreaterThan(0)
    expect(key).toMatch(asciiKey)
  })
  test('sortKey preserves base accented characters for collation', () => {
    // Unlike searchKey, sortKey keeps the accent so it can order the key.
    expect(disarm.sortKey('Café')).toBe('café')
    expect(disarm.searchKey('Café')).toBe('cafe')
    expect(disarm.sortKey('Café')).not.toBe(disarm.searchKey('Café'))
    // Non-Latin scripts are still folded to a consistent Latin form.
    expect(disarm.sortKey('Москва')).toBe('moskva')
  })
  test('catalogKey yields a non-empty ASCII key', () => {
    const key = disarm.catalogKey('naïve')
    expect(key.length).toBeGreaterThan(0)
    expect(key).toMatch(asciiKey)
  })
  test('lang and strictIso9 options are accepted', () => {
    expect(disarm.searchKey('Москва', { lang: 'ru' }).length).toBeGreaterThan(0)
    expect(disarm.sortKey('Москва', { lang: 'ru' }).length).toBeGreaterThan(0)
    expect(disarm.catalogKey('Москва', { lang: 'ru', strictIso9: true }).length).toBeGreaterThan(0)
  })
  test('an unknown lang throws DisarmInvalidArgument', () => {
    expect(() => disarm.searchKey('x', { lang: 'zz' })).toThrow(DisarmInvalidArgument)
    expect(() => disarm.sortKey('x', { lang: 'zz' })).toThrow(DisarmInvalidArgument)
    expect(() => disarm.catalogKey('x', { lang: 'zz' })).toThrow(DisarmInvalidArgument)
  })
})

describe('graphemes', () => {
  test('graphemeLen counts user-perceived characters', () => {
    expect(disarm.graphemeLen('a👍b')).toBe(3)
    expect(disarm.graphemeLen('🇬🇧')).toBe(1)
  })
  test('graphemeSplit', () => {
    expect(disarm.graphemeSplit('a👍')).toEqual(['a', '👍'])
  })
  test('graphemeTruncate never cuts a cluster', () => {
    expect(disarm.graphemeTruncate('héllo', 3)).toBe('hél')
  })
  test('width by East Asian Width', () => {
    expect(disarm.graphemeWidth('👍')).toBe(2)
    expect(disarm.terminalWidth('a👍')).toBe(3)
    expect(disarm.terminalWidth('¡', { ambiguousWide: true })).toBe(2)
  })
})

describe('negative size/threshold validation', () => {
  // napi's ToUint32 used to silently wrap a negative JS number to a huge value;
  // these now reject it with DisarmInvalidArgument (matching Python/Ruby).
  test('graphemeTruncate rejects a negative maxGraphemes', () => {
    expect(() => disarm.graphemeTruncate('ab', -1)).toThrow(DisarmInvalidArgument)
    expect(() => disarm.graphemeTruncate('ab', -1)).toThrow(DisarmError)
  })
  test('stripZalgo rejects a negative maxMarks', () => {
    expect(() => disarm.stripZalgo('Z', { maxMarks: -5 })).toThrow(DisarmInvalidArgument)
  })
  test('isZalgo rejects a negative threshold', () => {
    expect(() => disarm.isZalgo('Z', { threshold: -1 })).toThrow(DisarmInvalidArgument)
  })
  test('sanitizeFilename rejects a negative maxLength', () => {
    expect(() => disarm.sanitizeFilename('x', { maxLength: -1 })).toThrow(DisarmInvalidArgument)
  })
  test('slugify rejects a negative maxLength', () => {
    expect(() => disarm.slugify('hello', { maxLength: -1 })).toThrow(DisarmInvalidArgument)
  })
})

describe('reverse transliteration & untranslatable', () => {
  test('reverseTransliterate', () => {
    expect(disarm.reverseTransliterate('Moskva', { lang: 'ru' })).toBe('Москва')
  })
  test('reverseTransliterate throws on unsupported lang', () => {
    expect(() => disarm.reverseTransliterate('x', { lang: 'fr' })).toThrow(DisarmInvalidArgument)
  })
  test('findUntranslatable yields { char, offset }', () => {
    expect(disarm.findUntranslatable('a\u{1F70A}')).toEqual([{ char: '\u{1F70A}', offset: 1 }])
    expect(disarm.findUntranslatable('café')).toEqual([])
  })
})

describe('script analysis', () => {
  test('detectScripts', () => {
    expect(disarm.detectScripts('aМ')).toEqual(['Latin', 'Cyrillic'])
  })
  test('isMixedScript', () => {
    expect(disarm.isMixedScript('aМ')).toBe(true)
    expect(disarm.isMixedScript('abc')).toBe(false)
  })
  test('hasBidiConflict (#412)', () => {
    expect(disarm.hasBidiConflict('helloא')).toBe(true) // Latin + Hebrew
    expect(disarm.hasBidiConflict('аום')).toBe(true) // Cyrillic + Hebrew
    expect(disarm.hasBidiConflict('hello')).toBe(false) // all LTR
    expect(disarm.hasBidiConflict('אתר')).toBe(false) // all RTL
    expect(disarm.hasBidiConflict('ו443')).toBe(false) // digits are neutral
  })
  test('isSuspiciousHostname', () => {
    expect(disarm.isSuspiciousHostname('pаypal.com')).toBe(true)
    expect(disarm.isSuspiciousHostname('example.com')).toBe(false)
    // #412: a BiDi-Swap host (Latin sub on a Hebrew domain) is now flagged.
    expect(disarm.isSuspiciousHostname('varonis.com.ו.קום')).toBe(true)
  })
  test('analyzeHostname — full analysis (#549)', () => {
    const clean = disarm.analyzeHostname('example.com')
    expect(clean.suspicious).toBe(false)
    expect(clean.scripts).toEqual(['Latin'])
    expect(clean.labelScripts).toEqual([['Latin'], ['Latin']]) // Vec<Vec<String>>
    expect(clean.wholeScriptConfusable).toBe(false)
    expect(clean.labelWholeScriptConfusable).toEqual([false, false]) // Vec<bool>
    expect(clean.canonical).toBe('example.com')

    // Whole-script spoof: all-Cyrillic label skeletoning to a Latin brand (#545).
    const spoof = disarm.analyzeHostname('аррӏе.com')
    expect(spoof.wholeScriptConfusable).toBe(true)
    expect(spoof.labelWholeScriptConfusable).toEqual([true, false])
    expect(spoof.canonical).toBe('apple.com')

    // Mixed-script is a separate signal.
    const mixed = disarm.analyzeHostname('pаypal.com')
    expect(mixed.mixedScript).toBe(true)
    expect(mixed.hasConfusables).toBe(true)

    // Bidi control character (#603): flagged, and stripped from the canonical form
    // so a caller rendering that field cannot render the spoof.
    const rlo = disarm.analyzeHostname('paypal\u202Emoc.evil.com')
    expect(rlo.suspicious).toBe(true)
    expect(rlo.bidiControl).toBe(true)
    expect(rlo.bidiConflict).toBe(false) // disjoint signals
    expect(rlo.canonical).toBe('paypalmoc.evil.com')
    expect(clean.bidiControl).toBe(false)

    // Zero-width / invisible-format character (#605): flagged, and removed before
    // any other field is computed, so it reaches neither scripts nor canonical.
    const zwsp = disarm.analyzeHostname('paypal\u200B.evil.com')
    expect(zwsp.suspicious).toBe(true)
    expect(zwsp.hasInvisible).toBe(true)
    expect(zwsp.bidiControl).toBe(false) // disjoint signals
    expect(zwsp.canonical).toBe('paypal.evil.com')

    // U+FEFF lives in the Arabic Presentation Forms block; it must not be read
    // as evidence the host contains Arabic.
    const bom = disarm.analyzeHostname('paypal\uFEFF.evil.com')
    expect(bom.hasInvisible).toBe(true)
    expect(bom.scripts).toEqual(['Latin'])
    expect(bom.mixedScript).toBe(false)

    expect(clean.hasInvisible).toBe(false)

    // Compatibility form (#709): read off the RAW input, before the normalization
    // every other field needs. `hasConfusables` is correctly false — by the time it
    // runs the label is already `google`.
    const fw = disarm.analyzeHostname('\uFF47oogle.com')
    expect(fw.suspicious).toBe(true)
    expect(fw.compatFold).toBe(true)
    expect(fw.hasConfusables).toBe(false)
    expect(fw.canonical).toBe('google.com')
    expect(clean.compatFold).toBe(false)

    // UTS #46 maps every label, not only the `xn--` ones (#714): the two spellings
    // of one registered domain are one input.
    expect(disarm.analyzeHostname('\uAB70\uAB70.com').canonical).toBe(
      disarm.analyzeHostname('xn--58da.com').canonical,
    )
  })
  test('inspectAutoLang', () => {
    const info = disarm.inspectAutoLang('Москва')
    expect(info.script).toBe('Cyrillic')
    expect(info.chosenLang).toBe('ru')
    expect(info.reason).toBe('script_default')
    expect(info.discriminatorsHit).toEqual([])
  })
})

describe('metadata introspection (#404)', () => {
  test('langInfo returns static facts about a language', () => {
    expect(disarm.langInfo('de').name).toBe('German')
  })
  test('scriptInfo returns static facts about a script', () => {
    expect(disarm.scriptInfo('Coptic').defaultLang).toBe('cop')
  })
  test('confusablesVersion reports a dotted numeric data version', () => {
    const v = disarm.confusablesVersion()
    expect(typeof v).toBe('string')
    expect(v).toMatch(/^\d+(\.\d+)+$/)
  })
  test('normalizeConfusables digitPolicy selects the digit reading', () => {
    // Devanagari zeros: numeric keeps the number, tr39 makes the skeleton collide.
    expect(disarm.normalizeConfusables('g\u0966\u0966gle')).toBe('g00gle')
    expect(disarm.normalizeConfusables('g\u0966\u0966gle', { digitPolicy: 'tr39' })).toBe('google')
    // Everything outside the 45 divergent rows is identical under both.
    expect(disarm.normalizeConfusables('p\u0430ypal', { digitPolicy: 'tr39' })).toBe('paypal')
  })
  test('normalizeConfusables rejects a bad digitPolicy', () => {
    expect(() => disarm.normalizeConfusables('x', { digitPolicy: 'skeleton' })).toThrow()
  })
  test('mlNormalize folds case by default', () => {
    expect(disarm.mlNormalize('José Martínez')).toBe('jose martinez')
    expect(disarm.mlNormalize('Café RÉSUMÉ')).toBe('cafe resume')
  })
  test('mlNormalize foldCase:false keeps capitals but not accents', () => {
    expect(disarm.mlNormalize('José Martínez', { foldCase: false })).toBe('Jose Martinez')
  })
  test('mlNormalize honours lang and emojiStyle', () => {
    expect(disarm.mlNormalize('MÜNCHEN Straße', { lang: 'de' })).toBe('muenchen strasse')
    expect(disarm.mlNormalize('Hi \u{1F600}', { emojiStyle: 'none' })).toBe('hi \u{1F600}')
    expect(disarm.mlNormalize('Hi \u{1F600}', { emojiStyle: 'none', foldCase: false })).toBe(
      'Hi \u{1F600}',
    )
    expect(disarm.mlNormalize('Hi \u{1F600}')).toBe('hi grinning face')
  })
  test('mlNormalize rejects a bad emojiStyle', () => {
    expect(() => disarm.mlNormalize('x', { emojiStyle: 'bogus' })).toThrow()
  })
  test('analyzeHostname contractions is off by default', () => {
    expect(disarm.analyzeHostname('arnazon.com').canonical).toBe('arnazon.com')
  })
  test('analyzeHostname contractions recovers the digraph spoof', () => {
    expect(disarm.analyzeHostname('arnazon.com', { contractions: true }).canonical).toBe(
      'amazon.com',
    )
    // Leftmost-longest, and never across a label boundary.
    expect(disarm.analyzeHostname('vvv.com', { contractions: true }).canonical).toBe('wv.com')
    expect(disarm.analyzeHostname('var.net', { contractions: true }).canonical).toBe('var.net')
  })
  test('unmappedConfusables reports exposure, not coverage', () => {
    const unmapped = disarm.unmappedConfusables()
    expect(unmapped.size).toBeGreaterThan(1000)
    // Cyrillic а IS folded, so it is not exposure.
    expect(unmapped.has('\u0430')).toBe(false)
    // TR39 skeleton source m→rn, deliberately not applied.
    expect(unmapped.has('m')).toBe(true)
  })
  test('findUnmappedConfusables agrees with the fold', () => {
    // Cyrillic а folds to a, so the spoof is covered — nothing to report.
    expect(disarm.normalizeConfusables('p\u0430ypal')).toBe('paypal')
    expect(disarm.findUnmappedConfusables('p\u0430ypal')).toEqual([])
    // 'm' is a skeleton source the table does not fold; offset is a byte offset.
    expect(disarm.findUnmappedConfusables('am')).toEqual([{ char: 'm', offset: 1 }])
  })
  test('listScripts includes Latin and Common', () => {
    const scripts = disarm.listScripts()
    expect(scripts).toContain('Latin')
    expect(scripts).toContain('Common')
  })
  test('listContextLangs includes context-aware langs only', () => {
    const langs = disarm.listContextLangs()
    expect(langs).toContain('ar')
    expect(langs).not.toContain('de')
  })
  test('an unknown code/script throws DisarmInvalidArgument', () => {
    expect(() => disarm.langInfo('zz')).toThrow(DisarmInvalidArgument)
    expect(() => disarm.scriptInfo('Nope')).toThrow(DisarmInvalidArgument)
  })
})

describe('anomaly detection', () => {
  const lex = ['free', 'viagra', 'paypal']

  test('flags out-of-place characters that disguise a word', () => {
    expect(disarm.hasAnomalies('get fr33 now', lex)).toBe(true)
    expect(disarm.hasAnomalies('paypаl', lex)).toBe(true) // Cyrillic а
    expect(disarm.hasAnomalies('buy v.i.a.g.r.a now', lex)).toBe(true)
  })

  test('spares clean text and literal numbers', () => {
    expect(disarm.hasAnomalies('a perfectly clean sentence', lex)).toBe(false)
    expect(disarm.hasAnomalies('the win32 api and mp3 file', lex)).toBe(false)
  })

  test('accepts a Set lexicon', () => {
    expect(disarm.hasAnomalies('get fr33', new Set(['free']))).toBe(true)
  })

  test('lexicon is case-insensitive on ingest (title-cased wordlist matches)', () => {
    expect(disarm.hasAnomalies('get fr33 now', ['Free'])).toBe(true)
    expect(disarm.hasAnomalies('buy v.i.a.g.r.a now', ['VIAGRA'])).toBe(true)
    expect(disarm.hasAnomalies('get fr33 now', new Lexicon(['Free']))).toBe(true)
  })

  test('returns a structured report with byte spans', () => {
    const input = 'log in to paypаl today' // Cyrillic а in "paypаl"
    const r = disarm.inspectAnomalies(input, ['paypal'])
    expect(r.anomalous).toBe(true)
    expect(r.kinds).toEqual(['mixed_script'])
    const f = r.findings[0]
    expect(f.kind).toBe('mixed_script')
    expect(f.token).toBe('paypаl')
    expect(f.detail).toContain('Latin')
    expect(f.reason).toContain('Latin')
    // The byte span must carve the exact token out of the UTF-8 input.
    expect(typeof f.start).toBe('number')
    expect(typeof f.end).toBe('number')
    const slice = Buffer.from(input, 'utf8').slice(f.start, f.end).toString('utf8')
    expect(slice).toBe(f.token)
  })

  test('flags a bidi-direction conflict as bidi_mixed (#412)', () => {
    // Latin + Hebrew in one token can visually reorder.
    expect(disarm.inspectAnomalies('varonisו', []).kinds).toEqual(['bidi_mixed'])
    // Cyrillic + Hebrew: missed by the Latin-anchored mixed_script rule.
    expect(disarm.inspectAnomalies('аום', []).kinds).toEqual(['bidi_mixed'])
  })

  test('defaults the lexicon to empty (no throw without one)', () => {
    expect(disarm.hasAnomalies('paypаl')).toBe(true) // Cyrillic а, no lexicon needed
    const r = disarm.inspectAnomalies('paypаl')
    expect(r.anomalous).toBe(true)
  })

  test('reports nothing for clean text', () => {
    const r = disarm.inspectAnomalies('nothing to see here', [])
    expect(r.anomalous).toBe(false)
    expect(r.kinds).toEqual([])
    expect(r.findings).toEqual([])
    expect(r.reason ?? null).toBeNull()
  })

  describe('Lexicon (reusable handle, 6.1)', () => {
    test('a Lexicon gives the same hasAnomalies result as the raw array', () => {
      const lexicon = new Lexicon(lex)
      for (const input of ['get fr33 now', 'buy v.i.a.g.r.a now', 'the win32 api and mp3 file']) {
        expect(disarm.hasAnomalies(input, lexicon)).toBe(disarm.hasAnomalies(input, lex))
      }
    })

    test('a Lexicon gives the same inspectAnomalies report as the raw array', () => {
      const input = 'log in to paypаl today' // Cyrillic а in "paypаl"
      const words = ['paypal']
      const lexicon = new Lexicon(words)
      expect(disarm.inspectAnomalies(input, lexicon)).toEqual(disarm.inspectAnomalies(input, words))
    })

    test('one Lexicon is reusable across many calls', () => {
      const lexicon = new Lexicon(lex)
      expect(disarm.hasAnomalies('get fr33 now', lexicon)).toBe(true)
      expect(disarm.hasAnomalies('a perfectly clean sentence', lexicon)).toBe(false)
      expect(disarm.hasAnomalies('paypаl', lexicon)).toBe(true) // Cyrillic а
      const r = disarm.inspectAnomalies('buy v.i.a.g.r.a now', lexicon)
      expect(r.anomalous).toBe(true)
    })

    test('an empty Lexicon still flags lexicon-free anomalies', () => {
      const empty = new Lexicon([])
      expect(disarm.hasAnomalies('paypаl', empty)).toBe(true) // Cyrillic а, no lexicon needed
      expect(disarm.inspectAnomalies('paypаl', empty).anomalous).toBe(true)
    })
  })
})

describe('getPipeline (reusable policy-profile handle, #404)', () => {
  // 'search_index' is a built-in profile (NFKC → transliterate → strip accents →
  // fold case → collapse whitespace); it yields a clean, folded string.
  test('process yields a cleaned string', () => {
    const p = disarm.getPipeline('search_index')
    expect(p).toBeInstanceOf(Pipeline)
    expect(p.process('Café')).toBe('cafe')
  })

  test('the SAME handle is reusable across many calls', () => {
    const p = disarm.getPipeline('search_index')
    expect(p.process('Café')).toBe('cafe')
    expect(p.process('Москва')).toBe('moskva')
    expect(p.process('  Hello   World  ')).toBe('hello world')
    // Reusing it once more must give the same result as a fresh handle.
    expect(p.process('Café')).toBe(disarm.getPipeline('search_index').process('Café'))
  })

  test('an unknown profile throws DisarmInvalidArgument', () => {
    expect(() => disarm.getPipeline('nope')).toThrow(DisarmInvalidArgument)
    expect(() => disarm.getPipeline('nope')).toThrow(DisarmError)
  })
})

describe('invisible / non-interchange stripping (#413)', () => {
  const tags = (s) => [...s].map((c) => String.fromCodePoint(0xe0000 + c.codePointAt(0))).join('')
  const SCOTLAND = '\u{1F3F4}\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}'

  test('standalone helpers', () => {
    expect(disarm.stripTags(`hi${tags('PWN')}`)).toBe('hi')
    expect(disarm.stripTags(SCOTLAND)).toBe(SCOTLAND) // valid emoji flag preserved
    expect(disarm.stripVariationSelectors('g\u{FE01}data')).toBe('gdata')
    expect(disarm.stripNoncharacters('a\u{FFFE}b')).toBe('ab')
    expect(disarm.stripPua('a\u{E000}b')).toBe('ab')
  })

  test('preset behaviour flows from the core', () => {
    expect(disarm.canonicalize(`hi${tags('PWN')}`)).toBe('hi') // tag smuggling stripped
    expect(disarm.canonicalize('ad\u{034F}min')).toBe('admin') // CGJ stripped
    expect(disarm.canonicalize('a\u{2800}b')).toBe('a b') // Braille blank -> space
    expect(disarm.canonicalize('a\u{E000}b')).toBe('ab') // PUA stripped (comparison preset)
    expect(disarm.stripObfuscation('hi\u{E0001}bye')).toBe('hibye') // deprecated language tag
  })
})
