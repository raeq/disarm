// Runs the pinned transforms of a practitioner generator and prints their outputs.
//
// Written for disarm's meta-benchmark, not taken from the upstream project. The
// suite passes this file to `node --permission --allow-fs-read=<root> -e`, after
// checking the digest of the tree, so the permission model is the security
// boundary: no other file, no write, no child process and no network. The `vm`
// context below only keeps the module loader simple. It is not a boundary.
//
// stdin:  {"transforms": ["unicode/bold.js", ...], "texts": ["...", ...], "seed": 1}
// stdout: {"unicode/bold.js": {"outputs": ["...", ...], "error": null}, ...}
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const CALL_TIMEOUT_MS = 2000;

const root = process.argv[1];
const request = JSON.parse(fs.readFileSync(0, "utf8"));

let randomState = request.seed;

// mulberry32. A transform that draws random numbers, such as zalgo, then gives the
// same output on every run, and a baseline can compare two runs of it.
function seededRandom() {
  randomState = (randomState + 0x6d2b79f5) | 0;
  let t = Math.imul(randomState ^ (randomState >>> 15), 1 | randomState);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}

function splitEmojis(text) {
  const segmenter = new Intl.Segmenter("en", { granularity: "grapheme" });
  return Array.from(segmenter.segment(text), ({ segment }) => segment);
}

const context = vm.createContext({
  TextEncoder,
  TextDecoder,
  __seededRandom: seededRandom,
  window: { EmojiUtils: { splitEmojis } },
});
vm.runInContext("Math.random = __seededRandom;", context);

// The upstream modules are ES modules that a bundler joins. Loading one here means
// removing its import of the base class and turning its export into a return.
const base = fs.readFileSync(path.join(root, "BaseTransformer.js"), "utf8");
vm.runInContext(
  base.replace(/^export\s+default\s+.*$/m, "").replace(/^export\s+class\s+/m, "class "),
  context,
);

function load(relative) {
  const source = fs
    .readFileSync(path.join(root, relative), "utf8")
    .replace(/^\s*import\s+.*BaseTransformer.*$/m, "")
    .replace(/export\s+default\s+/, "return ");
  return vm.runInContext(`(function () {\n${source}\n})()`, context, {
    timeout: CALL_TIMEOUT_MS,
  });
}

const results = {};
for (const relative of request.transforms) {
  try {
    context.__transform = load(relative);
    const outputs = [];
    for (const text of request.texts) {
      randomState = request.seed;
      context.__text = text;
      const output = vm.runInContext("__transform.func(__text)", context, {
        timeout: CALL_TIMEOUT_MS,
      });
      if (typeof output !== "string") {
        throw new TypeError(`func returned ${typeof output}`);
      }
      outputs.push(output);
    }
    results[relative] = { outputs, error: null };
  } catch (error) {
    results[relative] = { outputs: [], error: String(error && error.message) };
  }
}
process.stdout.write(JSON.stringify(results));
