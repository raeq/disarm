// #469: the surrogate-input contract for the Node binding.
//
// A JS string is UTF-16 and may contain unpaired (lone) surrogates. napi's
// string→Rust conversion already replaces each lone surrogate with U+FFFD before
// the disarm core sees it, so the binding must (a) never throw on this input and
// (b) behave exactly as it would on the U+FFFD-scrubbed string — the same contract
// the Python binding is being brought to. These tests pin that behaviour so it is a
// documented guarantee rather than incidental napi behaviour.

import { describe, expect, test } from 'vitest'
import * as disarm from '../index.js'

// The WTF-8 → UTF-8 reference, no regex: spreading a JS string iterates by code
// POINT, so a well-formed high+low pair is already one astral scalar (kept) and
// only a genuinely lone surrogate stays a single unit → one U+FFFD. This is exactly
// what napi does at the boundary; the tests pin it as a guarantee.
const canonical = (s) =>
  [...s]
    .map((c) => {
      const cp = c.codePointAt(0)
      return cp >= 0xd800 && cp <= 0xdfff ? '�' : c
    })
    .join('')

// The presets the Node binding actually surfaces (a deliberate subset of Python —
// no stripFormat / canonicalizeStrict / mlNormalize on this surface).
const ENTRYPOINTS = [
  ['canonicalize', disarm.canonicalize],
  ['stripObfuscation', disarm.stripObfuscation],
  ['securityClean', disarm.securityClean],
  ['transliterate', disarm.transliterate],
  ['stripAccents', disarm.stripAccents],
  ['foldCase', disarm.foldCase],
  ['collapseWhitespace', disarm.collapseWhitespace],
  ['searchKey', disarm.searchKey],
  ['sortKey', disarm.sortKey],
  ['catalogKey', disarm.catalogKey],
]

const HI = '\uD83D' // lone high surrogate
const LO = '\uDCA0' // lone low surrogate
const PAIR = '😀' // a well-formed high+low pair = U+1F600; must stay astral, not become "��"
const INPUTS = [
  HI,
  LO,
  `abc${HI}`,
  `${HI}abc`,
  `a${HI}b${LO}c`,
  `PаyPal${HI}  ‮ rld${LO}`,
  PAIR,
  `x${PAIR}y`,
  `${HI}${PAIR}`, // lone high then a pair
]

describe('surrogate contract (#469)', () => {
  for (const [name, fn] of ENTRYPOINTS) {
    for (const input of INPUTS) {
      test(`${name}: surrogate input behaves as its WTF-8->UTF-8 form`, () => {
        expect(() => fn(input)).not.toThrow()
        expect(fn(input)).toBe(fn(canonical(input)))
      })
    }

    test(`${name}: valid astral is unaffected`, () => {
      const astral = '\u{1F600} grin \u{103FF}'
      expect(fn(astral)).toBe(fn(canonical(astral)))
    })
  }
})
