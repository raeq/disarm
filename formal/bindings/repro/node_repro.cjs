// Node reproductions (README: B1, B2, N1).  node formal/bindings/repro/node_repro.cjs
'use strict'
const path = require('node:path')
const d = require(path.join(__dirname, '..', '..', '..', 'bindings', 'node', 'index.js'))

const esc = (s) => JSON.stringify(s).replace(/[\u007f-\uffff]/g, (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`)
const show = (label, f) => {
  let r
  try {
    r = esc(f())
  } catch (e) {
    r = `threw ${e.name}: ${e.message}`
  }
  console.log(`${label.padEnd(58)} ${r}`)
}

console.log('-- B1: strip_zalgo default cap (core DEFAULT_MAX_MARKS = 3, #788) --')
const stack = 'a\u0316\u0317\u0318' // three marks below one base: not zalgo (3 is not > 3)
show('isZalgo(stack)', () => d.isZalgo(stack))
show('stripZalgo(stack)', () => d.stripZalgo(stack))
show('stripZalgo(stack, { maxMarks: 3 })', () => d.stripZalgo(stack, { maxMarks: 3 }))

console.log('-- B2: an unknown `lang` is accepted silently --')
show("transliterate('\\u041a\\u0438\\u0457\\u0432', { lang: 'uk' })", () => d.transliterate('\u{41a}\u{438}\u{457}\u{432}', { lang: 'uk' }))
show("transliterate('\\u041a\\u0438\\u0457\\u0432', { lang: 'UK' })", () => d.transliterate('\u{41a}\u{438}\u{457}\u{432}', { lang: 'UK' }))
show("transliterate('M\\u00fcnchen', { lang: 'german' })", () => d.transliterate('M\u{fc}nchen', { lang: 'german' }))
show("slugify('M\\u00fcnchen', { lang: 'dee' })", () => d.slugify('M\u{fc}nchen', { lang: 'dee' }))
show("findUntranslatable('x', { lang: 'zz' })", () => d.findUntranslatable('x', { lang: 'zz' }))
show("searchKey('M\\u00fcnchen', { lang: 'zz' })", () => d.searchKey('M\u{fc}nchen', { lang: 'zz' }))

console.log('-- N1: non-integer sizes are coerced, not rejected --')
show('stripZalgo(\'caf\\u00e9\', { maxMarks: NaN })', () => d.stripZalgo('caf\u{e9}', { maxMarks: NaN }))
show('stripZalgo(\'caf\\u00e9\', { maxMarks: 0.9 })', () => d.stripZalgo('caf\u{e9}', { maxMarks: 0.9 }))
show("graphemeTruncate('abcdef', 2.9)", () => d.graphemeTruncate('abcdef', 2.9))
show("graphemeTruncate('abcdef', NaN)", () => d.graphemeTruncate('abcdef', NaN))
show("slugify('hello world', { maxLength: 5.5 })", () => d.slugify('hello world', { maxLength: 5.5 }))
show("slugify('hello world', { maxLength: -1 })", () => d.slugify('hello world', { maxLength: -1 }))
show("isZalgo('a\\u0301\\u0301', { threshold: NaN })", () => d.isZalgo('a\u{301}\u{301}', { threshold: NaN }))
