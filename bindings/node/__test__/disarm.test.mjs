import { test, expect, describe } from 'vitest'
import * as disarm from '../index.js'
import { DisarmError, DisarmInvalidArgument } from '../index.js'

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

describe('confusables', () => {
  test('normalizeConfusables folds to latin by default', () => {
    expect(disarm.normalizeConfusables('раypal')).toBe('paypal')
  })
  test('isConfusable', () => {
    expect(disarm.isConfusable('pаypal')).toBe(true)
    expect(disarm.isConfusable('paypal')).toBe(false)
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
  test('demojize', () => expect(disarm.demojize('hi 👍')).toBe('hi thumbs up'))
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
  test('strip control / zero-width / bidi', () => {
    expect(disarm.stripControlChars('ab')).toBe('ab')
    expect(disarm.stripZeroWidthChars('a​b')).toBe('ab')
    expect(disarm.stripBidi('a‮b')).toBe('ab')
  })
  test('zalgo detection and stripping', () => {
    const zalgo = `Z${'́'.repeat(8)}`
    expect(disarm.isZalgo(zalgo)).toBe(true)
    expect(disarm.isZalgo(disarm.stripZalgo(zalgo))).toBe(false)
  })
})

describe('deobfuscation & security', () => {
  test('stripObfuscation', () => expect(disarm.stripObfuscation('рroduсt')).toBe('product'))
  test('securityClean', () => expect(disarm.securityClean('ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥')).toBe('Real text'))
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
  test('isSuspiciousHostname', () => {
    expect(disarm.isSuspiciousHostname('pаypal.com')).toBe(true)
    expect(disarm.isSuspiciousHostname('example.com')).toBe(false)
  })
  test('inspectAutoLang', () => {
    const info = disarm.inspectAutoLang('Москва')
    expect(info.script).toBe('Cyrillic')
    expect(info.chosenLang).toBe('ru')
    expect(info.reason).toBe('script_default')
    expect(info.discriminatorsHit).toEqual([])
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
})
