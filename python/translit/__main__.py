"""CLI entrypoint for translit-rs Docker image.

Usage:
    python -m translit transliterate "café résumé"
    python -m translit slugify "Hello World"
    python -m translit normalize --form NFKC "ﬁ"
    python -m translit pipeline --steps "normalize,fold_case,transliterate" "input"
    python -m translit demojize "Hello 😀"
    echo "piped input" | python -m translit slugify
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
    result = transliterate(text, lang=args.lang)
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


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="translit",
        description="Fast Unicode transliteration, slugification, and text normalization",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # transliterate
    p = sub.add_parser("transliterate", help="Transliterate Unicode text to ASCII")
    p.add_argument("text", nargs="*", help="Input text (or pipe via stdin)")
    p.add_argument("--lang", default=None, help="Language code (e.g. de, ja, zh)")
    p.set_defaults(func=cmd_transliterate)

    # slugify
    p = sub.add_parser("slugify", help="Generate URL-safe slugs")
    p.add_argument("text", nargs="*", help="Input text (or pipe via stdin)")
    p.add_argument("--separator", default=None, help="Separator character (default: -)")
    p.add_argument("--max-length", type=int, default=None, help="Maximum slug length")
    p.set_defaults(func=cmd_slugify)

    # normalize
    p = sub.add_parser("normalize", help="Unicode normalization")
    p.add_argument("text", nargs="*", help="Input text (or pipe via stdin)")
    p.add_argument(
        "--form",
        default="NFC",
        choices=["NFC", "NFD", "NFKC", "NFKD"],
        help="Normalization form (default: NFC)",
    )
    p.set_defaults(func=cmd_normalize)

    # pipeline
    p = sub.add_parser("pipeline", help="Run a TextPipeline with specified steps")
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

    # demojize
    p = sub.add_parser("demojize", help="Expand emoji to text descriptions")
    p.add_argument("text", nargs="*", help="Input text (or pipe via stdin)")
    p.set_defaults(func=cmd_demojize)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
