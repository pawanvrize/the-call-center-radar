"""The attention score drives the product's flagship ranking, so its arithmetic
needs to be pinned down — not just "produces a number"."""
import pytest

from app.pipeline.attention_score import WEIGHTS, compute_attention_score


def score(**kwargs) -> int:
    defaults = dict(
        resolution_status="resolved",
        worst_mood=0.0,
        mood_shift_delta=None,
        escalation_hits=[],
        handle_time_seconds=60.0,
        median_handle_time_seconds=60.0,
        is_repeat_contact=False,
    )
    return compute_attention_score(**{**defaults, **kwargs}).score


def test_a_clean_resolved_call_scores_zero():
    assert score() == 0


def test_unresolved_outweighs_partial():
    assert score(resolution_status="unresolved") > score(resolution_status="partial")
    assert score(resolution_status="partial") > score(resolution_status="resolved")


def test_positive_mood_does_not_add_to_the_score():
    """A happy customer is not a reason to escalate."""
    assert score(worst_mood=0.8) == 0


def test_mood_improving_is_not_penalised():
    """A call that starts badly and ends well is a success story. Only a shift
    for the worse should raise the score."""
    assert score(mood_shift_delta=+0.6) == 0
    assert score(mood_shift_delta=-0.6) > 0


def test_escalation_language_saturates():
    """Three escalation phrases is not three times as urgent as one."""
    one = score(escalation_hits=[(3, "speak to a manager")])
    many = score(escalation_hits=[(3, "speak to a manager"), (5, "lawsuit"),
                                  (7, "unacceptable"), (9, "supervisor")])
    assert one > 0
    assert many > one
    assert many <= round(WEIGHTS["escalation"] * 100) + 1


def test_worst_case_call_approaches_100():
    result = compute_attention_score(
        resolution_status="unresolved",
        worst_mood=-1.0,
        mood_shift_delta=-1.0,
        escalation_hits=[(1, "lawsuit"), (2, "speak to a manager")],
        handle_time_seconds=300.0,
        median_handle_time_seconds=60.0,
        is_repeat_contact=True,
        repeat_count=5,
    )
    assert result.score == 100


def test_score_is_bounded():
    assert 0 <= score(resolution_status="unresolved", worst_mood=-5.0) <= 100


def test_factors_are_returned_sorted_and_only_when_they_fire():
    result = compute_attention_score(
        resolution_status="unresolved",
        worst_mood=-0.2,
        mood_shift_delta=None,
        escalation_hits=[],
        handle_time_seconds=60.0,
        median_handle_time_seconds=60.0,
        is_repeat_contact=False,
    )
    names = [f.factor for f in result.factors]
    assert any("unresolved" in n for n in names)
    assert not any("escalation" in n for n in names)  # didn't fire, not listed
    weights = [f.weight for f in result.factors]
    assert weights == sorted(weights, reverse=True)


def test_escalation_factor_carries_a_citable_turn():
    result = compute_attention_score(
        resolution_status="resolved", worst_mood=0.0, mood_shift_delta=None,
        escalation_hits=[(7, "speak to a manager")],
        handle_time_seconds=60.0, median_handle_time_seconds=60.0,
        is_repeat_contact=False,
    )
    factor = next(f for f in result.factors if "escalation" in f.factor)
    assert factor.turn_index == 7


@pytest.mark.parametrize("status", ["resolved", "partial", "unresolved", None])
def test_handles_every_resolution_status(status):
    assert 0 <= score(resolution_status=status) <= 100


# --- citations -----------------------------------------------------------
# "A claim with no evidence scores zero." The attention score is a claim, and
# so is every factor under it, so each one that can point at a spoken moment
# must carry the turn to cite.


def factors(**kwargs):
    defaults = dict(
        resolution_status="resolved",
        worst_mood=0.0,
        mood_shift_delta=None,
        escalation_hits=[],
        handle_time_seconds=60.0,
        median_handle_time_seconds=60.0,
        is_repeat_contact=False,
    )
    return compute_attention_score(**{**defaults, **kwargs}).factors


def one(name_fragment, **kwargs):
    matches = [f for f in factors(**kwargs) if name_fragment in f.factor]
    assert matches, f"no factor matching {name_fragment!r} in {[f.factor for f in factors(**kwargs)]}"
    return matches[0]


def test_unresolved_factor_cites_the_resolution_turn():
    f = one("issue unresolved", resolution_status="unresolved", resolution_turn_index=12)
    assert f.turn_index == 12


def test_negative_mood_factor_cites_the_worst_mood_turn():
    f = one("negative customer mood", worst_mood=-0.7, worst_mood_turn_index=4)
    assert f.turn_index == 4
    # Our own minimum picked this turn, so entailment-checking it against the
    # abstract factor text is a category error — the citation is a pointer.
    assert f.check_support is False


def test_mood_shift_factor_cites_the_change_point_turn():
    f = one("mood turned negative", mood_shift_delta=-0.6, mood_shift_turn_index=9)
    assert f.turn_index == 9
    assert f.check_support is False


def test_long_call_factor_stays_uncited():
    """A long call is a fact about the clock, not about anything anyone said.
    Attaching a quote would be evidence that does not support the claim, which
    the brief scores NEGATIVE — strictly worse than the zero for staying quiet."""
    f = one("unusually long call", handle_time_seconds=300.0, median_handle_time_seconds=60.0)
    assert f.turn_index is None


def test_missing_turn_index_degrades_rather_than_inventing_one():
    """Callers that cannot supply a turn still get a factor — just an uncited
    one. Silently fabricating an index would be far worse."""
    f = one("issue unresolved", resolution_status="unresolved")
    assert f.turn_index is None


def test_repeat_contact_factor_cites_the_intent_turn():
    """The factor says "about this issue", so it cites the customer stating
    that issue. The ordinal count of earlier calls is a database fact carried
    in the factor/detail text — a quote cannot prove "again", only "about
    this"."""
    f = one("call about this issue", is_repeat_contact=True, repeat_count=2, intent_turn_index=1)
    assert f.turn_index == 1
    assert f.factor == "3rd call about this issue"
    assert "2 earlier call" in f.detail


def test_mood_factor_stays_silent_on_mild_negativity():
    """VADER scores 'I lost my debit card' and 'No thanks' negative because of
    the topic and the word "no", not because the customer is unhappy. Claiming
    those as negative mood, and citing them, is evidence that does not support
    the claim — which scores worse than saying nothing."""
    assert not [f for f in factors(worst_mood=-0.10) if "negative customer mood" in f.factor]
    assert [f for f in factors(worst_mood=-0.55) if "negative customer mood" in f.factor]
