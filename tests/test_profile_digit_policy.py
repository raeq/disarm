"""``digit_policy`` reaches the profiles, at construction (#646).

Eight profiles shipped and none could express the fold's digit policy, so a caller who
followed the CVE page to ``llm_guardrail`` got the ``numeric`` side of the trade with no
way to ask for the other and no signal that a choice had been made. The policy is fixed
when the profile is built — a profile is a resolved pipeline and calling it takes text
and nothing else — and a pipeline with no confusables step refuses a non-default policy
rather than keeping one that would never run.
"""

import pytest

import disarm

# U+0A66 GURMUKHI ZERO standing in for the letter "o": #646's own demonstration.
SPOOF = "g੦ogle"
FOLDING = ("llm_guardrail", "normalize_web_input", "library_catalog_key_eu")
CORPUS = [SPOOF, "paypal", "٢٠٢٤", "Москва", "SKU-100", "  Héllo  WÖRLD  ", "", "café"]


class TestProfiles:
    @pytest.mark.parametrize("profile", ["llm_guardrail", "normalize_web_input"])
    def test_the_policy_reaches_the_fold(self, profile):
        # The two profiles that fold without transliterating first: the fold sees the
        # Gurmukhi digit, and the policy decides what it becomes.
        assert disarm.get_pipeline(profile)(SPOOF) == "g0ogle"
        assert disarm.get_pipeline(profile, digit_policy="tr39")(SPOOF) == "google"

    @pytest.mark.parametrize("profile", sorted(disarm.list_profiles()))
    def test_the_default_is_byte_identical_spelled_out_or_not(self, profile):
        bare = disarm.get_pipeline(profile)
        spelled = disarm.get_pipeline(profile, digit_policy="numeric")
        for text in CORPUS:
            assert bare(text) == spelled(text)
        assert bare.steps == spelled.steps

    def test_rag_ingest_refuses_a_policy_it_could_never_run(self):
        # Its recovery is transliteration, which runs before the fold (#258).
        with pytest.raises(disarm.InvalidArgumentError, match="tr39") as info:
            disarm.get_pipeline("rag_ingest", digit_policy="tr39")
        # The message shows the steps it does have, so the reader sees why.
        assert "transliterate" in str(info.value)
        # The default is always accepted: spelling it out is not an error.
        disarm.get_pipeline("rag_ingest", digit_policy="numeric")

    @pytest.mark.parametrize("profile", sorted(set(disarm.list_profiles()) - set(FOLDING)))
    def test_every_profile_without_the_step_refuses(self, profile):
        with pytest.raises(disarm.InvalidArgumentError):
            disarm.get_pipeline(profile, digit_policy="tr39")

    @pytest.mark.parametrize("profile", FOLDING)
    def test_every_profile_with_the_step_accepts(self, profile):
        disarm.get_pipeline(profile, digit_policy="tr39")
        disarm.get_pipeline(profile, digit_policy="preserve")

    def test_an_unknown_policy_is_refused_by_name(self):
        with pytest.raises(disarm.InvalidArgumentError, match="digit_policy"):
            disarm.get_pipeline("llm_guardrail", digit_policy="loose")

    def test_the_setting_is_reported_only_when_it_is_not_the_default(self):
        def folds(pipe):
            return [param for step, param in pipe.steps if step == "confusables"]

        # Pre and post pass (#852), both under the one policy.
        assert folds(disarm.get_pipeline("llm_guardrail")) == ["latin", "latin"]
        assert folds(disarm.get_pipeline("llm_guardrail", digit_policy="tr39")) == [
            "latin,tr39",
            "latin,tr39",
        ]


class TestHandBuilt:
    def test_a_transcribed_profile_matches_the_profile_under_the_same_policy(self):
        # #918's rule: a TextPipeline transcribed field for field from a profile must
        # behave like the profile — under a non-default policy too.
        transcribed = disarm.TextPipeline(
            normalize="NFKC",
            resolve_deletions=True,
            strip_zalgo=0,
            strip_bidi=True,
            strip_zero_width=True,
            strip_control=True,
            confusables=True,
            strip_accents=True,
            fold_case=True,
            collapse_whitespace=True,
            strip_pua=True,
            strip_plane14=True,
            digit_policy="tr39",
        )
        profile = disarm.get_pipeline("llm_guardrail", digit_policy="tr39")
        assert transcribed.steps == profile.steps
        for text in CORPUS:
            assert transcribed(text) == profile(text)

    def test_the_keyword_is_refused_without_the_step(self):
        with pytest.raises(disarm.InvalidArgumentError, match="fold_case"):
            disarm.TextPipeline(fold_case=True, digit_policy="tr39")
        disarm.TextPipeline(fold_case=True, digit_policy="numeric")  # the default is fine
        assert disarm.TextPipeline(confusables=True, digit_policy="tr39")(SPOOF) == "google"

    def test_preserve_is_the_third_policy(self):
        # `preserve` (#648) leaves a non-Latin numeral in its own script.
        assert disarm.TextPipeline(confusables=True)("٢٠٢٤") == "٢0٢٤"
        assert disarm.TextPipeline(confusables=True, digit_policy="preserve")("٢٠٢٤") == "٢٠٢٤"
