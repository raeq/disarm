"""Idiomatic Python integration tests for the translit API.

These tests demonstrate (not merely prove) how translit composes with
standard Python patterns: lambdas, generators, list/dict comprehensions,
map/filter/sorted, functools, and itertools. Each test is a self-contained
usage example that a Python developer can read as documentation.
"""

from collections.abc import Iterable, Iterator
from functools import partial, reduce
from typing import Any, Literal, cast

from translit import (
    Slugifier,
    Text,
    TextPipeline,
    UniqueSlugifier,
    detect_scripts,
    fold_case,
    is_ascii,
    is_confusable,
    is_mixed_script,
    is_normalized,
    list_langs,
    normalize,
    sanitize_filename,
    slugify,
    transliterate,
)

# ═══════════════════════════════════════════════════════════════════
# Lambda functions
# ═══════════════════════════════════════════════════════════════════


class TestLambdaComposition:
    """Standalone functions as lambdas and higher-order function arguments."""

    def test_transliterate_as_lambda(self) -> None:
        """Lambda wrapping transliterate with a fixed language."""

        def german(text: str) -> str:
            return transliterate(text, lang="de")

        assert german("München") == "Muenchen"
        assert german("Straße") == "Strasse"

    def test_map_with_transliterate_lambda(self) -> None:
        """map() over a list using a transliterate lambda."""
        cities = ["Москва", "Київ", "Αθήνα", "München"]
        ascii_cities = list(map(lambda c: transliterate(c), cities))
        assert all(is_ascii(c) for c in ascii_cities)

    def test_filter_with_is_ascii_lambda(self) -> None:
        """filter() to separate ASCII from non-ASCII strings."""
        words = ["hello", "café", "world", "naïve", "test"]
        non_ascii = list(filter(lambda w: not is_ascii(w), words))
        assert non_ascii == ["café", "naïve"]

    def test_sorted_by_transliterated_form(self) -> None:
        """Sort Unicode strings by their ASCII transliteration."""
        names = ["Ørsted", "Åland", "Épée", "Ångström"]
        by_ascii = sorted(names, key=lambda n: transliterate(n).lower())
        assert by_ascii[0] == "Åland"  # "aland" sorts first

    def test_reduce_with_text_builder(self) -> None:
        """functools.reduce chaining Text transforms from a list."""
        transforms = [
            lambda t: t.normalize(form="NFC"),
            lambda t: t.strip_accents(),
            lambda t: t.fold_case(),
            lambda t: t.collapse_whitespace(),
        ]
        result = reduce(lambda t, fn: fn(t), transforms, Text("  Héllo  Wörld  "))
        assert result.value == "hello world"

    def test_partial_transliterate(self) -> None:
        """functools.partial to create language-specific transliterators."""
        de_transliterate = partial(transliterate, lang="de")
        no_transliterate = partial(transliterate, lang="no")
        assert de_transliterate("Ärger") == "Aerger"
        assert no_transliterate("Ærlig") == "Aerlig"

    def test_partial_slugify(self) -> None:
        """functools.partial for a project-specific slug convention."""
        project_slug = partial(slugify, separator="_", max_length=30)
        assert project_slug("Hello Beautiful World") == "hello_beautiful_world"

    def test_chained_lambdas_as_pipeline(self) -> None:
        """Compose a pipeline from chained lambdas."""

        def pipeline(text: str) -> str:
            return fold_case(transliterate(normalize(text, form="NFKC")))

        assert pipeline("Héllo") == "hello"
        assert pipeline("Straße") == "strasse"


# ═══════════════════════════════════════════════════════════════════
# Generator functions
# ═══════════════════════════════════════════════════════════════════


class TestGeneratorIntegration:
    """Generators producing and consuming translit transforms lazily."""

    def test_transliterate_generator(self) -> None:
        """Generator that yields transliterated strings lazily."""

        def transliterate_stream(texts: list[str], **kwargs: Any) -> Iterator[str]:
            for text in texts:
                yield transliterate(text, **kwargs)

        cities = ["Москва", "Київ", "Αθήνα"]
        gen = transliterate_stream(cities)

        # Lazy — nothing computed until iterated
        first = next(gen)
        assert first == "Moskva"
        rest = list(gen)
        assert len(rest) == 2

    def test_script_detector_generator(self) -> None:
        """Generator yielding (text, scripts) tuples for analysis."""

        def annotate_scripts(texts: list[str]) -> Iterator[tuple[str, list[str]]]:
            for text in texts:
                scripts = detect_scripts(text)
                yield text, [s.name for s in scripts]

        samples = ["hello", "Москва", "hello мир"]
        annotations = list(annotate_scripts(samples))
        assert annotations[0] == ("hello", ["LATIN"])
        assert annotations[1] == ("Москва", ["CYRILLIC"])
        assert annotations[2][1] == ["LATIN", "CYRILLIC"]

    def test_mixed_script_filter_generator(self) -> None:
        """Generator that filters for mixed-script strings (homoglyph attack detection)."""

        def find_suspicious(texts: list[str]) -> Iterator[str]:
            for text in texts:
                if is_mixed_script(text):
                    yield text

        inputs = ["hello", "hеllo", "world", "wоrld"]  # 2nd and 4th have Cyrillic
        suspicious = list(find_suspicious(inputs))
        assert len(suspicious) == 2

    def test_lazy_text_processing_chain(self) -> None:
        """Chain generators for a lazy ETL pipeline."""

        def normalize_stream(texts: Iterable[str]) -> Iterator[str]:
            for t in texts:
                yield normalize(t, form="NFC")

        def transliterate_stream(texts: Iterable[str]) -> Iterator[str]:
            for t in texts:
                yield transliterate(t)

        def lowercase_stream(texts: Iterable[str]) -> Iterator[str]:
            for t in texts:
                yield fold_case(t)

        raw = ["Café", "Naïve", "Résumé"]
        pipeline = lowercase_stream(transliterate_stream(normalize_stream(raw)))
        results = list(pipeline)
        assert results == ["cafe", "naive", "resume"]

    def test_generator_expression_with_text_builder(self) -> None:
        """Generator expression using Text builder — lazy and composable."""
        names = ["München", "São Paulo", "Łódź", "Москва"]
        slugs = (Text(n).transliterate().slugify().value for n in names)

        # Consume one at a time
        assert next(slugs) == "munchen"
        assert next(slugs) == "sao-paulo"

    def test_yield_from_with_language_groups(self) -> None:
        """yield from to flatten language-grouped transliterations."""

        def transliterate_by_lang(groups: dict[str, list[str]]) -> Iterator[str]:
            for lang, texts in groups.items():
                yield from (transliterate(t, lang=lang) for t in texts)

        groups = {
            "de": ["München", "Ärger"],
            "no": ["Ørsted", "Åland"],
        }
        results = list(transliterate_by_lang(groups))
        assert results == ["Muenchen", "Aerger", "Oersted", "Aaland"]


# ═══════════════════════════════════════════════════════════════════
# List comprehensions
# ═══════════════════════════════════════════════════════════════════


class TestListComprehensions:
    """List comprehensions with transforms, predicates, and filters."""

    def test_transliterate_list(self) -> None:
        """Simple list comprehension over transliterate."""
        words = ["café", "naïve", "résumé", "Łódź"]
        ascii_words = [transliterate(w) for w in words]
        assert ascii_words == ["cafe", "naive", "resume", "Lodz"]

    def test_slugify_list(self) -> None:
        """Generate slugs for a list of article titles."""
        titles = ["Hello World", "Café Culture", "Naïve Approach"]
        slugs = [slugify(t) for t in titles]
        assert slugs == ["hello-world", "cafe-culture", "naive-approach"]

    def test_filtered_comprehension_non_ascii(self) -> None:
        """Comprehension with filter: transliterate only non-ASCII strings."""
        words = ["hello", "café", "world", "naïve"]
        cleaned = [transliterate(w) if not is_ascii(w) else w for w in words]
        assert cleaned == ["hello", "cafe", "world", "naive"]

    def test_text_builder_comprehension(self) -> None:
        """Text builder inside a list comprehension."""
        inputs = ["  Héllo  ", "  Wörld  "]
        results = [Text(s).strip_accents().collapse_whitespace().value for s in inputs]
        assert results == ["Hello", "World"]

    def test_detect_scripts_comprehension(self) -> None:
        """Extract script names for each string."""
        texts = ["hello", "Москва", "日本語"]
        script_names = [[s.name for s in detect_scripts(t)] for t in texts]
        assert script_names == [["LATIN"], ["CYRILLIC"], ["HAN"]]

    def test_nested_comprehension_lang_matrix(self) -> None:
        """Nested comprehension: transliterate one word across multiple languages."""
        word = "Ärger"
        langs = ["de", "sv", "fi"]
        results = [(lang, transliterate(word, lang=lang)) for lang in langs]
        assert ("de", "Aerger") in results
        assert ("sv", "Aerger") in results

    def test_enumerate_with_transliterate(self) -> None:
        """enumerate() inside comprehension for indexed processing."""
        words = ["café", "naïve", "résumé"]
        indexed = [(i, transliterate(w)) for i, w in enumerate(words)]
        assert indexed == [(0, "cafe"), (1, "naive"), (2, "resume")]

    def test_zip_original_and_transliterated(self) -> None:
        """zip() original and transliterated forms."""
        originals = ["München", "Москва", "Αθήνα"]
        pairs = list(zip(originals, [transliterate(o) for o in originals], strict=True))
        assert pairs[0] == ("München", "Munchen")
        assert pairs[1] == ("Москва", "Moskva")

    def test_sanitize_filenames_comprehension(self) -> None:
        """Sanitize a batch of filenames."""
        raw_names = ["my file (1).txt", "hello/world.pdf", "résumé.docx"]
        safe = [sanitize_filename(n) for n in raw_names]
        assert all("/" not in s for s in safe)


# ═══════════════════════════════════════════════════════════════════
# Dict comprehensions
# ═══════════════════════════════════════════════════════════════════


class TestDictComprehensions:
    """Dict comprehensions building lookup tables and mappings."""

    def test_transliteration_lookup(self) -> None:
        """Build a Unicode→ASCII lookup dict."""
        words = ["café", "naïve", "Москва", "Łódź"]
        lookup = {w: transliterate(w) for w in words}
        assert lookup["café"] == "cafe"
        assert lookup["Москва"] == "Moskva"

    def test_slug_mapping(self) -> None:
        """Map titles to their slugs."""
        titles = ["Hello World", "Café Culture", "Naïve Art"]
        slug_map = {t: slugify(t) for t in titles}
        assert slug_map["Café Culture"] == "cafe-culture"

    def test_script_classification(self) -> None:
        """Classify strings by their detected script."""
        texts = ["hello", "Москва", "日本語", "Αθήνα"]
        by_script = {t: detect_scripts(t)[0].name for t in texts}
        assert by_script == {
            "hello": "LATIN",
            "Москва": "CYRILLIC",
            "日本語": "HAN",
            "Αθήνα": "GREEK",
        }

    def test_ascii_partition(self) -> None:
        """Partition words into ASCII and non-ASCII dicts."""
        words = ["hello", "café", "world", "naïve", "Москва"]
        partition = {
            "ascii": [w for w in words if is_ascii(w)],
            "unicode": [w for w in words if not is_ascii(w)],
        }
        assert partition["ascii"] == ["hello", "world"]
        assert len(partition["unicode"]) == 3

    def test_lang_transliteration_matrix(self) -> None:
        """Dict of dicts: multiple languages × multiple words."""
        words = ["Ärger", "Ørsted"]
        langs = ["de", "no", "sv"]
        matrix = {lang: {w: transliterate(w, lang=lang) for w in words} for lang in langs}
        assert matrix["de"]["Ärger"] == "Aerger"
        assert matrix["no"]["Ørsted"] == "Oersted"

    def test_filename_sanitization_map(self) -> None:
        """Map raw filenames to sanitized versions."""
        files = {"report (final).docx": None, "données/2024.csv": None}
        safe = {raw: sanitize_filename(raw) for raw in files}
        assert all("/" not in v for v in safe.values())

    def test_confusable_detection_dict(self) -> None:
        """Build a dict flagging confusable strings."""
        texts = ["hello", "hеllo", "world", "wоrld"]  # Cyrillic in 2nd, 4th
        flags = {t: is_confusable(t) for t in texts}
        assert flags["hello"] is False
        assert flags["hеllo"] is True

    def test_normalization_forms_dict(self) -> None:
        """Check a string against all normalization forms."""
        text = "café"
        forms = {
            f: is_normalized(text, form=cast(Literal["NFC", "NFD", "NFKC", "NFKD"], f))
            for f in ("NFC", "NFD", "NFKC", "NFKD")
        }
        # NFC-composed "café" is NFC and NFKC normalized
        assert forms["NFC"] is True
        assert forms["NFD"] is False


# ═══════════════════════════════════════════════════════════════════
# Stateful objects with Python idioms
# ═══════════════════════════════════════════════════════════════════


class TestStatefulObjectIdioms:
    """Slugifier, UniqueSlugifier, and TextPipeline as callables in
    Python higher-order patterns."""

    def test_slugifier_as_map_callable(self) -> None:
        """Slugifier instance used directly in map()."""
        slug = Slugifier(separator="_")
        titles = ["Hello World", "Café Culture"]
        slugs = list(map(slug, titles))
        assert slugs == ["hello_world", "cafe_culture"]

    def test_unique_slugifier_deduplication(self) -> None:
        """UniqueSlugifier in a list comprehension — auto-deduplicates."""
        unique = UniqueSlugifier()
        titles = ["Hello", "Hello", "Hello"]
        slugs = [unique(t) for t in titles]
        assert slugs[0] == "hello"
        assert slugs[1] == "hello-1"
        assert slugs[2] == "hello-2"

    def test_text_pipeline_in_map(self) -> None:
        """TextPipeline as a callable in map()."""
        pipe = TextPipeline(transliterate=True, fold_case=True)
        words = ["Café", "Naïve", "Straße"]
        results = list(map(pipe, words))
        assert results == ["cafe", "naive", "strasse"]

    def test_text_pipeline_in_comprehension(self) -> None:
        """TextPipeline in a list comprehension with filter."""
        pipe = TextPipeline(transliterate=True, fold_case=True, collapse_whitespace=True)
        texts = ["  Héllo  ", "  ", "  Wörld  "]
        cleaned = [pipe(t) for t in texts if t.strip()]
        assert cleaned == ["hello", "world"]

    def test_text_builder_in_sorted_key(self) -> None:
        """Text builder as a sort key."""
        names = ["Ørsted", "Åland", "Épée", "Ångström"]
        by_ascii = sorted(names, key=lambda n: Text(n).transliterate().fold_case().value)
        assert by_ascii[0] == "Åland"


# ═══════════════════════════════════════════════════════════════════
# Language profile idioms
# ═══════════════════════════════════════════════════════════════════


class TestLanguageProfileIdioms:
    """list_langs() and language iteration patterns."""

    def test_list_langs_as_set(self) -> None:
        """Convert to set for O(1) membership tests."""
        supported = set(list_langs())
        assert "de" in supported
        assert "xx" not in supported

    def test_lang_comprehension_filter(self) -> None:
        """Filter supported languages by prefix."""
        european = [
            lang
            for lang in list_langs()
            if lang
            in {
                "de",
                "fr",
                "es",
                "it",
                "pt",
                "nl",
                "sv",
                "no",
                "da",
                "fi",
                "pl",
                "cs",
                "sk",
                "hu",
                "ro",
                "bg",
                "hr",
                "sl",
                "sr",
                "uk",
            }
        ]
        assert "de" in european
        assert len(european) > 10

    def test_transliterate_all_langs_dict(self) -> None:
        """Transliterate one word in every supported language — dict comprehension."""
        word = "café"
        results = {lang: transliterate(word, lang=lang) for lang in list_langs()}
        # Every language should produce ASCII for "café"
        assert all(is_ascii(v) for v in results.values())


# ═══════════════════════════════════════════════════════════════════
# Text builder + comprehension integration
# ═══════════════════════════════════════════════════════════════════


class TestTextBuilderIdioms:
    """Text builder in idiomatic Python patterns."""

    def test_text_in_map(self) -> None:
        """map() with Text builder pipeline."""
        words = ["Héllo", "Wörld", "Café"]
        results = list(
            map(
                lambda w: Text(w).transliterate().fold_case().value,
                words,
            )
        )
        assert results == ["hello", "world", "cafe"]

    def test_text_in_filter(self) -> None:
        """filter() using Text predicates."""
        words = ["hello", "café", "world"]
        unicode_words = list(filter(lambda w: not Text(w).is_ascii(), words))
        assert unicode_words == ["café"]

    def test_text_in_dict_comprehension(self) -> None:
        """Dict mapping original → multiple derived forms via Text builder."""
        words = ["Héllo", "Straße"]
        forms = {
            w: {
                "ascii": Text(w).transliterate().value,
                "lower": Text(w).fold_case().value,
                "slug": Text(w).transliterate().slugify().value,
            }
            for w in words
        }
        assert forms["Héllo"]["ascii"] == "Hello"
        assert forms["Straße"]["lower"] == "strasse"
        assert forms["Héllo"]["slug"] == "hello"

    def test_text_equality_in_any_all(self) -> None:
        """any() and all() with Text comparisons."""
        words = ["café", "naïve", "résumé"]
        assert all(Text(w).transliterate().is_ascii() for w in words)
        assert any(Text(w) == "café" for w in words)
        assert not any(Text(w).transliterate() == "unchanged" for w in words)


# ═══════════════════════════════════════════════════════════════════
# Iterable parameter acceptance
# ═══════════════════════════════════════════════════════════════════


class TestIterableParams:
    """Verify that stopwords/replacements accept any Iterable, not just
    tuple/list.  Regression tests for type stub divergence fix."""

    def test_slugify_stopwords_set(self) -> None:
        assert slugify("hello the world", stopwords={"the"}) == "hello-world"

    def test_slugify_stopwords_frozenset(self) -> None:
        assert slugify("hello the world", stopwords=frozenset(["the"])) == "hello-world"

    def test_slugify_stopwords_generator(self) -> None:
        gen = (w for w in ["the"])
        assert slugify("hello the world", stopwords=gen) == "hello-world"

    def test_slugify_replacements_generator(self) -> None:
        gen = ((k, v) for k, v in [("hello", "hi")])
        assert slugify("hello world", replacements=gen) == "hi-world"

    def test_slugifier_stopwords_set(self) -> None:
        s = Slugifier(stopwords={"the", "a"})
        assert s("hello the world") == "hello-world"

    def test_unique_slugifier_stopwords_frozenset(self) -> None:
        u = UniqueSlugifier(stopwords=frozenset(["the"]))
        assert u("hello the world") == "hello-world"

    def test_text_slugify_stopwords_set(self) -> None:
        result = Text("hello the world").slugify(stopwords={"the"}).value
        assert result == "hello-world"

    def test_text_slugify_replacements_generator(self) -> None:
        gen = ((k, v) for k, v in [("hello", "hi")])
        result = Text("hello world").slugify(replacements=gen).value
        assert result == "hi-world"
