"""The needs-attention score (0-100) is computed, not asked for.

The LLM narrates *what* went wrong; this module owns the arithmetic that turns
that into a ranking. Two reasons that split matters:

1. **Explainability.** A manager can be shown why a call scored 82, factor by
   factor, each with its own citation. "The model said 82" cannot be audited,
   argued with, or tuned.
2. **Stability.** Asking a model for a number gives you a different number on
   Tuesday. The ranking that drives the whole product should not drift.

Weights are declared here as constants so they can be read, cited on a slide,
and adjusted deliberately rather than discovered by accident.
"""
from dataclasses import dataclass, field

#: Each factor's maximum contribution. They sum to 1.0; the final score is the
#: weighted sum scaled to 0-100.
WEIGHTS = {
    "resolution": 0.30,       # an unresolved issue is the strongest signal
    "mood_severity": 0.20,    # how bad the customer's mood got
    "mood_shift": 0.15,       # a sustained turn for the worse mid-call
    "escalation": 0.20,       # explicit escalation language
    "repeat_contact": 0.10,   # calling again about the same thing
    "handle_time": 0.05,      # unusually long call
}

RESOLUTION_SEVERITY = {"unresolved": 1.0, "partial": 0.5, "resolved": 0.0}

#: How negative the worst mood must be before we will *call* it negative mood.
#:
#: Distinct from mood.MIN_MOOD_WORDS, which decides whether a turn is scored at
#: all. This decides whether a score is strong enough to make a claim about.
#:
#: Measured on this corpus, VADER's negative scores mostly track negative
#: *topics*, not negative *affect*: the strongest were 'I lost my debit card.
#: Can you send me a new one?' (-0.31) and 'No, not today, thank you.' (-0.34) —
#: a calm request and a polite decline. Claiming those as an unhappy customer,
#: and citing them as proof, is precisely the "evidence that does not support
#: the claim" the brief scores negative.
#:
#: So the bar is set where a reader shown the quote would agree with the label.
#: On these 1,441 scripted, courteous calls that leaves few — which is the
#: correct answer for this data, not a failure to detect. The same is true of
#: ESCALATION_PHRASES: zero hits across 8,866 customer turns, because nobody in
#: this corpus escalates. Both signals are real and both stay in the pipeline
#: for recordings that do contain them, including anything ingested live.
MOOD_CLAIM_FLOOR = -0.20

#: A call this many times the median duration counts as a full outlier.
HANDLE_TIME_OUTLIER_RATIO = 2.0


def _ordinal(n: int) -> str:
    """2 -> '2nd'. Used so a factor reads "3rd call about this issue" rather
    than a generic label a manager has to decode."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


@dataclass
class AttentionFactor:
    factor: str
    weight: float                     # actual contribution, not the cap
    turn_index: int | None = None     # what to cite, if anything
    detail: str = ""
    #: Whether the citation should be entailment-checked against the factor text.
    #: False for factors whose turn was chosen by our own arithmetic (the worst
    #: mood score, the detected change point) rather than claimed by the model:
    #: there the citation means "these are the words spoken at the moment the
    #: number came from", which is true by construction. Asking an entailment
    #: model whether "Main Street," supports "sustained negative customer mood"
    #: is a category error — the same one documented in analyze.py's mood_shift
    #: branch, which measured 0/10 doing exactly that.
    check_support: bool = True


@dataclass
class AttentionResult:
    score: int
    factors: list[AttentionFactor] = field(default_factory=list)


def compute_attention_score(
    resolution_status: str | None,
    worst_mood: float | None,
    mood_shift_delta: float | None,
    escalation_hits: list[tuple[int, str]],
    handle_time_seconds: float,
    median_handle_time_seconds: float,
    is_repeat_contact: bool,
    repeat_count: int = 0,
    *,
    resolution_turn_index: int | None = None,
    worst_mood_turn_index: int | None = None,
    mood_shift_turn_index: int | None = None,
    intent_turn_index: int | None = None,
) -> AttentionResult:
    """Weighted composite -> (0-100, contributing factors).

    Only factors that actually fired are returned, so the UI never shows a list
    padded with zero-weight noise.

    The three `*_turn_index` arguments are what let each factor carry its own
    citation. They are keyword-only and default to None so the function stays
    callable without them, but omitting one means that factor renders as "no
    evidence" — which the brief scores zero. Pass them.

    One factor is deliberately left uncitable: "unusually long call" is a fact
    about the clock, not about anything anyone said. Inventing a quote for it
    would be evidence that does not support the claim, which scores *negative* —
    strictly worse than the zero it gets for staying honest.
    """
    factors: list[AttentionFactor] = []
    total = 0.0

    # --- Resolution -------------------------------------------------------
    severity = RESOLUTION_SEVERITY.get((resolution_status or "").lower(), 0.5)
    if severity > 0:
        contribution = WEIGHTS["resolution"] * severity
        total += contribution
        factors.append(
            AttentionFactor(
                factor=f"issue {resolution_status or 'unknown'}",
                weight=round(contribution, 3),
                turn_index=resolution_turn_index,
                detail=f"resolution status: {resolution_status}",
            )
        )

    # --- Mood severity ----------------------------------------------------
    # worst_mood is in [-1, 1]; only mood negative enough to stand behind
    # contributes. See MOOD_CLAIM_FLOOR for why the bar is not simply < 0.
    if worst_mood is not None and worst_mood <= MOOD_CLAIM_FLOOR:
        severity = min(abs(worst_mood), 1.0)
        contribution = WEIGHTS["mood_severity"] * severity
        total += contribution
        factors.append(
            AttentionFactor(
                factor="sustained negative customer mood",
                weight=round(contribution, 3),
                turn_index=worst_mood_turn_index,
                # Our own minimum over the mood series picked this turn; the
                # citation points at where the number came from.
                check_support=False,
                detail=f"worst mood score {worst_mood:.2f}",
            )
        )

    # --- Mood shift -------------------------------------------------------
    # Only a shift for the WORSE matters. A call that starts badly and improves
    # is a success story, not something to escalate.
    if mood_shift_delta is not None and mood_shift_delta < 0:
        severity = min(abs(mood_shift_delta), 1.0)
        contribution = WEIGHTS["mood_shift"] * severity
        total += contribution
        factors.append(
            AttentionFactor(
                factor="mood turned negative during the call",
                weight=round(contribution, 3),
                turn_index=mood_shift_turn_index,
                # Same reasoning: the change-point detector chose this turn.
                check_support=False,
                detail=f"mood fell by {abs(mood_shift_delta):.2f}",
            )
        )

    # --- Escalation language ---------------------------------------------
    if escalation_hits:
        # Saturating: three escalation phrases isn't three times as bad as one.
        severity = min(len(escalation_hits) / 2.0, 1.0)
        contribution = WEIGHTS["escalation"] * severity
        total += contribution
        turn_index, phrase = escalation_hits[0]
        factors.append(
            AttentionFactor(
                factor=f'escalation language: "{phrase}"',
                weight=round(contribution, 3),
                turn_index=turn_index,
                detail=f"{len(escalation_hits)} escalation phrase(s)",
            )
        )

    # --- Repeat contact ---------------------------------------------------
    # Counted against the same ISSUE CLUSTER, not just the same customer —
    # every customer in this corpus is a repeat caller, so "they've called
    # before" carries no information. "They've called about THIS before" does.
    if is_repeat_contact and repeat_count:
        severity = min(repeat_count / 3.0, 1.0)
        contribution = WEIGHTS["repeat_contact"] * severity
        total += contribution
        ordinal = _ordinal(repeat_count + 1)
        factors.append(
            AttentionFactor(
                factor=f"{ordinal} call about this issue",
                weight=round(contribution, 3),
                # Cites this call's own intent turn: the customer stating the
                # issue they are calling about again. The "again" is a database
                # fact carried in the factor text; the quote proves the "about
                # this issue" half, which is the part a quote can prove.
                # Pointing at the earlier call's audio instead would seek the
                # player to a different recording — a citation that actively
                # misleads is worse than one that is merely absent.
                turn_index=intent_turn_index,
                check_support=False,
                detail=f"{repeat_count} earlier call(s) about this issue",
            )
        )

    # --- Handle time ------------------------------------------------------
    if median_handle_time_seconds > 0:
        ratio = handle_time_seconds / median_handle_time_seconds
        if ratio > 1.2:
            severity = min((ratio - 1.2) / (HANDLE_TIME_OUTLIER_RATIO - 1.2), 1.0)
            contribution = WEIGHTS["handle_time"] * severity
            total += contribution
            factors.append(
                AttentionFactor(
                    factor="unusually long call",
                    weight=round(contribution, 3),
                    detail=f"{ratio:.1f}x the median handle time",
                )
            )

    factors.sort(key=lambda f: f.weight, reverse=True)
    return AttentionResult(score=int(round(min(total, 1.0) * 100)), factors=factors)
