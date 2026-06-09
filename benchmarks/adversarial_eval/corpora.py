"""Corpus adapters for the adversarial-text robustness harness (#49).

Each adapter yields :class:`Record` items. A new corpus is a one-class adapter:
set ``name`` / ``labeled`` / ``requires_credentials`` and implement ``load()``.
"""

from __future__ import annotations

import csv
import io
import os
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable
from urllib.request import urlopen

_CACHE = Path(os.environ.get("ADVERSARIAL_EVAL_CACHE", "/tmp/adversarial_eval_cache"))


@dataclass
class Record:
    """One evaluation row.

    ``text`` is the (possibly perturbed) input. ``clean`` is the ground-truth
    de-perturbed text when the corpus provides it (e.g. BitAbuse), else ``None``.
    """

    text: str
    clean: str | None = None


@runtime_checkable
class CorpusAdapter(Protocol):
    name: str
    labeled: bool  # True if records carry ground-truth ``clean`` text
    requires_credentials: bool

    def load(self, limit: int | None = None) -> Iterator[Record]: ...


def _download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        # Explicit timeout so a stalled host can't hang the harness indefinitely
        # (matches scripts/gen_confusables.py).
        with urlopen(url, timeout=30) as resp, open(dest, "wb") as out:  # noqa: S310 (trusted dataset URLs)
            out.write(resp.read())
    return dest


class YouTubeSpamAdapter:
    """YouTube Spam Collection (Alberto et al.) — 5 small CSVs, no credentials.

    Distributed via the UCI archive (dataset 380). Unlabeled for robustness: the
    ``CONTENT`` column is the comment text; there is no clean ground truth, so
    only canonicalization stats + miss-mining are reported.
    """

    name = "youtube-spam"
    labeled = False
    requires_credentials = False
    URL = "https://archive.ics.uci.edu/static/public/380/youtube+spam+collection.zip"

    def load(self, limit: int | None = None) -> Iterator[Record]:
        path = _download(self.URL, _CACHE / "youtube-spam.zip")
        n = 0
        with zipfile.ZipFile(path) as z:
            for member in sorted(z.namelist()):
                if not member.lower().endswith(".csv") or member.startswith("__MACOSX"):
                    continue
                with z.open(member) as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, "utf-8", errors="replace"))
                    for row in reader:
                        content = (row.get("CONTENT") or "").strip()
                        if not content:
                            continue
                        yield Record(text=content)
                        n += 1
                        if limit is not None and n >= limit:
                            return


class BitAbuseAdapter:
    """BitAbuse (HuggingFace ``AutoML/bitabuse``) — perturbed→clean pairs.

    Labeled: ``text`` is the perturbed line, ``label`` is the clean line, so XMR /
    word-level recovery are computed in addition to canonicalization stats.
    """

    name = "bitabuse"
    labeled = True
    requires_credentials = False

    def load(self, limit: int | None = None) -> Iterator[Record]:
        try:
            from datasets import load_dataset
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "BitAbuse needs the 'datasets' package: pip install datasets"
            ) from exc
        os.environ.setdefault("HF_DATASETS_CACHE", str(_CACHE / "hf"))
        ds = load_dataset(
            "AutoML/bitabuse",
            split="train",
            streaming=True,
            cache_dir=str(_CACHE / "hf"),
        )
        for n, row in enumerate(ds):
            if limit is not None and n >= limit:
                return
            yield Record(text=row["text"], clean=row["label"])


class TREC2007Adapter:
    """TREC-2007 public spam corpus (Kaggle) — requires the Kaggle API + creds.

    Unlabeled for robustness (raw spam/ham email bodies). Configure credentials
    as documented in ``scripts/bootstrap_dicts.sh`` before running.
    """

    name = "trec-2007"
    labeled = False
    requires_credentials = True
    DATASET = "imdeepmind/preprocessed-trec-2007-public-corpus-dataset"

    def load(self, limit: int | None = None) -> Iterator[Record]:
        try:
            from kaggle.api.kaggle_api_extended import KaggleApi
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "TREC-2007 needs the Kaggle API: pip install kaggle, and configure "
                "credentials (see scripts/bootstrap_dicts.sh)."
            ) from exc
        api = KaggleApi()
        api.authenticate()
        dest = _CACHE / "trec-2007"
        api.dataset_download_files(self.DATASET, path=str(dest), unzip=True)
        n = 0
        for csv_path in sorted(dest.rglob("*.csv")):
            with open(csv_path, encoding="utf-8", errors="replace", newline="") as f:
                reader = csv.DictReader(f)
                text_col = _guess_text_column(reader.fieldnames or [])
                for row in reader:
                    text = (row.get(text_col) or "").strip()
                    if not text:
                        continue
                    yield Record(text=text)
                    n += 1
                    if limit is not None and n >= limit:
                        return


class MeAJORPhishingAdapter:
    """MeAJOR phishing-email corpus (arXiv:2507.17978).

    The corpus is not fetched programmatically; download it per the paper and
    point ``ADVERSARIAL_EVAL_MEAJOR`` at the extracted CSV/JSONL.
    """

    name = "meajor"
    labeled = False
    requires_credentials = True  # manual data placement

    def load(self, limit: int | None = None) -> Iterator[Record]:
        path = os.environ.get("ADVERSARIAL_EVAL_MEAJOR")
        if not path or not Path(path).exists():
            raise RuntimeError(
                "MeAJOR corpus not found. Download it (arXiv:2507.17978) and set "
                "ADVERSARIAL_EVAL_MEAJOR to the extracted CSV path."
            )
        n = 0
        with open(path, encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            text_col = _guess_text_column(reader.fieldnames or [])
            for row in reader:
                text = (row.get(text_col) or "").strip()
                if not text:
                    continue
                yield Record(text=text)
                n += 1
                if limit is not None and n >= limit:
                    return


def _guess_text_column(fieldnames: list[str]) -> str:
    for candidate in ("text", "body", "content", "email", "message"):
        for name in fieldnames:
            if name.lower() == candidate:
                return name
    return fieldnames[0] if fieldnames else "text"


ADAPTERS: dict[str, CorpusAdapter] = {
    a.name: a()
    for a in (YouTubeSpamAdapter, BitAbuseAdapter, TREC2007Adapter, MeAJORPhishingAdapter)
}
