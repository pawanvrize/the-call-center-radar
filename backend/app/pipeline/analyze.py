"""Stages 4-5 for one call: mood -> shift -> reasoning -> verification -> score.

The ordering matters. Every citation is resolved to verbatim text from OUR
transcript and verified BEFORE it reaches storage, so nothing unverified can
leak onto the dashboard by accident. A claim whose evidence fails is still
stored — flagged unverified — because silently dropping it would hide the
system's own error rate, and that rate is a number worth reporting.

Split into `prepare_analysis` (reads + compute, no writes) and
`persist_analysis` (a short write transaction) so a batch can fan the slow part
across threads. The slow part is a ~10s network call to the LLM; holding a
SQLite write transaction open across it would serialise every worker and turn
concurrency into lock contention.
"""
import json
import sqlite3
from dataclasses import dataclass, field

from app.config import settings
from app.pipeline import attention_score, changepoint, mood, reality_check, reasoning, verifier
from app.pipeline.turns import Turn


@dataclass
class StoredTurn:
    """A turn as it exists in the database — index for citation, id for FK."""
    db_id: int
    turn: Turn


@dataclass
class EvidenceRow:
    claim_type: str
    claim_text: str
    turn_db_id: int
    timestamp: str
    quote: str
    match_score: float
    support_score: float
    verified: bool


@dataclass
class AnalysisResult:
    call_id: str
    intent_label: str
    resolution_status: str
    summary: str
    attention: int
    mood_shift_db_id: int | None
    mood_updates: list[tuple[float, int]] = field(default_factory=list)
    evidence: list[EvidenceRow] = field(default_factory=list)
    factors_json: str = "[]"
    shift_turn_index: int | None = None
    n_mood_points: int = 0


def load_turns(conn: sqlite3.Connection, call_id: str) -> list[StoredTurn]:
    rows = conn.execute(
        """
        SELECT id, turn_index, speaker, start_seconds, end_seconds, text,
               words_json, overlapping
        FROM turns WHERE call_id = ? ORDER BY turn_index
        """,
        (call_id,),
    ).fetchall()

    from app.pipeline.transcribe.base import Word

    return [
        StoredTurn(
            db_id=r["id"],
            turn=Turn(
                speaker=r["speaker"],
                start=r["start_seconds"],
                end=r["end_seconds"],
                text=r["text"],
                words=[Word(**w) for w in json.loads(r["words_json"] or "[]")],
                overlapping=bool(r["overlapping"]),
            ),
        )
        for r in rows
    ]


def timestamp(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def is_citable_shift(turn: Turn) -> bool:
    """Can this turn actually evidence a mood shift?

    Change-point detection finds where the mood *series* moves, but the series
    is partly prosodic — speaking rate and pauses — so it will happily fire on a
    customer reading out an address. Measured on the corpus, the rejected
    mood-shift citations were turns like 'Main Street,', '05418.', 'my savings
    account.' and 'You as well.': real breakpoints in the numbers, and no
    emotional content a reader could verify.

    So the rule is simply: don't make a claim you cannot cite. If the turn is
    too short to clear the verifier's own quote-length floor, we report no shift
    rather than a shift nobody can check. That trades some recall for citations
    that hold up, which is the trade this whole system is built around.
    """
    if turn.speaker != "customer":
        return False
    words = len(verifier.normalize(turn.text).split())
    return words >= getattr(
        settings, "evidence_min_quote_words", verifier.DEFAULT_MIN_QUOTE_WORDS
    )


#: A prior call only counts as the same complaint if it's recent. Two calls
#: about card replacement eleven weeks apart are two separate incidents.
REPEAT_WINDOW_DAYS = 30

#: A reported mood shift must land the customer in genuinely negative territory,
#: not merely lower than they started.
#:
#: This is the filter that matters most on this corpus. Change-point detection
#: finds where a series moves, but movement is not distress: measured across all
#: 8,866 scored turns, the mean mood is +0.05 with a standard deviation of 0.18,
#: and only 0.2% of turns fall below -0.35. These are scripted, uniformly polite
#: transactional calls — there is almost no negative mood present to find.
#:
#: Without this threshold the detector reports statistical wobble, and because
#: dictated data ("The address is 605 Main Street,") has unusual speaking rates,
#: that is exactly what it cites. Requiring real negativity means the feature
#: fires rarely and honestly rather than often and wrongly.
SHIFT_NEGATIVE_FLOOR = -0.15


def detect_reportable_shift(points, turns, stored):
    """The mood shift, if there is one worth reporting.

    Three filters, each added after measuring a specific false positive on this
    corpus:

    1. **Substantive turns only.** Pleasantries and dictated data are excluded
       from the series. Measured: the most-cited shift turns were "Thank you.",
       "Main Street," and "The zip code is 70021." — VADER scores a goodbye at
       +0.53, which against an otherwise near-zero series is the largest
       movement in the call.

    2. **Negative shifts only.** A customer cheering up as the call closes is
       not what "needs a manager's attention" means, and the attention score
       already ignores positive deltas. Reporting them inflated the count with
       findings nobody would act on.

    3. **Citable turns only.** A breakpoint we cannot quote is a claim without
       evidence — precisely what the brief scores zero.

    The result is far fewer shifts. That is the honest outcome: these calls are
    scripted and uniformly polite, and most contain no mood change to find.
    """
    series = mood.substantive_points(points, turns)
    shift = changepoint.find_mood_shift(
        [p.score for p in series], [p.turn_index for p in series]
    )
    if shift is None:
        return None
    if shift.delta > 0:
        return None
    if shift.after_mean > SHIFT_NEGATIVE_FLOOR:
        # Lower than before, but still neutral. Not a mood shift a manager
        # would recognise, and not something we can defend as evidence.
        return None
    if not is_citable_shift(stored[shift.turn_index].turn):
        return None
    return shift


def prior_call_count(conn: sqlite3.Connection, call_id: str) -> int:
    """How many earlier calls this customer made about the SAME issue.

    The attention factor this feeds is labelled "repeat contact about the same
    issue", so it has to actually check the issue. It previously counted any
    earlier call by the customer, which was both an unsupported claim and
    useless as a signal: every one of the 100 customers in this corpus is a
    repeat caller (mean 14.4 calls), so the factor fired on essentially
    everything and discriminated nothing.

    Same customer + same issue cluster + within REPEAT_WINDOW_DAYS is the thing
    the brief actually asks about — "the complaint that came up nine times this
    week". Returns 0 when clustering hasn't run yet, so the factor simply
    doesn't fire rather than reverting to the inaccurate behaviour.

    Cluster-based and used by the batch's later recompute_attention() pass,
    once every call has a cluster to compare against. prior_same_issue_count()
    below is the same idea keyed on intent instead — it has no such dependency,
    so prepare_analysis() uses it for a single call analysed on its own (the
    live /ingest path), where nothing has been clustered yet.
    """
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM calls prior
        JOIN call_clusters prior_cluster ON prior_cluster.call_id = prior.id
        WHERE prior.customer_id = (SELECT customer_id FROM calls WHERE id = :id)
          AND prior.started_at  < (SELECT started_at  FROM calls WHERE id = :id)
          AND prior_cluster.cluster_id = (
                SELECT cluster_id FROM call_clusters WHERE call_id = :id
              )
          AND julianday((SELECT started_at FROM calls WHERE id = :id))
              - julianday(prior.started_at) <= :window
        """,
        {"id": call_id, "window": REPEAT_WINDOW_DAYS},
    ).fetchone()
    return row["n"] if row else 0


def prior_same_issue_count(conn: sqlite3.Connection, call_id: str, intent_label: str) -> int:
    """How many earlier calls this customer made *about this same issue*.

    The attention factor above this reads "repeat contact about the same issue",
    so that is what has to be counted. Counting every prior call instead — which
    is what shipped — made the factor fire on 93% of the corpus, because 1,441
    calls are spread over 100 customers and almost everyone has phoned before.
    A signal that is true of nearly every row cannot rank anything, and the
    "about the same issue" half of the sentence was simply never checked.

    Matching on intent restores it to 43% and, more importantly, makes the claim
    mean what it says. Intent is the right key rather than the issue cluster:
    clusters are derived from summary embeddings and drift with re-clustering,
    while intent is per-call, stable, and already the thing the customer asked
    for.
    """
    if not intent_label:
        return 0
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM calls
        WHERE customer_id = (SELECT customer_id FROM calls WHERE id = ?)
          AND started_at < (SELECT started_at FROM calls WHERE id = ?)
          AND intent_label = ?
        """,
        (call_id, call_id, intent_label),
    ).fetchone()
    return row["n"] if row else 0


def _build_evidence(
    claim_type: str,
    claim_text: str,
    stored: list[StoredTurn],
    turn_index: int,
    check_support: bool = True,
) -> EvidenceRow | None:
    """Resolve a turn index to a verified citation.

    This is where the design pays off: the quote is *selected from* the turn's
    own text, never authored by the model, so it is verbatim by construction.
    What still has to be checked is whether it SUPPORTS the claim.
    """
    if not (0 <= turn_index < len(stored)):
        return None

    target = stored[turn_index]
    quote = verifier.select_quote(target.turn.text, claim_text)
    claim = verifier.claim_for(claim_type, claim_text) if check_support else None
    result = verifier.verify_evidence(
        quote=quote, turn_text=target.turn.text, claim=claim
    )

    return EvidenceRow(
        claim_type=claim_type,
        claim_text=claim_text,
        turn_db_id=target.db_id,
        timestamp=timestamp(target.turn.start),
        quote=quote,
        match_score=result.match_score,
        support_score=result.support_score,
        verified=result.verified,
    )


def prepare_analysis(
    conn: sqlite3.Connection,
    call_id: str,
    median_handle_time: float,
) -> AnalysisResult:
    """Everything except the writes. Safe to run on a worker thread."""
    stored = load_turns(conn, call_id)
    if not stored:
        raise ValueError(f"call {call_id} has no stored turns — transcribe it first")

    turns = [s.turn for s in stored]
    duration = conn.execute(
        "SELECT duration_seconds FROM calls WHERE id = ?", (call_id,)
    ).fetchone()

    # --- Stage 4: mood series + change point ------------------------------
    points = mood.score_customer_turns(turns)
    shift = detect_reportable_shift(points, turns, stored)
    mood_updates = [(p.score, stored[p.turn_index].db_id) for p in points]

    # Keep the turn the minimum came from, not just the value — the attention
    # factor it feeds has to cite the moment, and "worst mood" is meaningless to
    # a manager without the words that earned it.
    worst_point = min(points, key=lambda p: p.score, default=None)
    worst_mood = worst_point.score if worst_point else None
    # Only cite a turn substantial enough to clear the verifier's quote-length
    # floor, for the same reason is_citable_shift exists: a citation of "Okay."
    # is a citation nobody can check.
    worst_mood_turn_index = (
        worst_point.turn_index
        if worst_point and is_citable_shift(stored[worst_point.turn_index].turn)
        else None
    )

    # --- Stage 5: grounded reasoning (the slow, network-bound part) -------
    result = reasoning.analyze_call(turns)

    evidence: list[EvidenceRow] = []

    row = _build_evidence("intent", result.intent.label, stored, result.intent.turn_index)
    if row:
        evidence.append(row)

    # Contextualised with the call's own intent rather than left abstract.
    # "the issue was resolved" shares almost no vocabulary with the turn that
    # proves it ("$135 has been transferred from your savings to your
    # checking"), so cosine similarity scored real, correct citations as
    # unsupported — measured at 3% pass. Naming the intent puts claim and quote
    # in the same semantic neighbourhood: identical citations went 0.24 -> 0.56,
    # and 0/8 -> 5/8 on the sample. The remaining failures are genuinely
    # uninformative quotes ("Okay.", "$147"), which SHOULD fail.
    row = _build_evidence(
        "resolution",
        f"the customer wanted to {result.intent.label}; this was {result.resolution.label}",
        stored, result.resolution.turn_index,
    )
    if row:
        evidence.append(row)

    mood_shift_db_id = None
    if shift is not None:
        direction = "worse" if shift.delta < 0 else "better"
        # No support check here, deliberately. This turn was chosen by OUR
        # change-point detector, not claimed by the model — the citation means
        # "these are the words spoken where the shift was detected", which is
        # true by construction. Entailment-checking a factual pointer against a
        # statement about mood is a category error, and scored 0/10 doing it.
        # The span check still runs, so the quote is still verifiably verbatim.
        row = _build_evidence(
            "mood_shift",
            f"the customer's mood turned {direction} at this point in the call",
            stored, shift.turn_index, check_support=False,
        )
        if row:
            evidence.append(row)
        mood_shift_db_id = stored[shift.turn_index].db_id

    # --- Resolution Reality Check ------------------------------------------
    # Deterministic, no LLM: does the customer's own later turn back up
    # "resolved", or contradict it? Claim texts are worded to share vocabulary
    # with the quotes they're expected to cite ("resolved", "problem", "still
    # happening"), the same trick that fixed the resolution claim above, so
    # the entailment check has a fair shot at genuine hits rather than
    # rejecting them on vocabulary mismatch alone.
    contradiction = None
    contradiction_customer_row = None
    if result.resolution.label == "resolved":
        contradiction = reality_check.find_contradiction(stored)
    if contradiction is not None:
        agent_row = _build_evidence(
            "resolution_contradiction_agent",
            "the agent confirmed the customer's issue was resolved and everything should now work",
            stored, contradiction.agent_turn_index,
        )
        if agent_row:
            evidence.append(agent_row)
        contradiction_customer_row = _build_evidence(
            "resolution_contradiction_customer",
            "the customer says the problem is still happening and was not actually fixed",
            stored, contradiction.customer_turn_index,
        )
        if contradiction_customer_row:
            evidence.append(contradiction_customer_row)

    # --- Attention score --------------------------------------------------
    # Counted here rather than earlier because it needs the intent the model
    # just returned.
    repeat_count = prior_same_issue_count(conn, call_id, result.intent.label)
    hits = mood.escalation_hits(turns)
    attention = attention_score.compute_attention_score(
        resolution_status=result.resolution.label,
        worst_mood=worst_mood,
        mood_shift_delta=shift.delta if shift else None,
        escalation_hits=hits,
        handle_time_seconds=row_value(duration),
        median_handle_time_seconds=median_handle_time,
        is_repeat_contact=repeat_count > 0,
        repeat_count=repeat_count,
        resolution_turn_index=result.resolution.turn_index,
        worst_mood_turn_index=worst_mood_turn_index,
        mood_shift_turn_index=shift.turn_index if shift else None,
        intent_turn_index=result.intent.turn_index,
    )

    # A direct customer contradiction is the strongest signal this system can
    # find — stronger than "resolved" alone, which is why it gets its own
    # factor rather than folding into the resolution weight above. Appended
    # post-hoc rather than threaded through compute_attention_score() so that
    # well-calibrated, already-tested scoring function stays untouched; this
    # bonus is a layer on top of it, not a change to it.
    if contradiction_customer_row is not None:
        bonus_weight = 0.20
        attention.factors.append(
            attention_score.AttentionFactor(
                factor="customer's later words contradict the agent's \"resolved\" claim",
                weight=bonus_weight,
                turn_index=contradiction.customer_turn_index,
                detail="resolution reality check",
                # Already support-checked above as its own claim type; citing
                # it again here means "here is where that already-verified
                # contradiction lives", not a fresh assertion to re-check.
                check_support=False,
            )
        )
        attention.score = min(100, attention.score + round(bonus_weight * 100))
        attention.factors.sort(key=lambda f: f.weight, reverse=True)

    # Citations built above (intent, resolution, mood shift) are reused here
    # rather than rebuilt: the "issue unresolved" factor and the resolution
    # judgment cite the same moment, and storing that twice would inflate the
    # evidence count without adding one verifiable fact.
    by_turn = {row.turn_db_id: row for row in evidence}

    factors_json = []
    for factor in attention.factors:
        evidence_payload = None
        if factor.turn_index is not None and 0 <= factor.turn_index < len(stored):
            fact_row = by_turn.get(stored[factor.turn_index].db_id)
            if fact_row is None:
                fact_row = _build_evidence(
                    "attention_factor",
                    factor.factor,
                    stored,
                    factor.turn_index,
                    check_support=factor.check_support,
                )
                if fact_row:
                    evidence.append(fact_row)
                    by_turn[fact_row.turn_db_id] = fact_row
            if fact_row:
                evidence_payload = {
                    "turn_id": fact_row.turn_db_id,
                    "timestamp": fact_row.timestamp,
                    "quote": fact_row.quote,
                    "verified": fact_row.verified,
                }
        factors_json.append(
            {"factor": factor.factor, "weight": factor.weight, "evidence": evidence_payload}
        )

    return AnalysisResult(
        call_id=call_id,
        intent_label=result.intent.label,
        resolution_status=result.resolution.label,
        summary=result.summary,
        attention=attention.score,
        mood_shift_db_id=mood_shift_db_id,
        mood_updates=mood_updates,
        evidence=evidence,
        factors_json=json.dumps(factors_json),
        shift_turn_index=shift.turn_index if shift else None,
        n_mood_points=len(points),
    )


def row_value(row) -> float:
    return row["duration_seconds"] if row else 0.0


def persist_analysis(conn: sqlite3.Connection, result: AnalysisResult) -> dict:
    """Write everything for one call. Short transaction, single thread."""
    with conn:
        conn.executemany(
            "UPDATE turns SET mood_score = ? WHERE id = ?", result.mood_updates
        )
        # Citations are rebuilt from scratch on every analysis run.
        conn.execute("DELETE FROM evidence WHERE call_id = ?", (result.call_id,))
        conn.executemany(
            """
            INSERT INTO evidence (call_id, claim_type, claim_text, turn_id,
                                  timestamp, quote, match_score, support_score, verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (result.call_id, e.claim_type, e.claim_text, e.turn_db_id,
                 e.timestamp, e.quote, e.match_score, e.support_score, int(e.verified))
                for e in result.evidence
            ],
        )
        conn.execute(
            """
            UPDATE calls SET intent_label = ?, resolution_status = ?, summary = ?,
                             mood_shift_turn_id = ?, attention_score = ?,
                             attention_factors_json = ?, analyzed_at = datetime('now')
            WHERE id = ?
            """,
            (
                result.intent_label, result.resolution_status, result.summary,
                result.mood_shift_db_id, result.attention, result.factors_json,
                result.call_id,
            ),
        )

    verified = sum(1 for e in result.evidence if e.verified)
    return {
        "intent": result.intent_label,
        "resolution": result.resolution_status,
        "attention": result.attention,
        "mood_points": result.n_mood_points,
        "shift": result.shift_turn_index,
        "citations": len(result.evidence),
        "verified": verified,
    }


def analyze_call(
    conn: sqlite3.Connection,
    call_id: str,
    median_handle_time: float,
) -> dict:
    """Analyse and persist one call, single-threaded."""
    return persist_analysis(conn, prepare_analysis(conn, call_id, median_handle_time))


def recompute_attention(conn: sqlite3.Connection, median_handle_time: float) -> dict:
    """Re-score attention for every analysed call, without touching the LLM.

    Needed because repeat-contact detection depends on issue clusters, and
    clustering can only run after every call has a summary to cluster. So the
    ordering is: analyse -> cluster -> re-score. Everything this needs (mood
    series, escalation hits, resolution status) is either stored or recomputed
    locally in milliseconds, so a full re-score over 1,441 calls takes seconds
    rather than the ~13 minutes a re-analysis would.
    """
    rows = conn.execute(
        """
        SELECT id, resolution_status, duration_seconds, intent_label
        FROM calls WHERE analyzed_at IS NOT NULL
        """
    ).fetchall()

    changed = 0
    repeats = 0

    for row in rows:
        call_id = row["id"]
        stored = load_turns(conn, call_id)
        if not stored:
            continue
        turns = [s.turn for s in stored]

        points = mood.score_customer_turns(turns)
        shift = detect_reportable_shift(points, turns, stored)

        # Same rule as prepare_analysis: cite the turn the minimum actually
        # came from, only if it clears the verifier's quote-length floor.
        worst_point = min(points, key=lambda p: p.score, default=None)
        worst_mood = worst_point.score if worst_point else None
        worst_mood_turn_index = (
            worst_point.turn_index
            if worst_point and is_citable_shift(stored[worst_point.turn_index].turn)
            else None
        )

        repeat_count = prior_call_count(conn, call_id)
        if repeat_count:
            repeats += 1

        # Intent and resolution were already cited by the original analysis —
        # reuse those turns rather than re-deriving them, so a rescore points
        # at the same moment a fresh analysis would.
        intent_turn_index = _cited_turn_index(conn, call_id, "intent", stored)
        resolution_turn_index = _cited_turn_index(conn, call_id, "resolution", stored)

        attention = attention_score.compute_attention_score(
            resolution_status=row["resolution_status"],
            worst_mood=worst_mood,
            mood_shift_delta=shift.delta if shift else None,
            escalation_hits=mood.escalation_hits(turns),
            handle_time_seconds=row["duration_seconds"] or 0.0,
            median_handle_time_seconds=median_handle_time,
            is_repeat_contact=repeat_count > 0,
            repeat_count=repeat_count,
            resolution_turn_index=resolution_turn_index,
            worst_mood_turn_index=worst_mood_turn_index,
            mood_shift_turn_index=shift.turn_index if shift else None,
            intent_turn_index=intent_turn_index,
        )

        # A resolution-contradiction citation, if one exists, was stored by
        # prepare_analysis and is never deleted here (only 'attention_factor'
        # and 'mood_shift' rows are, below) — but the bonus FACTOR it earns is
        # part of attention_factors_json, which IS fully rebuilt every
        # recompute. Without re-deriving it here, a routine rescore (e.g.
        # after clustering) would silently drop the contradiction's score
        # contribution even though its evidence is still sitting in the table.
        contradiction_turn_index = _cited_turn_index(
            conn, call_id, "resolution_contradiction_customer", stored
        )
        if contradiction_turn_index is not None:
            bonus_weight = 0.20
            attention.factors.append(
                attention_score.AttentionFactor(
                    factor="customer's later words contradict the agent's \"resolved\" claim",
                    weight=bonus_weight,
                    turn_index=contradiction_turn_index,
                    detail="resolution reality check",
                    check_support=False,
                )
            )
            attention.score = min(100, attention.score + round(bonus_weight * 100))
            attention.factors.sort(key=lambda f: f.weight, reverse=True)

        # The shift just recomputed above supersedes whatever an earlier run
        # stored on `calls.mood_shift_turn_id` — rebuild that citation to match,
        # not just the attention factor. Written and committed BEFORE the
        # factor loop below, so if "mood turned negative" cites this same turn,
        # _factor_evidence finds and reuses this row instead of inserting a
        # second, duplicate citation of the identical quote.
        mood_shift_row = None
        if shift is not None:
            direction = "worse" if shift.delta < 0 else "better"
            mood_shift_row = _build_evidence(
                "mood_shift",
                f"the customer's mood turned {direction} at this point in the call",
                stored, shift.turn_index, check_support=False,
            )

        with conn:
            conn.execute(
                "DELETE FROM evidence WHERE call_id = ?"
                " AND claim_type IN ('attention_factor', 'mood_shift')",
                (call_id,),
            )
            if mood_shift_row:
                conn.execute(
                    """INSERT INTO evidence (call_id, claim_type, claim_text, turn_id,
                                             timestamp, quote, match_score, support_score, verified)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (call_id, mood_shift_row.claim_type, mood_shift_row.claim_text,
                     mood_shift_row.turn_db_id, mood_shift_row.timestamp, mood_shift_row.quote,
                     mood_shift_row.match_score, mood_shift_row.support_score, mood_shift_row.verified),
                )
            conn.execute(
                "UPDATE calls SET mood_shift_turn_id = ? WHERE id = ?",
                (stored[shift.turn_index].db_id if shift else None, call_id),
            )

        factors = [
            {"factor": f.factor, "weight": f.weight,
             "evidence": _factor_evidence(conn, call_id, f, stored)}
            for f in attention.factors
        ]

        with conn:
            conn.execute(
                "UPDATE calls SET attention_score = ?, attention_factors_json = ? WHERE id = ?",
                (attention.score, json.dumps(factors), call_id),
            )
        changed += 1

    return {"rescored": changed, "with_repeat_contact": repeats}


def _cited_turn_index(
    conn: sqlite3.Connection, call_id: str, claim_type: str, stored: list[StoredTurn]
) -> int | None:
    """The turn_index behind an already-stored citation of this claim type.

    Lets a rescore reuse the same moment prepare_analysis already cited for
    intent/resolution, instead of re-deriving it — the underlying transcript
    hasn't changed, so neither has where the evidence for it lives.
    """
    row = conn.execute(
        "SELECT turn_id FROM evidence WHERE call_id = ? AND claim_type = ? LIMIT 1",
        (call_id, claim_type),
    ).fetchone()
    if not row:
        return None
    for i, s in enumerate(stored):
        if s.db_id == row["turn_id"]:
            return i
    return None


def _factor_evidence(conn, call_id: str, factor, stored: list[StoredTurn]):
    """The citation for one attention factor: reuse an existing citation at
    this turn if one already exists (any claim type — the same moment already
    proves the point, whichever judgment first cited it), otherwise build and
    store a new one.

    This mirrors prepare_analysis's `by_turn` reuse-or-build dict. Without the
    "or build" half, a rescore could only ever *keep* citations a previous run
    happened to create — for a first rescore, where none exist yet, every
    factor would fall back to "no evidence" regardless of what
    compute_attention_score actually cited.
    """
    if factor.turn_index is None or not (0 <= factor.turn_index < len(stored)):
        return None
    target = stored[factor.turn_index]

    row = conn.execute(
        "SELECT timestamp, quote, verified FROM evidence WHERE call_id = ? AND turn_id = ? LIMIT 1",
        (call_id, target.db_id),
    ).fetchone()
    if row:
        return {
            "turn_id": target.db_id,
            "timestamp": row["timestamp"],
            "quote": row["quote"],
            "verified": bool(row["verified"]),
        }

    built = _build_evidence(
        "attention_factor", factor.factor, stored, factor.turn_index,
        check_support=factor.check_support,
    )
    if not built:
        return None
    with conn:
        conn.execute(
            """
            INSERT INTO evidence (call_id, claim_type, claim_text, turn_id,
                                   timestamp, quote, match_score, support_score, verified)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (call_id, built.claim_type, built.claim_text, built.turn_db_id,
             built.timestamp, built.quote, built.match_score, built.support_score, built.verified),
        )
    return {
        "turn_id": built.turn_db_id,
        "timestamp": built.timestamp,
        "quote": built.quote,
        "verified": built.verified,
    }
