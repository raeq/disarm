"""CLI for disarm — fast Unicode transliteration, slugification, and text normalization.

Usage:
    disarm t "café résumé"                        # transliterate
    disarm t --lang de "Ärger"                    # with language
    disarm t --target ru "Moskva"                 # reverse transliteration
    disarm s "Hello World"                        # slugify
    disarm n --form NFKC "ﬁ"                     # normalize
    disarm p --steps "normalize,fold_case" "input" # pipeline
    disarm d "Hello 😀"                           # demojize
    disarm scan src/ --json                       # find anomalies in a tree
    echo "piped input" | disarm t                 # pipe via stdin
"""

from __future__ import annotations

import argparse
import sys

from disarm import DisarmError, TextPipeline, demojize, normalize, slugify, transliterate


def _read_input(args_text: list[str]) -> str:
    """Read input from positional args or stdin."""
    if args_text:
        return " ".join(args_text)
    if not sys.stdin.isatty():
        return sys.stdin.read().rstrip("\n")
    print("Error: no input provided (pass as argument or pipe via stdin)", file=sys.stderr)
    sys.exit(1)


def cmd_transliterate(args: argparse.Namespace) -> None:
    text = _read_input(args.text)
    result = transliterate(
        text,
        lang=args.lang,
        target=args.target,
        strict_iso9=args.strict_iso9,
        gost7034=args.gost7034,
        tones=args.tones,
    )
    print(result)


def cmd_slugify(args: argparse.Namespace) -> None:
    text = _read_input(args.text)
    kwargs: dict[str, object] = {}
    if args.lang is not None:  # #250 C3: the subparser declared --lang but it was ignored
        kwargs["lang"] = args.lang
    if args.separator is not None:
        kwargs["separator"] = args.separator
    if args.max_length is not None:
        kwargs["max_length"] = args.max_length
    result = slugify(text, **kwargs)  # type: ignore[call-overload]
    print(result)


def cmd_normalize(args: argparse.Namespace) -> None:
    text = _read_input(args.text)
    result = normalize(text, form=args.form)
    print(result)


def cmd_pipeline(args: argparse.Namespace) -> None:
    text = _read_input(args.text)
    steps = [s.strip() for s in args.steps.split(",")]
    kwargs: dict[str, object] = {}
    for step in steps:
        if step == "normalize":
            kwargs["normalize"] = args.form or "NFC"
        elif step == "strip_zalgo":
            # #250 C6: strip_zalgo takes a value (max combining marks per base char).
            kwargs["strip_zalgo"] = args.zalgo_max_marks
        elif step in (
            "transliterate",
            "fold_case",
            "collapse_whitespace",
            "strip_accents",
            "confusables",
            "strip_control",
            "strip_zero_width",
            "demojize",
            "strip_bidi",  # #250 C6: was supported by TextPipeline but unreachable from the CLI
            "strip_pua",  # #911: same, and the reason a composed pipeline kept the PUA
            "strip_plane14",  # #914: the TAG block, reachable only via demojize before
            "resolve_deletions",  # #937: BS/DEL erase the preceding cell
            # A parameter of `resolve_deletions` rather than a step of its own, and
            # inert without it. Reachable here so the CLI can express the same
            # pipeline the library can (#937).
            "resolve_cr",
            # Also unreachable until #911 went looking. `lang` stays out on purpose: it
            # takes a value, so it needs its own flag rather than a --steps entry.
            "strict_iso9",
            "gost7034",
        ):
            kwargs[step] = True
        else:
            print(f"Error: unknown pipeline step '{step}'", file=sys.stderr)
            sys.exit(1)
    pipe = TextPipeline(**kwargs)  # type: ignore[arg-type]
    print(pipe(text))


def cmd_demojize(args: argparse.Namespace) -> None:
    text = _read_input(args.text)
    result = demojize(text)
    print(result)


def cmd_scan(args: argparse.Namespace) -> None:
    """Walk paths and report anomalies (#704).

    Returns through `sys.exit` with the scanner's own code rather than falling off the
    end, because the contract is the point: 0 clean, 1 findings under `--fail`, 3 a path
    could not be read. `main()`'s `DisarmError` handler exits 1 for API errors, and a
    scan that found something must not be confused with one that failed.
    """
    from pathlib import Path

    from disarm.scan import EXIT_READ_ERROR, run

    try:
        code = run(
            [Path(p) for p in args.paths],
            as_json=args.json,
            as_sarif=args.sarif,
            fail=args.fail,
            use_gitignore=not args.no_gitignore,
            baseline=Path(args.baseline) if args.baseline else None,
            write_baseline_to=Path(args.write_baseline) if args.write_baseline else None,
        )
    except OSError as exc:
        # A baseline file that cannot be read or written is a read error, code 3 — not a
        # traceback, and not the same number as "something was found".
        print(f"error: {exc.filename or ''}: {exc.strerror or exc}", file=sys.stderr)
        sys.exit(EXIT_READ_ERROR)
    sys.exit(code)


def _add_transliterate_parser(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register transliterate subcommand with both long and short names."""
    for name in ("transliterate", "t"):
        p = sub.add_parser(name, help="Transliterate Unicode text to ASCII")
        p.add_argument("text", nargs="*", help="Input text (or pipe via stdin)")
        lang_group = p.add_mutually_exclusive_group()
        lang_group.add_argument(
            "--lang", default=None, help="Language code (e.g. de, ja, zh, auto)"
        )
        lang_group.add_argument(
            "--target",
            default=None,
            help="Reverse transliteration target script (e.g. ru, uk, el)",
        )
        p.add_argument(
            "--strict-iso9",
            action="store_true",
            default=False,
            help="Use strict ISO 9 transliteration",
        )
        p.add_argument(
            "--gost7034", action="store_true", default=False, help="Use GOST 7.034 transliteration"
        )
        p.add_argument(
            "--tones", action="store_true", default=False, help="Include tone marks (Chinese)"
        )
        p.set_defaults(func=cmd_transliterate)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="disarm",
        description="Fast Unicode transliteration, slugification, and text normalization.",
        epilog=(
            "commands:\n"
            "  transliterate (t)  Transliterate Unicode text to ASCII\n"
            "  slugify (s)        Generate URL-safe slugs\n"
            "  normalize (n)      Unicode normalization (NFC/NFD/NFKC/NFKD)\n"
            "  pipeline (p)       Run a multi-step TextPipeline\n"
            "  demojize (d)       Expand emoji to text descriptions\n"
            "  scan (sc)          Walk files and report anomalies\n"
            "\n"
            "examples:\n"
            '  disarm t "café résumé"             transliterate\n'
            '  disarm t --lang de "Ärger"         German rules\n'
            '  disarm t --target ru "Moskva"      reverse to Cyrillic\n'
            '  disarm s "Hello World"              slugify\n'
            '  echo "input" | disarm t             pipe via stdin\n'
            "  disarm scan src/ --fail             gate CI on hidden characters"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # transliterate (+ short form "t")
    _add_transliterate_parser(sub)

    # slugify (+ short form "s")
    for name in ("slugify", "s"):
        p = sub.add_parser(name, help="Generate URL-safe slugs")
        p.add_argument("text", nargs="*", help="Input text (or pipe via stdin)")
        p.add_argument("--lang", default=None, help="Language code (e.g. de, ja)")
        p.add_argument("--separator", default=None, help="Separator character (default: -)")
        p.add_argument("--max-length", type=int, default=None, help="Maximum slug length")
        p.set_defaults(func=cmd_slugify)

    # normalize (+ short form "n")
    for name in ("normalize", "n"):
        p = sub.add_parser(name, help="Unicode normalization")
        p.add_argument("text", nargs="*", help="Input text (or pipe via stdin)")
        p.add_argument(
            "--form",
            default="NFC",
            choices=["NFC", "NFD", "NFKC", "NFKD"],
            help="Normalization form (default: NFC)",
        )
        p.set_defaults(func=cmd_normalize)

    # pipeline (+ short form "p")
    for name in ("pipeline", "p"):
        p = sub.add_parser(name, help="Run a TextPipeline with specified steps")
        p.add_argument("text", nargs="*", help="Input text (or pipe via stdin)")
        p.add_argument(
            "--steps",
            required=True,
            help="Comma-separated steps: normalize,transliterate,fold_case,"
            "collapse_whitespace,strip_accents,confusables,strip_control,"
            "strip_zero_width,demojize,strip_bidi,strip_zalgo,strip_pua,strip_plane14,"
            "resolve_deletions,resolve_cr,"
            "strict_iso9,gost7034",
        )
        p.add_argument("--form", default=None, help="Normalization form for normalize step")
        p.add_argument(
            "--zalgo-max-marks",
            type=int,
            default=0,
            help="Max combining marks per base char for the strip_zalgo step (default: 0)",
        )
        p.set_defaults(func=cmd_pipeline)

    # demojize (+ short form "d")
    for name in ("demojize", "d"):
        p = sub.add_parser(name, help="Expand emoji to text descriptions")
        p.add_argument("text", nargs="*", help="Input text (or pipe via stdin)")
        p.set_defaults(func=cmd_demojize)

    # scan (+ short form "sc") — #704: the one API built for scanning, pointed at files
    for name in ("scan", "sc"):
        p = sub.add_parser(name, help="Walk files and report anomalies")
        p.add_argument("paths", nargs="+", help="Files or directories to scan")
        fmt = p.add_mutually_exclusive_group()
        fmt.add_argument("--json", action="store_true", help="Emit findings as JSON")
        fmt.add_argument(
            "--sarif",
            action="store_true",
            help="Emit SARIF 2.1.0, for GitHub's Security tab and PR annotations (#705)",
        )
        p.add_argument(
            "--baseline",
            metavar="FILE",
            default=None,
            help="Suppress findings recorded in FILE; report entries that no longer match",
        )
        p.add_argument(
            "--write-baseline",
            metavar="FILE",
            default=None,
            help="Record every current finding to FILE and exit, so only new ones fail later",
        )
        p.add_argument(
            "--fail",
            action="store_true",
            help="Exit 1 if anything is found (for CI); 3 if a path could not be read",
        )
        p.add_argument(
            "--no-gitignore",
            action="store_true",
            help="Do not ask git which paths it ignores",
        )
        p.set_defaults(func=cmd_scan)

    args = parser.parse_args()

    try:
        args.func(args)
    except (DisarmError, ValueError) as exc:
        # #250 C7: surface API errors (bad --lang/--form, contradictory flags) as
        # a clean message + non-zero exit instead of a traceback, matching the
        # handling already used for unknown steps / missing input.
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
