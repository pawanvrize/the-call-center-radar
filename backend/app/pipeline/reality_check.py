"""Resolution Reality Check: does the customer's OWN later turn back up
"resolved", or contradict it?

Every other judgment in this pipeline is model-derived and then verified.
This one is the reverse — fully rule-based, no LLM call, no new failure mode
to worry about this close to submission. It only runs when the call is
already labelled "resolved": an unresolved call has nothing to contradict.

Two phrase families, in the same spirit as scripts/fix_channel_swaps.py's
greeting regex: specific enough that a hit has no innocent explanation, rather
than a broad net that needs a disambiguation pass afterwards. Order matters —
only a customer turn AFTER the agent's claim counts, because frustration
BEFORE the claim is the reason the agent made it, not a rebuttal to it.

Measured against this corpus's overall pattern (documented in
attention_score.py: scripted, uniformly polite calls, zero escalation hits
across 8,866 customer turns): a genuine post-claim contradiction is expected
to be rare-to-absent here, same as the honest 0/1441 mood-shift result. That
is not a reason to skip building it — a live /ingest call with a customer who
pushes back after the agent's "should be all set" is exactly the case this
exists to catch, demo-able the same way the mood-shift detector already is.
"""
import re
from dataclasses import dataclass

AGENT_CLAIM = re.compile(
    r"(should\s+(be|have)\s+(all\s+set|fixed|resolved|sorted|taken\s+care\s+of)"
    r"|(is|has\s+been|should\s+be)\s+(now\s+)?(resolved|fixed)"
    r"|you'?re\s+all\s+set"
    r"|that\s+should\s+(do\s+it|take\s+care\s+of\s+it))",
    re.IGNORECASE,
)

CUSTOMER_CONTRADICTION = re.compile(
    r"(still\s+(not\s+working|failing|broken|the\s+same|doesn'?t\s+work|not\s+fixed"
    r"|have\s+(the|this)\s+(same\s+)?(problem|issue))"
    r"|(didn'?t|did\s+not|does\s?n'?t)\s+(fix|solve|work)"
    r"|same\s+(problem|issue)\s+(again|as\s+before)"
    r"|that'?s\s+not\s+(fixed|right|working))",
    re.IGNORECASE,
)


@dataclass
class Contradiction:
    agent_turn_index: int
    customer_turn_index: int


def find_contradiction(stored: list) -> Contradiction | None:
    """`stored` is a list of `analyze.StoredTurn` (untyped here to avoid a
    circular import — analyze.py imports this module, not the reverse).

    Returns the FIRST agent claim and the FIRST customer turn after it that
    contradicts it, or None. One hit is enough to flag the call; scanning for
    every occurrence would only add noise a manager doesn't need.
    """
    for i, s in enumerate(stored):
        if s.turn.speaker != "agent" or not AGENT_CLAIM.search(s.turn.text):
            continue
        for j in range(i + 1, len(stored)):
            candidate = stored[j]
            if candidate.turn.speaker == "customer" and CUSTOMER_CONTRADICTION.search(
                candidate.turn.text
            ):
                return Contradiction(agent_turn_index=i, customer_turn_index=j)
    return None
