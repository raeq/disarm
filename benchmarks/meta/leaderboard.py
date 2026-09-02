"""A leaderboard over several benchmarks, weighted by how well each separates.

Nothing here is novel, and that is deliberate. Every step is a named method with
a textbook or paper behind it, so the ranking can be argued about on its
assumptions rather than on whether the arithmetic was invented for the occasion.

**Orientation.** Only measurements with a declared direction take part. A census
(`higher_is_better is None`) counts nothing and is not silently treated as
"more is better" — most of the numbers in this harness are censuses, and folding
them in would be the single easiest way to produce a meaningless ranking.

**Standardisation.** Each benchmark is converted to z-scores across subjects
(Kreyszig; any statistics text). Raw scales differ by orders of magnitude, so an
unstandardised mean is dominated by whichever benchmark has the widest range.

**Discrimination weighting — corrected item-total correlation.** Classical Test
Theory's standard item-discrimination index: the Pearson correlation between an
item's score and the total of *the other* items. Correcting for self-inclusion is
the textbook form (Crocker & Algina, *Introduction to Classical and Modern Test
Theory*, ch. 14; Ebel & Frisbie, *Essentials of Educational Measurement*). A
benchmark on which every tool scores alike correlates with nothing and earns no
weight; one that tracks the overall ordering earns full weight. Negative
correlations are clamped to zero rather than inverted — a benchmark that ranks
tools backwards relative to the rest is a finding to investigate, not a signal
to flip.

**Ranking — Bradley–Terry.** Reported beside the composite, fitted by Hunter's
minorization-maximization algorithm (Hunter, *MM algorithms for generalized
Bradley-Terry models*, Annals of Statistics 32(1), 2004). It is the model behind
Chatbot Arena and behind most paired-comparison leaderboards, and it uses only
the order of each pairwise result, so a single benchmark with an extreme scale
cannot dominate it.

**Battery diagnostics.** Cronbach's alpha (Cronbach, *Psychometrika* 16, 1951)
says whether the benchmarks measure one thing; Kendall's W (Kendall & Babington
Smith, 1939) says how much they agree on the ordering. Both are reported because
a composite over benchmarks that disagree is a weighted average of unrelated
quantities, and a reader is entitled to know that before reading the rank.

**Parcelling.** Measurements are averaged within a suite before ranking, so each
*benchmark* is one item rather than each measurement. Without it, a suite
reporting seven closely related numbers contributes seven near-duplicate items
and takes seven times the weight — `corruption-cost` did exactly that, supplying
seven of the top ten discriminating items at r≈0.945 apiece, and it also inflated
Cronbach's alpha to 0.92 while Kendall's W sat at 0.29. That combination is the
classic signature of redundant items, not of a coherent battery. Item parcelling
is the standard remedy (Little, Cunningham, Shahar & Widaman, *To parcel or not
to parcel*, Structural Equation Modeling 9(2), 2002).

**Controls are placed, not fitted.** The scale is computed from the tools alone
and the controls are then projected onto it. A subject that deletes everything
sits several standard deviations below the field, and letting it into the
standardisation compresses every real tool into a narrow band near the mean —
the ranking would then be driven by distance from a strawman rather than by
differences between tools.

**Uncertainty.** Ranks come with bootstrap intervals over the benchmark set
(Efron 1979). With a handful of subjects and a dozen benchmarks these intervals
are wide, and that is the honest result: it is what stops two adjacent rows being
read as a difference.

**Not attempted: Item Response Theory.** A 2PL model estimates a discrimination
parameter per item directly, and is the method of record for this problem
(Lalor et al., EMNLP 2016; Rodriguez et al., *Evaluation Examples Are Not Equally
Informative*, ACL 2021). It needs far more respondents than the number of tools
here — parameter estimates from single-digit respondents are not stable — so
fitting one would look more rigorous while being less so. Classical item-total
correlation is the small-sample instrument for the same idea.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, field

from .protocol import Outcome, Status

#: Below this, a benchmark is treated as carrying no ranking information.
MIN_DISCRIMINATION = 0.0
#: How many *other* benchmarks must cover a subject before that subject can
#: enter an item's corrected item-total correlation. Guards the rest-score
#: from resting on a single other item.
MIN_REST_ITEMS = 2
#: Conventional floor for acceptable internal consistency (Nunnally,
#: *Psychometric Theory*, 1978). Below it, a composite is an average over
#: quantities the battery itself says are unrelated.
ALPHA_FLOOR = 0.70
#: Fewer parcels than this and the bootstrap has nothing to resample.
MIN_PARCELS = 5
#: A subject scored on less than this fraction of the battery is listed but not
#: ranked against the others. Placing a tool measured on one benchmark above one
#: measured on four compares different things and flatters whichever was asked
#: the fewest questions.
MIN_COVERAGE = 0.75
#: Subjects that are controls are ranked but flagged, never quoted as rivals.
CONTROL_SUBJECTS = ("null-baseline", "identity")


def is_control(subject_key: str) -> bool:
    """``subject_key`` is ``name@version``; controls are matched on the name."""
    return subject_key.split("@", 1)[0] in CONTROL_SUBJECTS


@dataclass
class Item:
    """One benchmark measurement, oriented so that higher is better."""

    suite: str
    key: str
    scores: dict[str, float]  # subject -> oriented raw score
    discrimination: float = 0.0  # corrected item-total correlation
    z: dict[str, float] = field(default_factory=dict)
    #: subject -> the measurement keys it actually contributed to this parcel.
    member_keys: dict[str, set[str]] = field(default_factory=dict)
    #: Every key any subject contributed to this parcel.
    all_keys: set[str] = field(default_factory=set)
    #: subject -> the keys its own cohort answered. See :func:`parcel`.
    peer_keys: dict[str, set[str]] = field(default_factory=dict)

    def complete(self, subject: str) -> bool:
        """Did ``subject`` answer every measurement its peers answered?

        Not every measurement *any* subject answered: a subject with no detector
        cannot earn a detection score, and holding that against it excludes it
        from the benchmark entirely rather than scoring it fairly on the
        measurements it can answer.
        """
        answered = self.member_keys.get(subject, set())
        if not answered:
            return False
        return answered == self.peer_keys.get(subject, self.all_keys)


@dataclass
class Standing:
    subject: str
    composite: float
    bt_strength: float
    rank: int
    ci_low: float
    ci_high: float
    items: int
    control: bool = False
    #: Scored on too little of the battery to sit in the same ordering.
    partial: bool = False


@dataclass
class BenchmarkStanding:
    """One subject's place on one benchmark."""

    subject: str
    rank: int
    z: float
    raw: float
    control: bool = False
    #: Answered only part of this benchmark's measurement set.
    partial: bool = False


@dataclass
class Leaderboard:
    standings: list[Standing] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    alpha: float | None = None
    kendall_w: float | None = None
    correlations: dict[tuple[str, str], float] = field(default_factory=dict)
    subjects: list[str] = field(default_factory=list)
    excluded_census_measurements: int = 0

    @property
    def usable(self) -> bool:
        """Is there enough here to compute anything at all?"""
        return len(self.items) >= 2 and len(self.subjects) >= 2

    @property
    def blockers(self) -> list[str]:
        """Why this battery cannot support a published ranking, if it cannot.

        The interlock is the point. Aggregating anything into one number is easy;
        the reason to use standard methods is that they come with standard tests
        of whether the aggregate means anything, and those tests can fail. When
        they do, the honest output is the per-benchmark table and a statement of
        what is missing — not a ranking with a caveat under it.
        """
        why: list[str] = []
        if len(self.items) < MIN_PARCELS:
            why.append(
                f"only {len(self.items)} benchmarks contribute a directed score "
                f"({MIN_PARCELS} is the floor); a composite over this few is "
                "decided by whichever one moves"
            )
        # Cronbach's alpha is deliberately NOT a blocker. It assumes positively
        # related items, and these axes are opposed by design, so it is the wrong
        # instrument rather than a failed threshold. Rank agreement is the right
        # gate for aggregating orderings, and Friedman tests it without assuming
        # a common construct.
        opposed = [(pair, r) for pair, r in self.correlations.items() if r < -0.5]
        if opposed:
            worst = min(opposed, key=lambda kv: kv[1])
            why.append(
                f"the benchmarks are opposed, not merely unrelated: "
                f"`{worst[0][0]}` and `{worst[0][1]}` correlate at r = {worst[1]:.2f} "
                "across the tools, so no single weighting of them is more correct "
                "than another"
            )
        if self.separated_pairs() == 0 and len(self.standings) > 1:
            sep, total = self.separated_pairs_any()
            why.append(
                "no adjacently ranked pair has non-overlapping bootstrap "
                f"intervals ({sep} of {total} pairs separate anywhere in the "
                "table, none of them neighbours) — "
                "the ordering is not distinguishable from noise"
            )
        return why

    @property
    def supported(self) -> bool:
        return self.usable and not self.blockers

    def per_benchmark(self) -> dict[str, list[BenchmarkStanding]]:
        """A ranking for each benchmark on its own.

        Always publishable, even when the composite is not. The composite needs
        the benchmarks to measure one construct before averaging them; a single
        benchmark measures whatever it measures, so ranking within it carries no
        such assumption. When the battery cannot support a composite — which is
        the current state — these are the rankings that stand.

        Ties share a rank, because two tools that score identically on a
        benchmark are not ordered by it.
        """
        out: dict[str, list[BenchmarkStanding]] = {}
        for item in self.items:
            # A control is a reference line, never a competitor: it is in the
            # roster to prove a metric can reject it, and a metric it *wins* is
            # one that rewards the degenerate answer. Its value stays visible.
            complete = [s for s in item.z if item.complete(s) and not is_control(s)]
            incomplete = [s for s in item.z if not item.complete(s) and not is_control(s)]
            controls = [s for s in item.z if is_control(s)]
            ordered = sorted(complete, key=lambda s: item.z[s], reverse=True)
            standings: list[BenchmarkStanding] = []
            previous: float | None = None
            rank = 0
            for position, subject in enumerate(ordered, start=1):
                score = item.z[subject]
                if previous is None or score != previous:
                    rank = position
                    previous = score
                standings.append(
                    BenchmarkStanding(
                        subject=subject,
                        rank=rank,
                        z=score,
                        raw=item.scores[subject],
                        control=is_control(subject),
                    )
                )
            # Listed after the ordering, never inside it: a subject that answered
            # half a benchmark was asked an easier question, not a better one.
            for subject in sorted(incomplete, key=lambda s: item.z[s], reverse=True):
                standings.append(
                    BenchmarkStanding(
                        subject=subject,
                        rank=0,
                        z=item.z[subject],
                        raw=item.scores[subject],
                        control=False,
                        partial=True,
                    )
                )
            for subject in sorted(controls, key=lambda s: item.z[s], reverse=True):
                standings.append(
                    BenchmarkStanding(
                        subject=subject,
                        rank=0,
                        z=item.z[subject],
                        raw=item.scores[subject],
                        control=True,
                    )
                )
            out[item.suite] = standings
        return out

    def separated_pairs(self) -> int:
        """Adjacent pairs whose 95% intervals do not overlap.

        Adjacency is the right test for whether the *ordering* means anything:
        if no subject separates from the one directly below it, no rank position
        is distinguishable from its neighbour. It is a strictly weaker statement
        than "no two subjects separate" — see :meth:`separated_pairs_any`, which
        counts every pair — and the two must not be conflated in a message.
        """
        ranked = [s for s in self.standings if not s.control]
        return sum(1 for a, b in zip(ranked, ranked[1:], strict=False) if a.ci_low > b.ci_high)

    def separated_pairs_any(self) -> tuple[int, int]:
        """(separated, total) over *every* pair of ranked subjects."""
        ranked = [s for s in self.standings if not s.control and not s.partial]
        sep = total = 0
        for i, a in enumerate(ranked):
            for b in ranked[i + 1 :]:
                total += 1
                if a.ci_low > b.ci_high or b.ci_low > a.ci_high:
                    sep += 1
        return sep, total


def collect(outcomes: Sequence[Outcome], include_controls: bool = True) -> list[Item]:
    """Turn a run into oriented items, dropping everything undirected."""
    by_key: dict[tuple[str, str], dict[str, float]] = {}
    directions: dict[tuple[str, str], bool] = {}
    for out in outcomes:
        if out.status is not Status.OK:
            continue
        # Versioned identity: two builds of one tool are two competitors.
        subject = out.method.subject_key
        if not include_controls and out.method.subject in CONTROL_SUBJECTS:
            continue
        for m in out.measurements:
            if m.higher_is_better is None:
                continue
            value = m.ratio if m.ratio is not None else m.value
            key = (out.suite, m.key)
            by_key.setdefault(key, {})[subject] = value
            directions[key] = m.higher_is_better
    items: list[Item] = []
    for key, scores in by_key.items():
        if len(scores) < 2:
            continue
        higher_better = directions[key]
        oriented = {s: (v if higher_better else -v) for s, v in scores.items()}
        items.append(Item(suite=key[0], key=key[1], scores=oriented))
    return items


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _sd(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    mx, my = _mean(xs), _mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else 0.0


def parcel(items: list[Item]) -> list[Item]:
    """Average measurements within a suite so each benchmark is one item.

    Seven correlated numbers from one suite are seven votes for one benchmark.
    Parcelling makes the unit of analysis the benchmark, which is what the
    leaderboard claims to aggregate over.
    """
    grouped: dict[str, list[Item]] = {}
    for item in items:
        grouped.setdefault(item.suite, []).append(item)
    out: list[Item] = []
    for suite, group in grouped.items():
        subjects = sorted({s for i in group for s in i.scores})
        # A measurement every tool scores identically separates nothing, and
        # averaging it in as a run of zeros dilutes the ones that do. Five of
        # corruption-cost's seven directed measurements were constant across
        # every real tool, so its signal was being divided by seven.
        discriminating = [
            i
            for i in group
            if _sd([i.scores[s] for s in subjects if s in i.scores and not is_control(s)]) > 0
        ]
        group = discriminating or group
        # Average the *standardised* member scores, so measurements on wildly
        # different scales contribute equally inside the parcel.
        standardize(group, subjects, fit_on=subjects)
        merged = {
            s: _mean([i.z[s] for i in group if s in i.z])
            for s in subjects
            if any(s in i.z for i in group)
        }
        # Which measurements each subject actually answered. A parcel averaged
        # over a subset scores a different question: `unidecode` outranked
        # `disarm` on the word-joiner benchmark while recovering 24.3% to its
        # 43.2%, because disarm's average also carried a detection score that
        # `unidecode` has no surface to earn.
        # Completeness is judged against a subject's PEERS, not against every
        # subject that answered anything. `disarm` answers four directed
        # measurements on the TAG-block suite because it has a detector; every
        # transform-only subject answers two. Taking the union as the bar marked
        # all ten of them incomplete and left one tool on three benchmarks, which
        # collapsed the Pareto frontier to nothing and deleted the non-dominated
        # count from the report. Being excluded for lacking a detector is the
        # same error as being scored zero for it, wearing the opposite sign.
        #
        # Peers are subjects answering the same key set. A subject is complete
        # when it answered everything its own cohort answered, so a detector is
        # judged against detectors and a plain transform against transforms.
        cohorts: dict[frozenset[str], set[str]] = {}
        for subj in merged:
            answered = frozenset(i.key for i in group if subj in i.z)
            cohorts.setdefault(answered, set()).add(subj)
        member_keys = {s: {i.key for i in group if s in i.z} for s in merged}
        out.append(
            Item(
                suite=suite,
                key=f"parcel({len(group)} measurement{'' if len(group) == 1 else 's'})",
                scores=merged,
                member_keys=member_keys,
                all_keys={i.key for i in group},
                peer_keys={s: set(k) for k, v in cohorts.items() for s in v},
            )
        )
    return out


def standardize(
    items: list[Item], subjects: Sequence[str], fit_on: Sequence[str] | None = None
) -> None:
    """z-score each benchmark across subjects, in place.

    ``fit_on`` names the subjects the mean and standard deviation are computed
    from; everything in ``subjects`` is then placed on that scale. Controls are
    excluded from the fit so a strawman cannot set the units.

    A benchmark on which every fitted subject scores identically has zero spread
    and contributes zero, which is correct: it separates nothing.
    """
    basis = list(fit_on) if fit_on else [s for s in subjects if not is_control(s)]
    if len(basis) < 2:
        basis = list(subjects)
    for item in items:
        present = [item.scores[s] for s in basis if s in item.scores]
        mu, sigma = _mean(present), _sd(present)
        item.z = {
            s: ((item.scores[s] - mu) / sigma if sigma else 0.0)
            for s in subjects
            if s in item.scores
        }


def discriminations(items: list[Item], subjects: Sequence[str]) -> None:
    """Corrected item-total correlation for every benchmark, in place.

    Missing data is handled by **pairwise** deletion, not listwise. A benchmark
    that only some subjects can answer is normal here — ``flagged_by_a_detector``
    exists only for the subjects in the detector role, so a detector-only suite
    legitimately covers two of eleven subjects. Under listwise deletion that one
    narrow item caps the shared-subject set for *every other* item at two, every
    item then falls below the three-subject floor, and the whole battery reports
    a discrimination of exactly zero — which in turn makes every composite zero.
    The narrowness of one benchmark must not propagate to the rest.

    So the rest-score is the **mean** of whichever other items cover the subject,
    not the sum over all of them: a sum would score a subject answering ten items
    on a different scale from one answering four. An item still needs
    ``MIN_REST_ITEMS`` other items behind each subject for the rest-score to mean
    anything, and three subjects before a correlation is worth computing.
    """
    for item in items:
        others = [o for o in items if o is not item]
        shared = [
            s
            for s in subjects
            if s in item.z and sum(1 for o in others if s in o.z) >= MIN_REST_ITEMS
        ]
        if len(shared) < 3 or not others:
            item.discrimination = 0.0
            continue
        rest_total = [_mean([o.z[s] for o in others if s in o.z]) for s in shared]
        own = [item.z[s] for s in shared]
        item.discrimination = max(MIN_DISCRIMINATION, _pearson(own, rest_total))


def composite(items: list[Item], subject: str) -> float:
    """Discrimination-weighted mean of a subject's z-scores."""
    num = den = 0.0
    for item in items:
        if subject not in item.z:
            continue
        num += item.discrimination * item.z[subject]
        den += item.discrimination
    return num / den if den else 0.0


def bradley_terry(
    items: list[Item], subjects: Sequence[str], iterations: int = 200
) -> dict[str, float]:
    """Fit Bradley-Terry strengths by Hunter's MM algorithm (2004).

    Each benchmark contributes one pairwise result per subject pair: whichever
    scored higher wins. Ties contribute half a win to each, which is the standard
    treatment. Strengths are normalised to sum to one.
    """
    wins: dict[tuple[str, str], float] = {}
    for item in items:
        for a in subjects:
            for b in subjects:
                if a >= b or a not in item.z or b not in item.z:
                    continue
                if item.z[a] > item.z[b]:
                    wins[(a, b)] = wins.get((a, b), 0.0) + 1
                elif item.z[b] > item.z[a]:
                    wins[(b, a)] = wins.get((b, a), 0.0) + 1
                else:
                    wins[(a, b)] = wins.get((a, b), 0.0) + 0.5
                    wins[(b, a)] = wins.get((b, a), 0.0) + 0.5
    p = dict.fromkeys(subjects, 1.0)
    for _ in range(iterations):
        new: dict[str, float] = {}
        for a in subjects:
            num = sum(wins.get((a, b), 0.0) for b in subjects if b != a)
            den = 0.0
            for b in subjects:
                if b == a:
                    continue
                n_ab = wins.get((a, b), 0.0) + wins.get((b, a), 0.0)
                if n_ab:
                    den += n_ab / (p[a] + p[b])
            # A subject that never wins has no finite strength; hold it at a
            # floor rather than letting the iteration send it to zero and
            # produce a division by zero for everyone else.
            new[a] = (num / den) if den and num else 1e-9
        total = sum(new.values()) or 1.0
        p = {k: v / total for k, v in new.items()}
    return p


def axis_correlations(items: list[Item], subjects: Sequence[str]) -> dict[tuple[str, str], float]:
    """Pearson r between every pair of benchmarks, over the tools.

    The diagnostic Cronbach's alpha cannot give here. Alpha collapses the whole
    correlation structure to one number that assumes the items are positively
    related; this shows *which* pairs oppose, which is the actual finding when a
    battery is built from axes that trade against each other.
    """
    tools = [s for s in subjects if not is_control(s)]
    out: dict[tuple[str, str], float] = {}
    for a_idx, a in enumerate(items):
        for b in items[a_idx + 1 :]:
            shared = [s for s in tools if s in a.z and s in b.z]
            if len(shared) < 3:
                continue
            out[(a.suite, b.suite)] = _pearson([a.z[s] for s in shared], [b.z[s] for s in shared])
    return out


def cronbach_alpha(items: list[Item], subjects: Sequence[str]) -> float | None:
    """Internal consistency (Cronbach 1951) — reported, never used as a gate.

    Two reasons it does not apply to this battery, both load-bearing.

    It assumes the items are positively related measures of one construct. These
    axes are opposed by design: corruption-cost against equivalence-class closure
    correlates at r = -0.80. On opposed items a *negative* alpha is the expected
    signature, not a low score, so quoting it against the conventional 0.70 floor
    would imply a standard was missed when the statistic simply does not apply.

    And it must be computed over the tools alone. The two synthetic controls
    score badly on every axis at once, which manufactures positive inter-item
    correlation: alpha reads 0.64 with them and -0.33 without. Including them
    made the battery look coherent purely because a strawman is bad at
    everything.
    """
    k = len(items)
    if k < 2:
        return None
    tools = [s for s in subjects if not is_control(s)]
    shared = [s for s in tools if all(s in i.z for i in items)]
    if len(shared) < 3:
        return None
    item_var = sum(_sd([i.z[s] for s in shared]) ** 2 for i in items)
    totals = [sum(i.z[s] for i in items) for s in shared]
    total_var = _sd(totals) ** 2
    if total_var == 0:
        return None
    return (k / (k - 1)) * (1 - item_var / total_var)


def kendall_w(items: list[Item], subjects: Sequence[str]) -> float | None:
    """Coefficient of concordance: how far the benchmarks agree on the order."""
    shared = [s for s in subjects if all(s in i.z for i in items)]
    n, k = len(shared), len(items)
    if n < 2 or k < 2:
        return None
    rank_sums = dict.fromkeys(shared, 0.0)
    for item in items:
        order = sorted(shared, key=lambda s: item.z[s])
        for rank, s in enumerate(order, start=1):
            rank_sums[s] += rank
    mean_rank = _mean(list(rank_sums.values()))
    ss = sum((r - mean_rank) ** 2 for r in rank_sums.values())
    denominator = k**2 * (n**3 - n) / 12
    return ss / denominator if denominator else None


#: Upper-tail chi-square critical values at alpha = 0.05, by degrees of freedom.
#: Tabulated rather than computed so the module keeps no numerical dependency.
_CHI2_05 = {
    1: 3.84,
    2: 5.99,
    3: 7.81,
    4: 9.49,
    5: 11.07,
    6: 12.59,
    7: 14.07,
    8: 15.51,
    9: 16.92,
    10: 18.31,
    11: 19.68,
    12: 21.03,
    13: 22.36,
    14: 23.68,
    15: 25.00,
    16: 26.30,
    17: 27.59,
    18: 28.87,
    19: 30.14,
    20: 31.41,
}


@dataclass
class Concordance:
    """Friedman's test on the per-benchmark rankings (Friedman, JASA 32, 1937).

    The right diagnostic for a *rank* aggregation, where Cronbach's alpha is the
    right one for a *score* composite. It asks whether the benchmarks order the
    tools more consistently than chance would, and it does not assume they
    measure one construct.
    """

    benchmarks: int
    tools: int
    w: float
    chi_square: float
    df: int
    critical: float | None

    @property
    def significant(self) -> bool:
        return self.critical is not None and self.chi_square > self.critical

    @property
    def benchmarks_needed(self) -> int | None:
        """How many benchmarks this level of agreement would need to be significant.

        The most useful number in the whole module: it turns "not enough
        evidence" into a target. Friedman's chi-square is k(n-1)W, so at fixed
        agreement it grows linearly in the number of benchmarks.
        """
        if self.critical is None or self.w <= 0 or self.tools < 2:
            return None
        need = self.critical / ((self.tools - 1) * self.w)
        return max(self.benchmarks, math.ceil(need))


@dataclass
class Pareto:
    """Non-dominated tools under multi-objective comparison."""

    """Non-dominated tools under multi-objective comparison.

    The answer when the benchmarks genuinely disagree, which they do here: a
    tool that folds aggressively wins coverage and loses cost, and no weighting
    of the two is more correct than another. Dominance needs no weights and no
    common construct — A dominates B when A is at least as good on every axis
    and strictly better on one — so the partial order it yields is a real
    ranking that cannot be argued with on aggregation grounds. Standard in
    multi-objective optimisation.
    """

    axes: list[str] = field(default_factory=list)
    frontier: list[str] = field(default_factory=list)
    dominated: dict[str, list[str]] = field(default_factory=dict)
    scores: dict[str, dict[str, float]] = field(default_factory=dict)

    @property
    def separating(self) -> bool:
        """Does dominance actually distinguish anything?

        With enough axes almost everything is non-dominated, because a tool need
        only lead on one axis to be safe. A frontier holding most of the field is
        a weak result wearing the language of a strong one, and a reader seeing
        their own tool on it should be told how much company it has.
        """
        total = len(self.frontier) + len(self.dominated)
        return bool(total) and len(self.frontier) / total < 0.5


def concordance(board: Leaderboard) -> Concordance | None:
    """Friedman's test over the benchmarks that produced a real ordering."""
    usable = {
        suite: [x for x in standings if not x.control and not x.partial]
        for suite, standings in board.per_benchmark().items()
    }
    usable = {s: v for s, v in usable.items() if len(v) >= 2}
    if not usable:
        return None
    shared = set.intersection(*[{x.subject for x in v} for v in usable.values()])
    tools = sorted(shared)
    k, n = len(usable), len(tools)
    if k < 2 or n < 3:
        return None
    totals = []
    for tool in tools:
        totals.append(sum(next(x.rank for x in v if x.subject == tool) for v in usable.values()))
    mean_total = _mean(totals)
    spread = sum((t - mean_total) ** 2 for t in totals)
    w = 12 * spread / (k**2 * (n**3 - n))
    chi = k * (n - 1) * w
    return Concordance(
        benchmarks=k,
        tools=n,
        w=w,
        chi_square=chi,
        df=n - 1,
        critical=_CHI2_05.get(n - 1),
    )


def pareto(board: Leaderboard) -> Pareto | None:
    """Which tools no other tool beats on every axis at once."""
    usable = {
        suite: [x for x in standings if not x.control and not x.partial]
        for suite, standings in board.per_benchmark().items()
    }
    usable = {s: v for s, v in usable.items() if len(v) >= 2}
    if len(usable) < 2:
        return None
    # Tools are those the battery can actually compare, not the intersection of
    # every benchmark's field. Intersecting listwise let one narrow benchmark —
    # `weaponizing-unicode`, whose only directed measurement needs a detector, so
    # two subjects answer it — empty the frontier and silently delete the
    # non-dominated count from the report. Dominance still needs a common basis,
    # so it is taken pairwise below rather than abandoned.
    tools = sorted({x.subject for v in usable.values() for x in v})
    if len(tools) < 2:
        return None
    axes = list(usable)
    scores = {
        t: {
            s: next((x.z for x in v if x.subject == t), None)  # type: ignore[misc]
            for s, v in usable.items()
        }
        for t in tools
    }

    def beats(a: str, b: str) -> bool:
        # Compare on the axes BOTH answered. A pair sharing too few axes is not
        # comparable, and saying so is better than declaring one non-dominated
        # because the other never met it.
        shared = [s for s in axes if scores[a][s] is not None and scores[b][s] is not None]
        if len(shared) < max(2, len(axes) // 2):
            return False
        return all(scores[a][s] >= scores[b][s] for s in shared) and any(
            scores[a][s] > scores[b][s] for s in shared
        )

    frontier = [t for t in tools if not any(beats(o, t) for o in tools if o != t)]
    dominated = {
        t: [o for o in tools if o != t and beats(o, t)] for t in tools if t not in frontier
    }
    return Pareto(axes=axes, frontier=frontier, dominated=dominated, scores=scores)


def build(
    outcomes: Sequence[Outcome],
    include_controls: bool = True,
    bootstrap: int = 400,
    seed: int = 0,
) -> Leaderboard:
    """Rank the subjects, and say how much the ranking should be trusted."""
    census = sum(
        1
        for o in outcomes
        if o.status is Status.OK
        for m in o.measurements
        if m.higher_is_better is None
    )
    items = parcel(collect(outcomes, include_controls=include_controls))
    subjects = sorted({s for i in items for s in i.scores})
    board = Leaderboard(items=items, subjects=subjects, excluded_census_measurements=census)
    if not board.usable:
        return board

    standardize(items, subjects)
    discriminations(items, subjects)
    strengths = bradley_terry(items, subjects)
    board.alpha = cronbach_alpha(items, subjects)
    board.kendall_w = kendall_w(items, subjects)
    board.correlations = axis_correlations(items, subjects)

    # Bootstrap over the benchmark set: the question is whether the ranking
    # survives a different draw of benchmarks, which is the sampling that
    # actually happened here.
    rng = random.Random(seed)
    draws: dict[str, list[float]] = {s: [] for s in subjects}
    for _ in range(bootstrap):
        sample = [items[rng.randrange(len(items))] for _ in items]
        standardize(sample, subjects)
        discriminations(sample, subjects)
        for s in subjects:
            draws[s].append(composite(sample, s))
    standardize(items, subjects)
    discriminations(items, subjects)

    scored = []
    for s in subjects:
        values = sorted(draws[s])
        lo = values[int(0.025 * len(values))] if values else 0.0
        hi = values[min(len(values) - 1, int(0.975 * len(values)))] if values else 0.0
        scored.append(
            Standing(
                subject=s,
                composite=composite(items, s),
                bt_strength=strengths.get(s, 0.0),
                rank=0,
                ci_low=lo,
                ci_high=hi,
                items=sum(1 for i in items if s in i.z),
                control=is_control(s),
            )
        )
    # Fully-covered subjects rank; partially-covered ones are listed after, out
    # of the ordering, because their composite answers a smaller set of questions.
    total_items = len(items)
    for st in scored:
        st.partial = total_items > 0 and (st.items / total_items) < MIN_COVERAGE
    # Ranked tools first, then partial coverage, then controls. Neither a
    # control nor a partially-measured subject may occupy a rank, because a rank
    # asserts it beat the things below it.
    scored.sort(key=lambda st: (st.control, st.partial, -st.composite))
    # A control sits far outside the fitted distribution by construction, so its
    # composite is an artefact of dividing by the tools' spread. Recorded, never
    # presented as a comparable magnitude.
    position = 0
    for st in scored:
        if st.partial or st.control:
            continue
        position += 1
        st.rank = position
    board.standings = scored
    return board
