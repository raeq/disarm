#!/usr/bin/env python3
"""Does an installed disarm import and work? (#667, #669)

Every other gate in this repository tests a *development environment*. The local
pre-push gate uses ``maturin develop``, an editable install into a virtualenv
that already holds pytest, hypothesis, mypy and sybil. CI builds a wheel, installs
it, and then installs the project again from source with its test extras on top —
so what pytest imports afterwards is not reliably the wheel that was built, and
the wheel is never imported on its own.

Three things that leaves uncovered:

* **The sdist is built at publish time and never installed.** So
  ``pip install git+https://github.com/raeq/disarm`` and ``pip install disarm``
  on any platform without a matching wheel both take a path nobody has executed
  before a user executes it. If a ``src/tables/data/*.tsv`` or a ``build.rs``
  input ever fell out of the sdist file list, the first person to find out would
  be a user.
* **A missing runtime dependency cannot be detected**, because the wheel is only
  ever imported alongside the test extras, which would satisfy it.
* **The tree on ``main`` is never built at all** — ``ci.yml`` runs on
  ``pull_request`` only, so the commit that lands is the one commit nothing checks.

This script is the body those gates share. It deliberately imports nothing but
``disarm`` and the standard library, so it runs in a virtualenv containing the
artifact and nothing else.

Run it from a directory **outside** the checkout. A source tree on ``sys.path``
shadows the installed package and the check passes without testing an install at
all — which is the failure it exists to find.

    python scripts/smoke_installed.py

Exit status is 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

from pathlib import Path

FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok    {label}")
        return
    FAILURES.append(f"{label}{f' — {detail}' if detail else ''}")
    print(f"  FAIL  {label}{f' — {detail}' if detail else ''}")


def main() -> int:
    print("disarm installed-artifact smoke test")

    # --- the import itself ---------------------------------------------------
    try:
        import disarm
    except Exception as exc:  # noqa: BLE001 — any failure here is the finding
        print(f"  FAIL  import disarm — {type(exc).__name__}: {exc}")
        return 1
    print(f"  ok    import disarm  ({disarm.__file__})")

    # A source tree reachable on sys.path — through the working directory, or
    # through PYTHONPATH, or through anything else — shadows the installed
    # package, and every check below would then pass without an install existing.
    #
    # Anchored on *this script's* location rather than the working directory.
    # A cwd-based check passes whenever cwd is outside the repository, which is
    # exactly how CI invokes it, so PYTHONPATH pointing at the checkout would
    # have walked straight through.
    checkout = Path(__file__).resolve().parent.parent
    module = Path(disarm.__file__).resolve()
    check(
        "not imported from the checkout",
        checkout not in module.parents,
        f"imported {module}, which is inside {checkout} — a source tree is "
        "shadowing the installed package, so nothing below tests an install",
    )
    check(
        "imported from an installed location",
        any(part in {"site-packages", "dist-packages"} for part in module.parts),
        f"imported {module}, which is not in site-packages or dist-packages",
    )

    # --- the version ---------------------------------------------------------
    # `python/disarm/__init__.py` falls back to "0.0.0+unknown" when distribution
    # metadata is absent, so an import that resolved to a source tree still
    # produces a usable-looking module. Asserting the import succeeded is not
    # enough; the version is what distinguishes an install from a directory.
    version = getattr(disarm, "__version__", None)
    check("__version__ is present", isinstance(version, str) and bool(version))
    check(
        "__version__ is not the missing-metadata fallback",
        version != "0.0.0+unknown",
        f"got {version!r} — the package is importable but not installed",
    )
    print(f"        version = {version!r}")

    # --- one call per public surface -----------------------------------------
    # Not a test suite. One representative call each, so that a packaging failure
    # which leaves a data table out of the artifact shows up as a failure here
    # rather than in somebody's production pipeline.
    surfaces: list[tuple[str, object, object]] = [
        ("preset: canonicalize", lambda: disarm.canonicalize("Ηello Ꮤorld"), "Hello World"),
        ("preset: strip_obfuscation", lambda: disarm.strip_obfuscation("рroduсt"), "product"),
        ("key builder: search_key", lambda: disarm.search_key("  Café  RÉSUMÉ  "), "cafe resume"),
        ("key builder: catalog_key", lambda: disarm.catalog_key("ΩMEGA  café"), "omega cafe"),
        ("transform: transliterate", lambda: disarm.transliterate("Москва"), "Moskva"),
        ("transform: slugify", lambda: disarm.slugify("Hello, World!"), "hello-world"),
        ("predicate: is_confusable", lambda: disarm.is_confusable("раypal"), True),
        ("detector: has_anomalies", lambda: disarm.has_anomalies("ad​min"), True),
        ("detector: has_anomalies (clean)", lambda: disarm.has_anomalies("admin"), False),
        ("builder: Text", lambda: str(disarm.Text("Café").transliterate()), "Cafe"),
    ]
    for label, call, expected in surfaces:
        try:
            got = call()  # type: ignore[operator]
        except Exception as exc:  # noqa: BLE001 — any failure here is the finding
            check(label, False, f"{type(exc).__name__}: {exc}")
            continue
        check(label, got == expected, f"expected {expected!r}, got {got!r}")

    # --- the one documented path that raises on every released artifact -------
    # `[tool.maturin]` does not ship `data/*.bin`; the context dictionaries are
    # located at runtime through DISARM_DICT_DIR. The behaviour is intended and
    # the message is good. It is still a public API path that raises on every
    # artifact, so the gate decides about it explicitly rather than discovering
    # it on the first run.
    try:
        disarm.transliterate("مرحبا بالعالم", context=True)
    except disarm.DisarmError as exc:
        check(
            "context=True raises with the bootstrap instructions",
            "bootstrap_dicts.sh" in str(exc),
            f"raised DisarmError without naming the fix: {exc}",
        )
    except Exception as exc:  # noqa: BLE001
        check("context=True raises DisarmError", False, f"raised {type(exc).__name__}: {exc}")
    else:
        # Not a failure: a build that bundles the dictionaries is legitimate.
        # Saying so out loud keeps the artifact under test identifiable.
        print("  note  context=True succeeded — this build has the dictionaries")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed:")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1
    print(f"all {len(surfaces) + 5} checks passed against disarm {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
