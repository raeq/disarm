"""CLI for translit — fast Unicode transliteration, slugification, and text normalization.

Usage:
    translit t "café résumé"                        # transliterate
    translit t --lang de "Ärger"                    # with language
    translit t --target ru "Moskva"                 # reverse transliteration
    translit s "Hello World"                        # slugify
    translit n --form NFKC "ﬁ"                     # normalize
    translit p --steps "normalize,fold_case" "input" # pipeline
    translit d "Hello 😀"                           # demojize
    echo "piped input" | translit t                 # pipe via stdin
"""

from __future__ import annotations

import argparse
import sys

from translit import TextPipeline, demojize, normalize, slugify, transliterate


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
    if args.separator is not None:
        kwargs["separator"] = args.separator
    if args.max_length is not None:
        kwargs["max_length"] = args.max_length
    result = slugify(text, **kwargs)  # type: ignore[arg-type]
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
        elif step in (
            "transliterate",
            "fold_case",
            "collapse_whitespace",
            "strip_accents",
            "confusables",
            "strip_control",
            "strip_zero_width",
            "demojize",
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


def _add_transliterate_parser(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register transliterate subcommand with both long and short names."""
    for name in ("transliterate", "t"):
        p = sub.add_parser(name, help="Transliterate Unicode text to ASCII")
        p.add_argument("text", nargs="*", help="Input text (or pipe via stdin)")
        lang_group = p.add_mutually_exclusive_group()
        lang_group.add_argument("--lang", default=None, help="Language code (e.g. de, ja, zh, auto)")
        lang_group.add_argument(
            "--target",
            default=None,
            help="Reverse transliteration target script (e.g. ru, uk, el)",
        )
        p.add_argument(
            "--strict-iso9", action="store_true", default=False, help="Use strict ISO 9 transliteration"
        )
        p.add_argument(
            "--gost7034", action="store_true", default=False, help="Use GOST 7.034 transliteration"
        )
        p.add_argument("--tones", action="store_true", default=False, help="Include tone marks (Chinese)")
        p.set_defaults(func=cmd_transliterate)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="translit",
        description="Fast Unicode transliteration, slugification, and text normalization.",
        epilog=(
            "commands:\n"
            "  transliterate (t)  Transliterate Unicode text to ASCII\n"
            "  slugify (s)        Generate URL-safe slugs\n"
            "  normalize (n)      Unicode normalization (NFC/NFD/NFKC/NFKD)\n"
            "  pipeline (p)       Run a multi-step TextPipeline\n"
            "  demojize (d)       Expand emoji to text descriptions\n"
            "\n"
            "examples:\n"
            '  translit t "café résumé"             transliterate\n'
            '  translit t --lang de "Ärger"         German rules\n'
            '  translit t --target ru "Moskva"      reverse to Cyrillic\n'
            '  translit s "Hello World"              slugify\n'
            '  echo "input" | translit t             pipe via stdin'
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
            "strip_zero_width,demojize",
        )
        p.add_argument("--form", default=None, help="Normalization form for normalize step")
        p.set_defaults(func=cmd_pipeline)

    # demojize (+ short form "d")
    for name in ("demojize", "d"):
        p = sub.add_parser(name, help="Expand emoji to text descriptions")
        p.add_argument("text", nargs="*", help="Input text (or pipe via stdin)")
        p.set_defaults(func=cmd_demojize)

    args = parser.parse_args()

    args.func(args)


if __name__ == "__main__":
    main()
