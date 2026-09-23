// N2: "Everything disarm throws is a DisarmError" (docs/node/api.md, Errors).
//   node formal/bindings/repro/errors_repro.cjs
'use strict'
const path = require('node:path')
const d = require(path.join(__dirname, '..', '..', '..', 'bindings', 'node', 'index.js'))

const cases = [
  ['transliterate(123)', () => d.transliterate(123)],
  ["transliterate(123, { lang: 'de' })", () => d.transliterate(123, { lang: 'de' })],
  ['stripAccents(undefined)', () => d.stripAccents(undefined)],
  ['demojize(null)', () => d.demojize(null)],
  ['graphemeLen(42)', () => d.graphemeLen(42)],
  ['hasBidiControl({})', () => d.hasBidiControl({})],
  ['normalize(1)', () => d.normalize(1)],
  ["slugify('x', { maxLength: 2 ** 64 })", () => d.slugify('x', { maxLength: 2 ** 64 })],
]
for (const [label, f] of cases) {
  try {
    const r = f()
    console.log(`${label.padEnd(40)} returned ${JSON.stringify(r)}`)
  } catch (e) {
    console.log(`${label.padEnd(40)} threw ${e.constructor.name}; instanceof DisarmError = ${e instanceof d.DisarmError}`)
  }
}
