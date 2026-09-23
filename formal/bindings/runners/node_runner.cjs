// Harness runner for the Node binding: the public idiomatic layer (bindings/node/index.js).
// Protocol: see ../rust_oracle/src/main.rs and ../README.md ("The harness").
'use strict'
const fs = require('node:fs')
const path = require('node:path')
const zlib = require('node:zlib')
const d = require(path.join(__dirname, '..', '..', '..', 'bindings', 'node', 'index.js'))

const NSCALAR = 0x110000 - 0x800
const BLOCK = 4096

class Rec {
  constructor(...fields) {
    this.fields = fields
  }
}

function enc(v, out) {
  if (typeof v === 'boolean') out.push(Buffer.from(v ? 'b1' : 'b0'))
  else if (typeof v === 'number' || typeof v === 'bigint') {
    if (typeof v === 'number' && !Number.isInteger(v)) throw new Error(`non-integer ${v}`)
    out.push(Buffer.from(`i${v};`))
  } else if (v === null || v === undefined) out.push(Buffer.from('n'))
  else if (typeof v === 'string') {
    const b = Buffer.from(v, 'utf8')
    out.push(Buffer.from(`s${b.length}:`), b)
  } else if (v instanceof Rec) {
    out.push(Buffer.from(`r${v.fields.length}:`))
    for (const f of v.fields) enc(f, out)
  } else if (Array.isArray(v)) {
    out.push(Buffer.from(`l${v.length}:`))
    for (const x of v) enc(x, out)
  } else throw new Error(`cannot encode ${typeof v}`)
}

function encodeCall(fn, t) {
  const out = []
  let v
  try {
    v = fn(t)
  } catch (e) {
    const kind =
      e instanceof d.DisarmInvalidArgument ? 'inv' : e instanceof d.DisarmError ? 'err' : `js:${e && e.name}`
    out.push(Buffer.from(`e${kind}:`))
    enc(String(e && e.message), out)
    return Buffer.concat(out)
  }
  enc(v, out)
  return Buffer.concat(out)
}

const host = (a) =>
  new Rec(
    a.suspicious,
    a.scripts,
    a.mixedScript,
    a.hasConfusables,
    a.bidiConflict,
    a.bidiControl,
    a.hasInvisible,
    a.compatFold,
    a.crossLabelScript,
    a.labelScripts,
    a.wholeScriptConfusable,
    a.labelWholeScriptConfusable,
    a.canonical,
  )
const anomalies = (r) =>
  new Rec(
    r.anomalous,
    r.kinds,
    r.findings.map((f) => new Rec(f.kind, f.token, f.start, f.end, f.detail, f.reason)),
    r.reason,
  )

const CASES = {
  tr: (t) => d.transliterate(t),
  tr_iso9: (t) => d.transliterate(t, { scheme: 'strict_iso9' }),
  tr_gost: (t) => d.transliterate(t, { scheme: 'gost7034' }),
  tr_de: (t) => d.transliterate(t, { lang: 'de' }),
  tr_auto: (t) => d.transliterate(t, { lang: 'auto' }),
  tr_uk: (t) => d.transliterate(t, { lang: 'uk' }),
  tr_ja: (t) => d.transliterate(t, { lang: 'ja' }),
  tr_bad: (t) => d.transliterate(t, { lang: 'xx' }),
  nc_lat: (t) => d.normalizeConfusables(t, { target: 'latin' }),
  nc_lat_tr39: (t) => d.normalizeConfusables(t, { target: 'latin', digitPolicy: 'tr39' }),
  nc_lat_pres: (t) => d.normalizeConfusables(t, { target: 'latin', digitPolicy: 'preserve' }),
  nc_cyr: (t) => d.normalizeConfusables(t, { target: 'cyrillic' }),
  nc_ara: (t) => d.normalizeConfusables(t, { target: 'arabic' }),
  nc_heb: (t) => d.normalizeConfusables(t, { target: 'hebrew' }),
  sa: (t) => d.stripAccents(t),
  fc: (t) => d.foldCase(t),
  cfs: (t) => d.isCaseFoldStable(t),
  dj: (t) => d.demojize(t),
  dj_sm: (t) => d.demojize(t, { stripModifiers: true }),
  re_empty: (t) => d.replaceEmoji(t, ''),
  re_sp: (t) => d.replaceEmoji(t, ' '),
  cw: (t) => d.collapseWhitespace(t),
  scc: (t) => d.stripControlChars(t),
  szw: (t) => d.stripZeroWidthChars(t),
  sbd: (t) => d.stripBidi(t),
  stg: (t) => d.stripTags(t),
  svs: (t) => d.stripVariationSelectors(t),
  snc: (t) => d.stripNoncharacters(t),
  spua: (t) => d.stripPua(t),
  can: (t) => d.canonicalize(t),
  can_tr39: (t) => d.canonicalize(t, { digitPolicy: 'tr39' }),
  can_pres: (t) => d.canonicalize(t, { digitPolicy: 'preserve' }),
  cans: (t) => d.canonicalizeStrict(t),
  sfmt: (t) => d.stripFormat(t),
  sobf: (t) => d.stripObfuscation(t),
  sobf_tr39: (t) => d.stripObfuscation(t, { digitPolicy: 'tr39' }),
  sk: (t) => d.searchKey(t),
  sk_de: (t) => d.searchKey(t, { lang: 'de' }),
  sok: (t) => d.sortKey(t),
  ck: (t) => d.catalogKey(t),
  ck_iso: (t) => d.catalogKey(t, { strictIso9: true }),
  skel: (t) => d.skeletonKey(t),
  skel_tr39: (t) => d.skeletonKey(t, { digitPolicy: 'tr39' }),
  nfc: (t) => d.normalize(t, { form: 'NFC' }),
  nfd: (t) => d.normalize(t, { form: 'NFD' }),
  nfkc: (t) => d.normalize(t, { form: 'NFKC' }),
  nfkd: (t) => d.normalize(t, { form: 'NFKD' }),
  isn_nfc: (t) => d.isNormalized(t, { form: 'NFC' }),
  mix: (t) => d.isMixedScript(t),
  bconf: (t) => d.hasBidiConflict(t),
  bctl: (t) => d.hasBidiControl(t),
  susp: (t) => d.isSuspiciousHostname(t),
  ah: (t) => host(d.analyzeHostname(t)),
  ah_c: (t) => host(d.analyzeHostname(t, { contractions: true })),
  glen: (t) => d.graphemeLen(t),
  gsplit: (t) => d.graphemeSplit(t),
  gtrunc1: (t) => d.graphemeTruncate(t, 1),
  tw: (t) => d.terminalWidth(t),
  tw_amb: (t) => d.terminalWidth(t, { ambiguousWide: true }),
  ial: (t) => {
    const a = d.inspectAutoLang(t)
    return new Rec(a.script, a.chosenLang, a.reason, a.discriminatorsHit)
  },
  ds: (t) => d.detectScripts(t),
  iscan: (t) => d.isCanonical(t),
  mln: (t) => d.mlNormalize(t),
  mln_nofold: (t) => d.mlNormalize(t, { foldCase: false }),
  sfn: (t) => d.sanitizeFilename(t),
  ia: (t) => anomalies(d.inspectAnomalies(t)),
  ha: (t) => d.hasAnomalies(t),
  ed: (t) => d.editDistance(t, 'paypal'),
  fu: (t) => d.findUntranslatable(t).map((u) => new Rec(u.char, u.offset)),
  fuc: (t) => d.findUnmappedConfusables(t).map((u) => new Rec(u.char, u.offset)),
  rv_ru: (t) => d.reverseTransliterate(t, { lang: 'ru' }),
  rv_el: (t) => d.reverseTransliterate(t, { lang: 'el' }),
  rv_uk: (t) => d.reverseTransliterate(t, { lang: 'uk' }),
  slug: (t) => d.slugify(t),
  zs: (t) => d.stripZalgo(t, { maxMarks: 3 }),
  zi: (t) => d.isZalgo(t, { threshold: 3 }),
  isconf: (t) => d.isConfusable(t),
}

// `surr N SEED`: the malformed-Unicode contract (THREAT_MODEL.md, #469) relationally:
// f(s) must equal f(s.toWellFormed()) for strings of random UTF-16 code units, where
// toWellFormed() keeps pairs and turns each lone surrogate into one U+FFFD.
function surrogateCheck(n, seed) {
  let x = seed >>> 0
  const rnd = () => {
    x = (x + 0x6d2b79f5) >>> 0
    let t = x
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
  const pick = (a) => a[Math.floor(rnd() * a.length)]
  const unit = [
    () => String.fromCharCode(0xd800 + Math.floor(rnd() * 0x400)),
    () => String.fromCharCode(0xdc00 + Math.floor(rnd() * 0x400)),
    () => String.fromCharCode(0x61 + Math.floor(rnd() * 26)),
    () => ' ',
    () => String.fromCharCode(pick([0xe9, 0x430, 0x5d0, 0x301, 0x200b, 0x202e])),
    () => String.fromCodePoint(0x1f600 + Math.floor(rnd() * 0x50)),
  ]
  const strings = []
  for (let i = 0; i < n; i++) {
    let s = ''
    const len = 1 + Math.floor(rnd() * 12)
    for (let j = 0; j < len; j++) s += pick(unit)()
    strings.push(s)
  }
  const lines = []
  for (const [c, fn] of Object.entries(CASES)) {
    const bad = strings.filter((s) => !encodeCall(fn, s).equals(encodeCall(fn, s.toWellFormed())))
    const ex = bad.length ? JSON.stringify(bad[0]) : ''
    lines.push(`${c}\t${strings.length}\t${bad.length}\t${ex}`)
  }
  process.stdout.write(`${lines.join('\n')}\n`)
}

function main() {
  const [mode, corpusPath, arg3, lo0, hi0] = process.argv.slice(2)
  if (mode === 'list') {
    process.stdout.write(`${Object.keys(CASES).join(',')}\n`)
    return
  }
  if (mode === 'surr') {
    surrogateCheck(Number(corpusPath), Number(arg3))
    return
  }
  // An empty line is a valid corpus entry (the empty string); keep line count exact.
  const raw = fs.readFileSync(corpusPath, 'ascii').split('\n')
  raw.pop()
  const corpus = raw.map((l) => Buffer.from(l, 'hex').toString('utf8'))
  const total = NSCALAR + corpus.length
  const inp = (i) => (i < NSCALAR ? String.fromCodePoint(i < 0xd800 ? i : i + 0x800) : corpus[i - NSCALAR])
  const lines = []
  if (mode === 'crc') {
    for (const c of arg3.split(',')) {
      if (!(c in CASES)) continue
      for (let b = 0; b * BLOCK < total; b++) {
        const lo = b * BLOCK
        const hi = Math.min(lo + BLOCK, total)
        let crc = 0
        for (let i = lo; i < hi; i++) crc = zlib.crc32(encodeCall(CASES[c], inp(i)), crc)
        lines.push(`${c}\t${b}\t${(crc >>> 0).toString(16).padStart(8, '0')}\t${hi - lo}`)
      }
    }
  } else if (mode === 'dump') {
    const hi = Math.min(Number(hi0), total)
    for (let i = Number(lo0); i < hi; i++) lines.push(`${i}\t${encodeCall(CASES[arg3], inp(i)).toString('hex')}`)
  } else throw new Error(`unknown mode ${mode}`)
  process.stdout.write(`${lines.join('\n')}\n`)
}

main()
