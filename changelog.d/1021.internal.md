- **Formal models of the whole library (#PR).** Six more models join `formal/`, each
  validated against the library by differential testing before a proof or a
  counterexample counted: the confusable fold (`formal/lean/Confusables`), the
  detectors (`formal/lean/Detection`), the presets and pipeline profiles
  (`formal/lean/Presets`), the output sanitizers (`formal/lean/Sanitizers`), the text
  primitives (`formal/lean/Text`), and a differential harness over all five bindings
  with a TLA+ model of the C ABI (`formal/bindings`, `formal/tla/CABI`).
  `.github/workflows/formal.yml` builds every new Lean project and model-checks the C
  ABI against its expected verdicts. `formal/README.md` and
  `docs/formal-verification.md` index what each model found and where it was fixed.
