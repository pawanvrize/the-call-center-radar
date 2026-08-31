"""Response models. Every judgment field pairs with an Evidence — a claim without
one is a schema violation, not a runtime hope."""
from typing import Literal

from pydantic import BaseModel


class Evidence(BaseModel):
    turn_id: int
    timestamp: str  # "HH:MM:SS"
    quote: str
    verified: bool  # result of the fuzzy-match check against the transcript


class Word(BaseModel):
    text: str
    start: float
    end: float
    confidence: float


class Turn(BaseModel):
    id: int
    turn_index: int
    speaker: Literal["agent", "customer"]
    start_seconds: float
    end_seconds: float
    text: str
    words: list[Word] = []
    mood_score: float | None = None
    overlapping: bool = False


class AttentionFactor(BaseModel):
    factor: str
    weight: float
    evidence: Evidence | None = None


class ResolutionContradiction(BaseModel):
    """Resolution Reality Check: the agent's claim and the customer's own
    later words, side by side. Present only when both were found — a rule-
    based check (pipeline/reality_check.py), not an LLM judgment, so no
    partial/uncertain state exists to represent."""
    agent_evidence: Evidence
    customer_evidence: Evidence


class CallDetail(BaseModel):
    id: str
    customer_id: str
    customer_name: str
    agent_id: str
    agent_name: str
    started_at: str
    duration_seconds: float
    audio_url: str
    transcript_provider: Literal["assemblyai", "whisper"]

    turns: list[Turn]

    intent_label: str | None
    intent_evidence: Evidence | None

    resolution_status: Literal["resolved", "unresolved", "partial"] | None
    resolution_evidence: Evidence | None

    summary: str | None  # <= 40 words

    mood_shift_turn_id: int | None
    mood_shift_evidence: Evidence | None

    attention_score: int | None  # 0-100
    attention_factors: list[AttentionFactor] = []

    resolution_contradiction: ResolutionContradiction | None = None

    #: % of this call's evidence rows that passed verification. None when the
    #: call has no evidence yet (not analysed). Answers a different question
    #: than the attention score: "how much of what the system told you about
    #: THIS call can you actually trace back to the transcript?"
    evidence_coverage: float | None = None


class CallSummary(BaseModel):
    id: str
    started_at: str
    duration_seconds: float
    intent_label: str | None
    resolution_status: str | None
    summary: str | None
    attention_score: int | None

    #: % of this call's evidence rows that passed verification — same figure
    #: as CallDetail.evidence_coverage, so a list row can flag "some claims
    #: here are unverified" before a manager ever opens the call. None when
    #: not yet analysed (no evidence rows exist).
    evidence_coverage: float | None = None


class Customer(BaseModel):
    id: str
    name: str
    call_count: int
    last_contact: str | None


class AgentIssueStat(BaseModel):
    """How one agent performs on one issue type."""
    cluster_id: int
    label: str
    call_count: int
    resolution_rate: float
    #: Percentage points versus this agent's OWN overall rate. Comparing an
    #: agent against themselves isolates "this issue is hard for them" from
    #: "this agent is weaker overall".
    delta_vs_self: float


class AgentStats(BaseModel):
    id: str
    name: str
    call_count: int
    avg_handle_time_seconds: float
    resolution_rate: float
    avg_attention_score: float
    #: The issue this agent handles worst relative to their own baseline —
    #: the coaching signal. None when no issue has enough calls to judge.
    weakest_issue: AgentIssueStat | None = None


class RepeatContact(BaseModel):
    """One customer calling repeatedly about the same issue.

    The brief's own example — "the complaint that came up nine times this week".
    Keyed on issue cluster, not just customer: every customer in this corpus is
    a repeat caller, so only same-issue repetition carries information.
    """
    customer_id: str
    customer_name: str
    cluster_id: int
    issue_label: str
    call_count: int
    unresolved_count: int
    first_call_at: str
    last_call_at: str
    span_days: float
    calls: list[CallSummary]


class TrendingIssue(BaseModel):
    cluster_id: int
    label: str
    call_count: int
    counts_by_day: dict[str, int]

    # Outcome quality is the real signal in this corpus. With only four
    # non-contiguous recording days, per-day counts mirror the recording
    # schedule rather than any trend — these fields are what actually
    # distinguish one issue from another.
    resolution_rate: float
    avg_attention_score: float
    avg_handle_time_seconds: float

    #: Cluster's share of each day's calls. Comparable across days in a way raw
    #: counts are not: a day with 95 calls and one with 369 look identical here
    #: unless the issue genuinely over- or under-indexes on that day.
    share_by_day: dict[str, float]


class TrendsBaseline(BaseModel):
    """Corpus-wide averages, so a cluster's numbers can be read as better or
    worse than typical rather than in isolation."""
    call_count: int
    resolution_rate: float
    avg_attention_score: float
    avg_handle_time_seconds: float


class TrendsResponse(BaseModel):
    baseline: TrendsBaseline
    issues: list[TrendingIssue]
