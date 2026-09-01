"""Suites anchored to a released model artifact.

The chat-template delimiter set is not something disarm may invent: a delimiter
is whatever a published ``tokenizer.json`` / ``chat_template`` actually declares
as a special token. The suite reads those files and derives the delimiter list
from them, so the benchmark moves when the model families move and not when
disarm does.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..base import CACHE, SuiteBase, add, artifact, record
from ..protocol import Availability, Family, Outcome, Provenance


class ChatTemplateDelimiters(SuiteBase):
    name = "chat-template-delimiters"
    family = Family.MODEL_ARTIFACT
    availability = Availability.MANUAL
    MULTI_SUBJECT = True
    env_var = "DISARM_META_TOKENIZERS"
    summary = "Do released special tokens survive a preset, and does NFKC manufacture them?"
    provenance = Provenance(
        origin="Model publishers (Qwen, Meta, Microsoft, DeepSeek, Google, Mistral)",
        citation="released tokenizer.json / tokenizer_config.json added_tokens",
        url="https://huggingface.co/",
        version="whatever the operator placed",
        licence="per model licence",
        issues=(742, 743, 747, 748),
        finding=(
            "#742: 11 of 26 delimiters survived every preset — Gemma 2/3 5/5 and "
            "Llama 2/Mistral 6/6, while Qwen/ChatML, Llama 3.x, Phi-3 and DeepSeek "
            "were broken only by the accidental TR39 U+007C -> l fold. #747: "
            "canonicalize MANUFACTURED all 11 survivors from fullwidth input."
        ),
        notes=(
            "Two directions, one answer, which is why they are one suite. Forward: a "
            "delimiter spelled as text re-parses as a real special token unless "
            "something breaks it. Reverse: NFKC produces the same delimiter from "
            "inert fullwidth input, so screening before disarm hands the live "
            "delimiter back out of it. Point the env var at a directory of "
            "tokenizer.json files, one per model."
        ),
    )

    #: Fullwidth spellings are generated from the delimiter, never hand-listed:
    #: every ASCII character in a delimiter maps to its fullwidth form where one
    #: exists, so the reverse probe stays derived from the external token.
    @staticmethod
    def _fullwidth(text: str) -> str:
        out = []
        for ch in text:
            cp = ord(ch)
            if 0x21 <= cp <= 0x7E:
                out.append(chr(cp - 0x21 + 0xFF01))
            else:
                out.append(ch)
        return "".join(out)

    def locate(self) -> Path | None:
        return artifact(CACHE / "tokenizers", env=self.env_var)

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        root = self.locate()
        assert root is not None
        delimiters: dict[str, str] = {}  # delimiter -> model file it came from
        for path in sorted(Path(root).rglob("*.json")):
            try:
                blob = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except (ValueError, OSError):
                continue
            for token in _special_tokens(blob):
                delimiters.setdefault(token, path.stem)
        tokens = sorted(delimiters)
        if limit is not None:
            tokens = tokens[:limit]
        outcome.population = len(tokens)
        if not tokens:
            add(outcome, "delimiters", 0)
            return

        surface_map = self.transforms()
        record(
            outcome,
            domain=f"{len(tokens)} declared special tokens",
            predicates=sorted(surface_map),
            forward="is the delimiter still a substring of the output",
            reverse="does the fullwidth spelling produce the live delimiter",
        )
        survives_all = 0
        manufactured_by_any_surface = 0
        per_surface_survive = {name: 0 for name in surface_map}
        per_surface_manufacture = {name: 0 for name in surface_map}

        for token in tokens:
            wide = self._fullwidth(token)
            survived_here = 0
            manufactured_here = False
            for name, fn in surface_map.items():
                try:
                    forward = fn(token)
                    reverse = fn(wide)
                except Exception:  # noqa: BLE001
                    continue
                if token in forward:
                    per_surface_survive[name] += 1
                    survived_here += 1
                if token in reverse:
                    per_surface_manufacture[name] += 1
                    manufactured_here = True
            if survived_here == len(surface_map):
                survives_all += 1
            if manufactured_here:
                manufactured_by_any_surface += 1

        n = len(tokens)
        add(outcome, "delimiters", n, unit="tokens")
        add(
            outcome,
            "survive_every_surface",
            survives_all,
            of=n,
            higher_is_better=False,
            detail="the delimiter passes through all 19 surfaces intact",
        )
        add(
            outcome,
            "manufactured_from_fullwidth",
            manufactured_by_any_surface,
            of=n,
            higher_is_better=False,
            detail="at least one surface PRODUCES the live delimiter from inert input",
        )
        add(
            outcome,
            "manufactured_by_worst_surface",
            max(per_surface_manufacture.values()),
            of=n,
            higher_is_better=False,
            detail="the single surface that manufactures the most delimiters",
        )
        outcome.extra = {
            "survive_by_surface": per_surface_survive,
            "manufacture_by_surface": per_surface_manufacture,
            "sources": {t: delimiters[t] for t in tokens},
        }


def _special_tokens(blob: object) -> list[str]:
    """Pull declared special tokens out of a tokenizer JSON of either shape."""
    found: list[str] = []
    if isinstance(blob, dict):
        for key in ("added_tokens", "added_tokens_decoder"):
            entries = blob.get(key)
            if isinstance(entries, list):
                for e in entries:
                    if (
                        isinstance(e, dict)
                        and e.get("special")
                        and isinstance(e.get("content"), str)
                    ):
                        found.append(e["content"])
            elif isinstance(entries, dict):
                for e in entries.values():
                    if (
                        isinstance(e, dict)
                        and e.get("special")
                        and isinstance(e.get("content"), str)
                    ):
                        found.append(e["content"])
        for key in ("bos_token", "eos_token", "unk_token", "pad_token"):
            val = blob.get(key)
            if isinstance(val, str):
                found.append(val)
            elif isinstance(val, dict) and isinstance(val.get("content"), str):
                found.append(val["content"])
    return [t for t in found if t]


SUITES = [ChatTemplateDelimiters()]
