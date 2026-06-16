#!/usr/bin/env node
// Verify the docs' Node/TypeScript examples against the built addon (#44).
//
// The Node usage tabs document outputs with `// =>` comments, e.g.
//   normalizeConfusables('раypal') // => 'paypal'
// This script loads the compiled addon and, for every such line in a fenced
// ```ts / ```typescript / ```js / ```javascript block, evaluates the expression
// and checks it against the documented value — the Node analogue of the Sybil
// (Python), cargo (Rust), and Ruby doc gates. Every `disarm` export is injected
// by name (and as a `disarm` namespace), so both `transliterate(...)` and
// `disarm.transliterate(...)` resolve. It is lenient about trailing prose: when
// the `// =>` side does not parse as a literal, the call is still run (so a throw
// is caught) and only the value comparison is skipped. Lines without `// =>`
// (imports, setup, intentional error demos) are ignored.
//
// Usage:  node scripts/check_doc_node_examples.mjs
// Requires the addon to be built (`npm run build:debug` in bindings/node).

import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
import { isDeepStrictEqual } from 'node:util'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const require = createRequire(import.meta.url)
const disarm = require(join(root, 'bindings', 'node', 'index.js'))

const names = Object.keys(disarm)
const vals = Object.values(disarm)

function markdownFiles(dir) {
  const out = []
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry)
    if (statSync(p).isDirectory()) out.push(...markdownFiles(p))
    else if (p.endsWith('.md')) out.push(p)
  }
  return out
}

const blockRe = /^[ \t]*```(?:ts|typescript|js|javascript)\n([\s\S]*?)\n[ \t]*```/gm
const lineRe = /^(.+?)\s*\/\/\s*=>\s*(.+?)\s*$/

let checked = 0
const failures = []

for (const md of markdownFiles(join(root, 'docs')).sort()) {
  const text = readFileSync(md, 'utf8')
  let block
  while ((block = blockRe.exec(text)) !== null) {
    for (const raw of block[1].split('\n')) {
      const m = raw.trim().match(lineRe)
      if (!m) continue
      const expr = m[1].trim()
      const expectedSrc = m[2].trim()
      if (!expr || expr.startsWith('import') || expr.startsWith('//')) continue

      checked++
      let got
      try {
        got = new Function(...names, 'disarm', `return (${expr})`)(...vals, disarm)
      } catch (e) {
        failures.push(`${md}: \`${expr}\` threw ${e.constructor.name}: ${e.message}`)
        continue
      }

      let want
      try {
        want = new Function('disarm', `return (${expectedSrc})`)(disarm)
      } catch {
        continue // trailing prose after the literal — the call ran, skip value check
      }
      if (!isDeepStrictEqual(got, want)) {
        failures.push(
          `${md}: \`${expr}\` => ${JSON.stringify(got)}, documented ${JSON.stringify(want)}`,
        )
      }
    }
  }
}

console.log(`checked ${checked} node doc expressions`)
if (failures.length > 0) {
  for (const f of failures) console.error(`FAIL ${f}`)
  process.exit(1)
}
console.log('all node doc examples ok')
