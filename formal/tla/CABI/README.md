# Ownership and input protocol of the C ABI (TLA+/TLC)

`CABI.tla` models one C client of `bindings/cabi` against the code as written: which
side allocates, which function frees, what `NULL` means for each argument and result,
what an empty result is, and what the library assumes about its input bytes. It is one
part of the bindings study; the findings it supports (C1-C3), the correspondence of
every model element to a file and line, and the reproductions on the real library are in
[`../../bindings/README.md`](../../bindings/README.md) ("The C ABI").

Baseline: `595fbda`, safer-ffi 0.1.13, TLC 2.19 (tla2tools 1.7.4).

| Config | Result |
|---|---|
| `CABI_utf8.cfg` | `NoInvalidUtf8UB` violated (C1) |
| `CABI_null.cfg` | `NoNullArgUB` violated (C2) |
| `CABI_write.cfg` | `NoWriteToStatic` violated (C3) |
| `CABI_truncate.cfg` | `NoLayoutMismatch` violated (C3) |
| `CABI_alias.cfg` | `NoAlias` violated (C3) |
| `CABI_contract.cfg` | pass: the code is sound for a client that keeps the unwritten rules |
| `CABI_fixed.cfg` | pass: the proposed fix, every input the header admits |

```bash
TLA2TOOLS=/path/to/tla2tools.jar bash run_tlc.sh     # compares every verdict with expected.tsv
TLA2TOOLS=/path/to/tla2tools.jar python3 mutants.py  # each invariant must catch its mutant
```

A pass covers every interleaving of the configured number of calls (two or three), not
every number.
