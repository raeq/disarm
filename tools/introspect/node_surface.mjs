// Emit disarm's LIVE Node public surface as a JSON array of exported function names.
//
// Reality, not source-scraping: import the built addon's TypeScript entrypoint and
// read what it actually exports. Functions are camelCase; PascalCase exports
// (the `Lexicon` class, error classes) are excluded to match the manifest's op
// granularity. The parity checker (scripts/parity_check.py) diffs this against the
// manifest. Run after `npm run build:debug`:
//
//   node tools/introspect/node_surface.mjs > surfaces/node.json
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const mod = await import(resolve(here, "../../bindings/node/index.js"));

const names = Object.keys(mod)
  .filter((k) => typeof mod[k] === "function" && /^[a-z]/.test(k))
  .sort();
console.log(JSON.stringify(names));
