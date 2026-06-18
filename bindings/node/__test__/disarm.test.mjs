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
    expect(disarm.collapseWhitespace('a​b')).toBe('a​b')
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
    expect(disarm.securityClean(`hi${tags('PWN')}`)).toBe('hi') // tag smuggling stripped
    expect(disarm.securityClean('ad\u{034F}min')).toBe('admin') // CGJ stripped
    expect(disarm.securityClean('a\u{2800}b')).toBe('a b') // Braille blank -> space
    expect(disarm.securityClean('a\u{E000}b')).toBe('ab') // PUA stripped (comparison preset)
    expect(disarm.stripObfuscation('hi\u{E0001}bye')).toBe('hibye') // deprecated language tag
  })
})
