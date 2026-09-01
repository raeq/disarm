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

    def complete(self, subject: str) -> bool:
        """Did ``subject`` answer every measurement this benchmark reports?"""
        return self.member_keys.get(subject, set()) == self.all_keys


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
        if self.alpha is not None and self.alpha < ALPHA_FLOOR:
            why.append(
                f"Cronbach's alpha is {self.alpha:.2f}, below the conventional "
                f"{ALPHA_FLOOR:.2f} floor — the benchmarks do not measure one "
                "construct, so a weighted average of them is not a quantity"
            )
        if self.alpha is None:
            why.append("internal consistency could not be estimated")
        if self.separated_pairs() == 0 and len(self.standings) > 1:
            why.append(
                "no two subjects have non-overlapping bootstrap intervals — "
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
            complete = [s for s in item.z if item.complete(s)]
            incomplete = [s for s in item.z if not item.complete(s)]
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
                        control=is_control(subject),
                        partial=True,
                    )
                )
            out[item.suite] = standings
        return out

    def separated_pairs(self) -> int:
        """Adjacent pairs whose 95% intervals do not overlap."""
        ranked = [s for s in self.standings if not s.control]
        return sum(1 for a, b in zip(ranked, ranked[1:], strict=False) if a.ci_low > b.ci_high)


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
        out.append(
            Item(
                suite=suite,
                key=f"parcel({len(group)} measurement{'' if len(group) == 1 else 's'})",
                scores=merged,
                member_keys={s: {i.key for i in group if s in i.z} for s in merged},
                all_keys={i.key for i in group},
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
    """Corrected item-total correlation for every benchmark, in place."""
    for item in items:
        others = [o for o in items if o is not item]
        shared = [s for s in subjects if s in item.z and all(s in o.z for o in others)]
        if len(shared) < 3 or not others:
            item.discrimination = 0.0
            continue
        rest_total = [sum(o.z[s] for o in others) for s in shared]
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


def cronbach_alpha(items: list[Item], subjects: Sequence[str]) -> float | None:
    """Internal consistency of the battery (Cronbach 1951)."""
    k = len(items)
    if k < 2:
        return None
    shared = [s for s in subjects if all(s in i.z for i in items)]
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
    scored.sort(key=lambda st: (st.partial, -st.composite))
    # A control sits far outside the fitted distribution by construction, so its
    # composite is an artefact of dividing by the tools' spread. Recorded, never
    # presented as a comparable magnitude.
    position = 0
    for st in scored:
        if st.partial:
            continue
        position += 1
        st.rank = position
    board.standings = scored
    return board
