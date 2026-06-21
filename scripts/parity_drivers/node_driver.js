// Node parity driver (local only). Reads a JSON job, calls each op on each
// input through the prebuilt Node binding, prints a JSON results map.
// Usage: node node_driver.js <jobfile.json> <repoRoot>
// job: { inputs: [str, ...], ops: [[opId, nodeName], ...] }
// out: { opId: [ {v: value} | {e: "message"} , ... ] }
const path = require("path");
const fs = require("fs");

const jobfile = process.argv[2];
const root = process.argv[3] || path.join(__dirname, "..", "..");
const binding = require(path.join(root, "bindings", "node", "index.js"));
const job = JSON.parse(fs.readFileSync(jobfile, "utf8"));

const out = {};
for (const [opId, nodeName] of job.ops) {
  const fn = binding[nodeName];
  out[opId] = job.inputs.map((s) => {
    if (typeof fn !== "function") return { e: "no-export" };
    try {
      return { v: fn(s) };
    } catch (err) {
      return { e: String((err && err.message) || err).slice(0, 100) };
    }
  });
}
process.stdout.write(JSON.stringify(out));
