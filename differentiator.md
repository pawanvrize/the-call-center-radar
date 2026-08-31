# Call-Centre Radar — Differentiators for Winning the Hackathon

> Goal: turn Call-Centre Radar from a normal "Whisper + LLM + dashboard" project into an **evidence-backed investigation and action system**.
>
> Core principle:
>
> **Don't just tell the manager what happened. Show what needs attention, why it matters, and let the manager jump directly to the evidence in the call.**

---

# 1. What Is Already Table Stakes?

The hackathon itself requires:

- raw audio → transcript;
- speaker identification;
- turn-by-turn timestamps;
- customer intent;
- customer mood;
- mood-shift timestamp;
- resolution status;
- <=40-word summary;
- manager-attention ranking;
- issue trends;
- agent volume / handle time / outcomes;
- customer history;
- playable recordings;
- transcript;
- mood timeline;
- API;
- dashboard;
- evidence timestamp + spoken words behind every judgment.

So these features are **mandatory**, but they should not be presented as the main innovation.

The main innovation should sit on top of these capabilities.

---

# 2. Winning Product Positioning

## Do NOT pitch:

> "We built an AI call-centre analytics platform."

That category already has many examples.

## Pitch:

> **"Call-Centre Radar turns thousands of support calls into evidence-backed manager actions. It identifies what went wrong, proves why it believes that, and takes the manager directly to the exact moment in the call."**

The product loop becomes:

```text
RAW AUDIO
    ↓
TRANSCRIPT
    ↓
AI / RULE ANALYSIS
    ↓
EVIDENCE VALIDATION
    ↓
TRUSTED INSIGHT
    ↓
MANAGER ACTION
```

This should be the identity of the entire product.

---

# 3. Differentiator #1 — Evidence Graph

## Concept

Every important AI claim becomes a node connected to the exact transcript evidence supporting it.

```text
                         CALL
                          |
            +-------------+-------------+
            |             |             |
            v             v             v
          INTENT         MOOD       RESOLUTION
            |             |             |
            v             v             v
         Evidence      Evidence      Evidence
            |             |             |
            v             v             v
          01:17         03:42         04:58
            |             |             |
            v             v             v
       "card was      "I've called    "still
        declined"      3 times"       doesn't work"
```

## UX

Every insight has:

```text
[Why?]
```

Clicking it shows:

- timestamp;
- speaker;
- exact transcript text;
- audio seek action.

Example:

```text
Resolution: UNRESOLVED

Why?

04:58 — CUSTOMER
"It still doesn't work."

[▶ Jump to 04:58]
```

## Why it wins

Most AI demos ask the evaluator to trust the model.

This system asks the evaluator to **inspect the evidence**.

---

# 4. Differentiator #2 — Evidence Coverage Score

## Concept

Measure how much of the system's important output is actually backed by evidence.

Example:

```text
AI TRUST
━━━━━━━━━━━━━━━━━━
94%
Evidence Coverage
```

Breakdown:

```text
Intent                 ✓
Mood                   ✓
Mood shift             ✓
Resolution             ✓
Manager reason #1      ✓
Manager reason #2      ✓
```

Display:

```text
5 / 5 critical claims supported
```

## Why it wins

Traditional:

```text
LLM confidence = 92%
```

Our product:

```text
Evidence coverage = 94%
```

The second metric answers a more useful question:

> "How much of what the system is telling me can I actually trace back to the conversation?"

---

# 5. Differentiator #3 — AI Hallucination Firewall

## Concept

Never allow raw LLM output to become a manager-facing fact.

Pipeline:

```text
                 LLM
                  ↓
            Structured claims
                  ↓
           Evidence lookup
                  ↓
         Evidence validation
                  ↓
       Semantic/rule validation
             /           \
            /             \
        APPROVE          REJECT
           |               |
           v               v
       Dashboard       Needs Review
```

## Example

LLM says:

```text
Customer threatened legal action.
```

Evidence:

```text
"I have already called three times."
```

Validator:

```text
❌ REJECTED
Evidence does not support the claim.
```

The false claim must never be silently presented as fact.

---

# 6. Differentiator #4 — Evidence Quality Levels

Give every evidence-backed claim a quality level:

```text
DIRECT
INFERRED
WEAK
UNSUPPORTED
```

Recommended policy:

```text
DIRECT      → trusted manager-facing evidence
INFERRED    → allowed with warning
WEAK        → review required
UNSUPPORTED → reject
```

Example:

```text
Resolution
UNRESOLVED

Evidence quality: DIRECT
```

---

# 7. Differentiator #5 — Conversation Journey

Instead of only showing a sentiment graph, show the important stages of the call.

```text
CALL JOURNEY

00:00
  |
  v
Greeting
  |
  v
Problem identified
  |
  v
Troubleshooting
  |
  v
First frustration
  |
  v
Repeated explanation
  |
  v
Mood collapse
  |
  v
Escalation
  |
  v
Resolution / unresolved ending
```

Each event should be clickable.

This allows a manager to understand a 5-minute call in seconds.

---

# 8. Differentiator #6 — Mood Shift Detective

The brief specifically requires the point where mood shifts.

Do not make the LLM invent this timestamp.

## Detection

1. Calculate customer sentiment per transcript turn.
2. Smooth into time buckets.
3. Detect meaningful change points.
4. Require persistence to avoid a one-turn false positive.
5. Map the change point to the nearest customer utterance.
6. Store the original evidence segment.

Example:

```text
00:00  +0.42
01:00  +0.18
02:00  -0.04
03:00  -0.31
03:42  -0.68  ← SHIFT
04:10  -0.74
```

Then:

```text
Mood shift detected at 03:42

Likely cause:
Customer had to repeat the problem.

Evidence:
03:42 CUSTOMER
"I've already explained this three times."

[▶ Jump to 03:42]
```

---

# 9. Differentiator #7 — Conversation Turning Points

Not every timestamp matters.

Detect a small set of turning points:

```text
INTRO
PROBLEM_IDENTIFIED
PROBLEM_CLARIFIED
FIRST_NEGATIVE_CHANGE
REPETITION
ESCALATION
RESOLUTION_ATTEMPT
RESOLUTION_CONFIRMED
UNRESOLVED_END
```

Show them as timeline bookmarks.

Example:

```text
00:00       01:18       02:41       03:42       04:56
  ●-----------●-----------●-----------●-----------●
 Start       Intent      Repeat      Mood↓      Outcome
```

---

# 10. Differentiator #8 — Why Is This Call Dangerous?

Replace one opaque attention number with an explainable score.

Example:

```text
MANAGER ATTENTION
━━━━━━━━━━━━━━━━━━
92 / 100

WHY?

+25  Unresolved
+20  Strong negative mood
+15  Large mood deterioration
+10  Repeated explanation
+10  Escalation language
+07  Repeat-contact customer
+05  AI uncertainty / evidence risk
━━━━━━━━━━━━━━━━━━
92
```

Every component must be clickable.

---

# 11. Differentiator #9 — Counterfactual Attention Score

Show what would have lowered the risk.

Example:

```text
CURRENT
92 / 100

IF RESOLVED
67 / 100

IF MOOD SPIKE DID NOT OCCUR
77 / 100

IF ESCALATION DID NOT OCCUR
82 / 100
```

## Implementation

This does not need true causal inference.

Use the deterministic scoring engine:

```python
current_score = 92

without_unresolved = current_score - 25
without_mood_spike = current_score - 15
without_escalation = current_score - 10
```

The feature answers:

> "What was the biggest driver of manager risk?"

---

# 12. Differentiator #10 — Resolution Reality Check

This is one of the strongest product features.

Compare agent language with customer outcome signals.

Example:

```text
AGENT
"That should be resolved now."

CUSTOMER
"No, it is still failing."
```

System:

```text
⚠ RESOLUTION CONTRADICTION

Agent outcome:
Resolved

Customer outcome:
Unresolved

Confidence:
High
```

Evidence:

```text
04:02 Agent
"That should be sorted now."

04:11 Customer
"No, it's still failing."
```

This catches calls that look successful from an operational perspective but were not actually successful for the customer.

---

# 13. Differentiator #11 — Agent vs Customer Reality Gap

Create a dedicated view:

```text
AGENT VIEW
✓ Explained process
✓ Completed verification
✓ Gave next steps

CUSTOMER VIEW
⚠ Had to repeat issue
⚠ Remained frustrated
⚠ Did not confirm resolution
```

The feature identifies the difference between:

```text
procedure completed
```

and

```text
customer problem actually solved
```

---

# 14. Differentiator #12 — Customer Effort Score

Do not measure only sentiment.

Measure:

> **How hard did the customer have to work to get help?**

Signals:

- repeated explanation;
- repeated questions;
- transfers;
- long holds;
- long unexplained silence;
- repeated verification;
- interruptions;
- unresolved outcome;
- multiple contacts;
- frustration language.

Example:

```text
CUSTOMER EFFORT
━━━━━━━━━━━━━━━━━━
78 / 100
HIGH

3 repeated explanations
2 long waits
1 unresolved ending
```

This is more actionable than a simple sentiment label.

---

# 15. Differentiator #13 — Customer Repetition Index

Measure semantic repetition.

Example:

```text
CUSTOMER EXPLAINS THE SAME PROBLEM

01:03  First explanation
02:16  Second explanation
03:41  Third explanation
```

Then:

```text
REPETITION INDEX
83 / 100
```

Evidence:

- repeated issue segments;
- semantic similarity;
- elapsed time between explanations.

This can become a strong proxy for customer friction.

---

# 16. Differentiator #14 — Hidden Repeat Complaint Detector

Exact keyword matching is insufficient.

These may mean the same thing:

```text
"My debit card isn't working."

"My card keeps getting rejected."

"Payment won't go through."

"Why is my card being declined?"
```

Use embeddings + controlled intent labels to connect different wording to the same underlying issue.

Output:

```text
UNDERLYING ISSUE
CARD_DECLINED
```

This makes trend analytics much more reliable.

---

# 17. Differentiator #15 — Repeat Frustration Detector Across Customer History

Customer history should not be only a table.

Detect recurring unresolved problems.

Example:

```text
CUSTOMER: JOHN

Aug 21
Card declined → unresolved

Aug 25
Card declined → unresolved

Aug 30
Card declined → unresolved
```

System:

```text
🚨 RECURRING UNRESOLVED ISSUE

3 contacts
9 days
Same intent
0 confirmed resolutions
```

Then elevate the customer/call into the manager queue.

---

# 18. Differentiator #16 — Emerging Issue Radar

Static categories are not enough.

Find newly increasing issue clusters.

Example:

```text
EMERGING ISSUE

"ATM withdrawal balance mismatch"

This week:    38
Last week:    9
Growth:       +322%

Unresolved:   61%
Affected:     14 agents
```

Click:

```text
[View all 38 calls]
```

## Implementation

1. Extract customer problem statements.
2. Generate embeddings locally.
3. Cluster similar statements.
4. Label clusters with a local LLM.
5. Aggregate by date.
6. Calculate growth rate.
7. Rank by growth + volume + unresolved rate.

---

# 19. Differentiator #17 — Issue Radar

Visualize issues using multiple dimensions.

Suggested axes:

```text
X = growth rate
Y = unresolved rate
bubble size = call volume
bubble intensity = manager attention
```

Example interpretation:

```text
High growth + high unresolved = dangerous emerging issue
High volume + low unresolved = operationally normal
Low volume + high risk = specialist risk
```

This is more informative than a simple "top issues" bar chart.

---

# 20. Differentiator #18 — Team-Level Failure Detection

Do not only rank agents.

Identify systemic problems.

Example:

```text
TEAM ISSUE

CARD DECLINED
Unresolved rate:

Team average:  11%
Current issue: 37%

Affected:
14 agents
182 calls
```

Conclusion:

> This may be a process/problem-type issue rather than an individual-agent issue.

This moves the system from:

```text
agent monitoring
```

to:

```text
operations intelligence
```

---

# 21. Differentiator #19 — Agent Friction Map

Show performance by interaction stage.

```text
AGENT A

Greeting              94
Problem Discovery     81
Explanation           73
Empathy               88
Resolution             61
Closing                95
```

Then explain the weakest stage:

```text
BIGGEST FRICTION:
Resolution

18 unresolved calls
11 contained follow-up language
6 lacked customer confirmation
```

The agent page should be about **coachable behavior**, not only rankings.

---

# 22. Differentiator #20 — Dead-Air Intelligence

Do not simply calculate:

```text
Total silence = 52 sec
```

Classify silence.

```text
NORMAL
customer thinking

POSSIBLE SEARCH / HOLD
agent likely navigating systems

HIGH FRICTION
customer asked question and response was delayed

CRITICAL
long unexplained silence during escalation
```

Example:

```text
LONGEST UNEXPLAINED SILENCE

01:12 → 01:49
37 seconds

Context:
Customer asked for an explanation.
Agent response delayed.
```

Click to jump to the segment.

---

# 23. Differentiator #21 — Call Reliability Score

Separate business risk from AI/data reliability.

```text
MANAGER RISK
92 / 100

AI RELIABILITY
86 / 100
```

Break down:

```text
Audio quality          96
Transcript quality     91
Evidence coverage      94
Intent confidence      97
Mood confidence        77
```

This prevents false certainty.

---

# 24. Differentiator #22 — Audio Quality Awareness

Telephone audio can create model uncertainty.

Detect:

- low volume;
- clipping;
- heavy noise;
- corrupted segments;
- excessive overlap;
- unusually low speech confidence.

Output:

```text
TRANSCRIPT RELIABILITY
86 / 100
```

The manager sees both:

```text
business risk
```

and:

```text
measurement reliability
```

---

# 25. Differentiator #23 — Audio Bookmarks

Create intelligent audio bookmarks:

```text
● Intent
● Mood shift
● Repetition
● Risk
● Evidence
● Resolution
```

The timeline becomes:

```text
00:00 ───────●────────●──────●──────────●──── 05:12
             intent   repeat  mood↓      outcome
```

Every marker seeks the audio directly.

This makes the demo visually memorable.

---

# 26. Differentiator #24 — Conversation Compression

Measure the value of the product itself.

Example:

```text
CALL LENGTH
05:14

RADAR REVIEW
00:19
```

Show:

```text
Manager can review:
- why it matters;
- what changed;
- where it went wrong;
- what evidence proves it;
```

The product is not merely analyzing calls.

It is reducing the amount of **manager time required to understand calls**.

---

# 27. Differentiator #25 — Jump-to-Why

Every important element gets a standard UX pattern:

```text
[Why?]
```

Examples:

```text
Intent: Card Declined     [Why?]
Mood: Frustrated          [Why?]
Mood shift: 03:42         [Why?]
Resolution: Unresolved    [Why?]
Attention: 92             [Why?]
Repeat complaint         [Why?]
Emerging issue           [Why?]
```

One interaction:

```text
claim
→ evidence
→ transcript
→ audio
```

This should become the signature interaction of the application.

---

# 28. Differentiator #26 — Manager Inbox

Turn analytics into an operational workflow.

```text
TODAY'S ATTENTION QUEUE

1. CRITICAL
   Unresolved + escalation
   Score: 96
   [Review]

2. HIGH
   Repeat complaint
   Score: 91
   [Review]

3. HIGH
   Resolution contradiction
   Score: 88
   [Review]
```

Actions:

```text
Acknowledge
Assign
Escalate
Dismiss
Mark Reviewed
```

Persist actions in an audit table.

This makes the system a manager workflow rather than a passive report.

---

# 29. Differentiator #27 — Manager Feedback Loop

After review:

```text
CALL ANALYSIS

Prediction:
Unresolved

Manager:
[Correct] [Incorrect] [Needs Review]
```

Store:

```text
model_prediction
human_label
reviewer
timestamp
reason
```

Then dashboard:

```text
MODEL QUALITY

Intent accuracy
Resolution accuracy
Mood-shift accuracy
Evidence validity
Attention precision
```

This creates a path to future model improvement.

---

# 30. Differentiator #28 — Model Disagreement Radar

Run different signals:

```text
Rule engine
Classifier
LLM
```

If they disagree:

```text
⚠ MODEL DISAGREEMENT

LLM:         RESOLVED
Rule layer:  UNRESOLVED
Customer:    Strong negative

Decision:
NEEDS REVIEW
```

This is a strong way to use AI while avoiding blind trust.

---

# 31. Differentiator #29 — Uncertainty-Aware Dashboard

Do not pretend every prediction is equally reliable.

Example:

```text
Intent         94%   ✓
Resolution     91%   ✓
Mood           82%   ✓
Mood Shift     61%   ⚠
```

Policy:

```text
High confidence → normal
Medium confidence → warning
Low confidence → review
```

---

# 32. Differentiator #30 — Natural-Language Investigation

A manager can ask:

> Show calls where customers repeatedly complained about card declines and became frustrated.

Translate into:

```text
intent = CARD_DECLINED
AND repetition_index > threshold
AND mood_shift = negative
```

Then return matching calls.

All results still have evidence.

Do not build a free-form chatbot that can invent answers.

Build a constrained query system that maps natural language to:

```text
filters
semantic search
aggregations
```

---

# 33. Differentiator #31 — Ask the Call

On the call-detail page:

```text
ASK ABOUT THIS CALL

> Why did the customer become frustrated?
> Was the issue actually resolved?
> What went wrong?
> What should the agent have done differently?
```

Every answer must end with evidence:

```text
Answer:
Customer frustration increased after repeated explanations.

Evidence:
03:42 CUSTOMER
"I've already explained this three times."

[▶ Jump to 03:42]
```

The key rule:

**Ask the Call must never become an evidence-free chatbot.**

---

# 34. Differentiator #32 — Claim-to-Audio API

Make evidence a first-class backend concept.

Example:

```json
{
  "claim": "Customer card payment was declined",
  "evidence": {
    "segment_id": 12,
    "start": 87.4,
    "end": 91.0,
    "speaker": "customer",
    "text": "My card was declined again.",
    "audio_url": "/calls/abc/audio?t=87.4"
  }
}
```

This gives the frontend a direct contract:

```text
Claim
→ evidence
→ audio seek
```

---

# 35. Differentiator #33 — Evidence-Backed Summary

Normal summary:

> Customer called about a card problem.

Better summary:

```text
Customer reported repeated card declines,
became frustrated after repeated explanations,
and ended the call without confirmation of resolution.
```

But expose an evidence map:

```text
Summary sentence 1 → segments 8, 10
Summary sentence 2 → segments 21, 23
Summary sentence 3 → segment 33
```

This can be implemented as optional sentence-level evidence.

---

# 36. Differentiator #34 — Complaint → Root Cause Ladder

Do not stop at:

```text
Complaint:
Card declined
```

Build a ladder:

```text
CUSTOMER COMPLAINT
        ↓
CARD DECLINED
        ↓
REPEATED DECLINES
        ↓
TROUBLESHOOTING DID NOT RESOLVE
        ↓
CUSTOMER FRUSTRATION
        ↓
ESCALATION
```

The manager can see the chain of events.

This is especially useful for detecting:

```text
symptom
→ operational failure
→ customer experience impact
```

---

# 37. Differentiator #35 — "What Went Wrong?" Summary

A second summary can be optimized for managers:

```text
WHAT WENT WRONG?

Customer's issue was not resolved after three explanations.
The agent stated the issue should be fixed, but the customer
immediately disagreed.
```

Then:

```text
WHY?
[03:42] [04:11]
```

This is often more useful than another generic call summary.

---

# 38. Differentiator #36 — "What Should Happen Next?"

Make the output actionable:

```text
RECOMMENDED ACTION

1. Review this call.
2. Verify the underlying card-decline process.
3. Check whether the customer had prior unresolved contacts.
4. Coach the agent on explicit resolution confirmation.
```

Every recommendation should identify whether it is:

```text
evidence-backed
or
general best practice
```

Never present speculation as observed fact.

---

# 39. Differentiator #37 — Customer Escalation Prediction

Use only after the core system works.

Estimate:

```text
Probability of manager escalation
Probability of repeat contact
Probability of unresolved callback
```

Example:

```text
REPEAT-CONTACT RISK
74%

Drivers:
- same issue in previous calls;
- unresolved outcome;
- negative ending;
- customer explicitly requested follow-up.
```

Again, every observed driver must have evidence.

---

# 40. Differentiator #38 — Human Review Queue for Uncertainty

Not every call deserves equal processing effort.

Automatically route:

```text
HIGH RISK + LOW CONFIDENCE
```

into:

```text
HUMAN REVIEW
```

Example:

```text
Call 991

Attention: 91
AI reliability: 63

Reason:
Intent and resolution models disagree.

[Review]
```

This is a very strong enterprise design pattern.

---

# 41. Differentiator #39 — Smart Review Prioritization

The manager queue should not simply sort by attention score.

Use:

```text
Priority =
business risk
×
confidence
×
customer impact
×
repeat-contact risk
```

Example:

```text
Call A
Risk 95
Confidence 98
→ review immediately

Call B
Risk 97
Confidence 54
→ review because uncertainty is high

Call C
Risk 73
Confidence 99
→ lower priority
```

This is more nuanced than a single risk number.

---

# 42. Differentiator #40 — Trend + Evidence Drilldown

When the dashboard says:

```text
ATM balance mismatch
+278%
```

the manager should immediately be able to do:

```text
Trend
 ↓
Cluster
 ↓
38 calls
 ↓
Top contributing agents
 ↓
Top timestamps
 ↓
Representative evidence
```

This creates a continuous drill-down path:

```text
WHAT
 ↓
HOW BIG
 ↓
WHY
 ↓
WHICH CALLS
 ↓
WHICH EVIDENCE
```

---

# 43. The 5 Features Most Likely to Impress Judges

If implementation time is limited, prioritize these:

## 1. Evidence Graph

The strongest match to the challenge requirement.

## 2. Resolution Reality Check

Agent says resolved vs customer says unresolved.

## 3. Manager Attention Explainability

Not just 92/100 — show exactly why.

## 4. Conversation Journey + Audio Bookmarks

A manager understands a long call quickly.

## 5. Emerging Issue Radar

Move from individual-call analytics to operational intelligence.

---

# 44. The Strongest Overall Product Flow

The demo should follow this exact story:

```text
1,441 CALLS
      ↓
RADAR
      ↓
"19 critical calls today"
      ↓
OPEN CRITICAL CALL
      ↓
Attention = 92
      ↓
WHY?
      ↓
Unresolved
Mood collapse
Repetition
Resolution contradiction
      ↓
CLICK MOOD SHIFT
      ↓
03:42
      ↓
Audio jumps
      ↓
"I've already explained this three times."
      ↓
CLICK RESOLUTION CONTRADICTION
      ↓
Agent: "That should be resolved."
Customer: "No, it still doesn't work."
      ↓
GO TO CUSTOMER HISTORY
      ↓
3 calls in 9 days
      ↓
GO TO ISSUE RADAR
      ↓
Card-decline complaints +42%
      ↓
CONCLUSION
      ↓
Individual problem + customer friction
+ possible systemic process issue
```

The evaluator sees one connected story.

---

# 45. Signature UX: "Why?"

The entire interface should revolve around one interaction.

```text
                    [ WHY? ]

Intent               → evidence
Mood                 → evidence
Mood Shift           → evidence
Resolution           → evidence
Attention Score      → evidence
Repeat Complaint     → evidence
Emerging Issue       → evidence
```

This consistency makes the product easy to understand.

---

# 46. Recommended Dashboard

```text
┌──────────────────────────────────────────────────────┐
│ CALL-CENTRE RADAR                                    │
├──────────────────────────────────────────────────────┤
│ 1,441 CALLS   127 ATTENTION   19 CRITICAL            │
│                                                      │
│ EVIDENCE COVERAGE: 94%                               │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 🚨 MANAGER ATTENTION                                 │
│                                                      │
│ 96  John    Card Declined      Unresolved            │
│ 92  Sarah   Transfer Failed    Mood Collapse         │
│ 89  Mike    Fraud              Escalation            │
│                                                      │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 🔥 EMERGING ISSUES                                   │
│                                                      │
│ ATM mismatch                 +278%                    │
│ Card decline                +84%                     │
│ Refund delay                +61%                     │
│                                                      │
├──────────────────────────────────────────────────────┤
│                                                      │
│ CUSTOMER FRICTION                                    │
│                                                      │
│ Repeat explanations          143                     │
│ Resolution contradictions     27                     │
│ High effort calls             91                     │
│                                                      │
└──────────────────────────────────────────────────────┘
```

The dashboard should be a **radar**, not a spreadsheet.

---

# 47. Recommended Call Detail

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CALL RADAR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ATTENTION SCORE                         92 / 100
██████████████████░░

WHY?
✓ Unresolved
✓ Strong negative mood
✓ 3 repeated explanations
✓ Resolution contradiction

────────────────────────────────────────────────────

CONVERSATION JOURNEY

00:00        01:14        02:36       03:42       04:58
  ●------------●------------●------------●------------●
 start        intent       repeat      mood↓       outcome

────────────────────────────────────────────────────

MOOD

Positive ─────────────╮
                     ╰──────────────╮
                                    ╰──── 🔴

Mood shift: 03:42

Evidence:
"I've already explained this three times."

[▶ Jump to 03:42]

────────────────────────────────────────────────────

RESOLUTION REALITY CHECK

Agent:
"That should be resolved."

Customer:
"No, it's still failing."

⚠ CONTRADICTION

[▶ Jump to 04:11]

────────────────────────────────────────────────────

CUSTOMER EFFORT

78 / 100 — HIGH

Repeated explanation: 3x
Waits: 2
Resolution confirmation: missing

[WHY?]

────────────────────────────────────────────────────

RECOMMENDED ACTION

Review resolution handling and investigate whether
this customer has a recurring card-decline problem.
```

---

# 48. Backend Architecture for the Differentiators

The backend should contain explicit services:

```text
services/
├── analysis.py
├── evidence.py
├── scoring.py
├── mood.py
├── repetition.py
├── contradictions.py
├── effort.py
├── issue_clusters.py
├── trends.py
├── agent_metrics.py
├── customer_risk.py
├── review_queue.py
└── recommendations.py
```

AI should not be responsible for every feature.

Use:

```text
Rules
+
signal processing
+
classifiers
+
embeddings
+
LLM
```

instead of:

```text
LLM does everything
```

---

# 49. Evidence Data Model

Recommended:

```sql
CREATE TABLE evidence (
    id UUID PRIMARY KEY,
    call_id UUID NOT NULL,
    claim_type TEXT NOT NULL,
    claim_text TEXT NOT NULL,

    segment_id UUID NOT NULL,

    start_time DOUBLE PRECISION NOT NULL,
    end_time DOUBLE PRECISION NOT NULL,

    speaker TEXT NOT NULL,
    transcript_text TEXT NOT NULL,

    quality TEXT NOT NULL,
    confidence DOUBLE PRECISION,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Every manager-facing claim can reference this table.

---

# 50. Claim Data Model

```sql
CREATE TABLE claims (
    id UUID PRIMARY KEY,
    call_id UUID NOT NULL,

    category TEXT NOT NULL,
    label TEXT NOT NULL,

    claim_text TEXT NOT NULL,

    confidence DOUBLE PRECISION,
    status TEXT NOT NULL,

    evidence_coverage DOUBLE PRECISION,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Statuses:

```text
APPROVED
REVIEW
REJECTED
```

---

# 51. Attention Score Model

Store every component.

```json
{
  "score": 92,

  "components": {
    "unresolved": 25,
    "negative_mood": 20,
    "mood_shift": 15,
    "repetition": 10,
    "escalation": 10,
    "repeat_contact": 7,
    "uncertainty": 5
  }
}
```

Do not store only:

```text
score = 92
```

Otherwise debugging and explainability become difficult.

---

# 52. Customer Effort Formula

Initial deterministic model:

```text
effort =
    repetition_score * 0.25
  + wait_score * 0.15
  + interruption_score * 0.10
  + transfer_score * 0.15
  + unresolved_score * 0.20
  + negative_mood_score * 0.15
```

Clamp to:

```text
0..100
```

Store the components so the score remains explainable.

---

# 53. Repeat Complaint Detection

Recommended pipeline:

```text
Customer utterances
      ↓
Select problem-related turns
      ↓
Generate embeddings
      ↓
Similarity matrix
      ↓
Cluster
      ↓
Repeated issue candidates
      ↓
LLM label
```

Use both:

```text
within-call repetition
```

and:

```text
cross-call customer repetition
```

---

# 54. Contradiction Detection

Basic architecture:

```text
Agent outcome statements
         |
         v
Customer outcome statements
         |
         v
Outcome classifier
         |
         v
Compare
         |
    +----+----+
    |         |
 consistent  conflict
                |
                v
       resolution contradiction
```

Example signals:

```text
agent:
"resolved"
"fixed"
"completed"

customer:
"still not working"
"not fixed"
"again"
"same problem"
```

This can be rule-driven first, LLM-assisted second.

---

# 55. Conversation Journey Generation

Use deterministic events wherever possible.

Example:

```text
Greeting:
first meaningful agent segment

Problem identified:
first intent evidence

Repetition:
second semantically similar customer statement

Mood shift:
change-point detection

Escalation:
escalation phrase / risk classifier

Resolution:
customer confirmation or explicit completion

Unresolved end:
conversation ends without positive resolution
```

This makes the journey explainable.

---

# 56. Emerging Issue Ranking

Suggested score:

```text
emerging_score =
    growth_rate * 0.35
  + volume_normalized * 0.20
  + unresolved_rate * 0.25
  + attention_rate * 0.20
```

This avoids ranking an issue solely because it increased from:

```text
1 call → 3 calls
```

while a major issue increased from:

```text
50 → 100
```

---

# 57. Human-in-the-Loop Design

Human review should happen when:

```text
high risk
+
low confidence
```

or:

```text
model disagreement
```

or:

```text
evidence validation failure
```

This creates:

```text
AI automation
+
human verification where needed
```

rather than pretending AI is perfect.

---

# 58. Local-First Implementation

All differentiators should work locally wherever practical.

Suggested components:

```text
ASR:
Faster-Whisper

Sentiment:
local transformer classifier

Embeddings:
Sentence Transformers

Vector storage:
pgvector

LLM:
Ollama / llama.cpp / vLLM

Queue:
Redis + Celery

Database:
PostgreSQL

Object storage:
MinIO

API:
FastAPI

Frontend:
Next.js
```

No feature should require a cloud API unless used as an optional adapter.

---

# 59. What Should NOT Become a Differentiator

Avoid gimmicks such as:

- generic chatbot;
- generic sentiment donut;
- generic word cloud;
- generic "AI score";
- dozens of colorful dashboard cards;
- an LLM-generated paragraph with no evidence;
- cloud-only architecture;
- unnecessary real-time telephony integration;
- custom model training just for novelty.

A smaller system with trustworthy evidence is stronger than a huge system with unverifiable predictions.

---

# 60. Priority Matrix

## P0 — Must Build

```text
Evidence graph
Evidence validation
Why? interaction
Explainable attention score
Mood shift detective
Conversation journey
Audio bookmarks
Resolution reality check
Customer history
Repeat complaint detection
```

## P1 — Strong Winning Features

```text
Evidence coverage score
Customer effort score
Customer repetition index
Emerging issue radar
Agent friction map
Dead-air intelligence
Call reliability score
Model disagreement radar
Manager inbox
Human review queue
```

## P2 — Stretch

```text
Counterfactual score
Natural-language investigation
Ask the Call
Semantic search
Agent coaching
Escalation prediction
Feedback loop
```

---

# 61. Suggested Hackathon Demo

## Scene 1 — Scale

Open dashboard:

```text
1,441 calls
19 critical
127 needing attention
```

## Scene 2 — Find the problem

Click:

```text
#1 Critical Call
```

## Scene 3 — Explain

Show:

```text
92 / 100

Why?
Unresolved
Mood collapse
Repetition
Contradiction
```

## Scene 4 — Prove

Click:

```text
Mood shift — 03:42
```

Audio automatically jumps.

Customer:

> "I've already explained this three times."

## Scene 5 — Surprise

Click:

```text
Resolution Reality Check
```

Agent:

> "That should be resolved."

Customer:

> "No, it still doesn't work."

## Scene 6 — Go beyond one call

Open customer history:

```text
3 similar contacts
9 days
0 confirmed resolutions
```

## Scene 7 — Go beyond one customer

Open issue radar:

```text
Card-decline complaint trend +42%
```

## Scene 8 — End with action

System:

```text
Recommended:
Review customer
Review agent interaction
Investigate card-decline process
```

This demonstrates:

```text
scale
→ detection
→ explanation
→ evidence
→ customer history
→ operational insight
→ action
```

---

# 62. The Winning Differentiation Statement

Use this in the presentation:

> **Call-Centre Radar is an evidence-first conversation intelligence system. Instead of simply summarizing calls, it identifies the moments that matter, validates every important judgment against the transcript, explains why a manager should care, and lets the manager jump directly from insight to audio evidence.**

---

# 63. One-Slide Architecture for Judges

```text
                    1,441 CALLS
                         |
                         v
                  LOCAL ASR
                         |
                         v
              TIMESTAMPED TRANSCRIPT
                         |
              +----------+----------+
              |                     |
              v                     v
       DETERMINISTIC         LOCAL AI MODELS
         SIGNALS                    |
              |              +------+------+
              |              |             |
              |           intent        mood
              |              |             |
              +--------------+-------------+
                             |
                             v
                    EVIDENCE ENGINE
                             |
                    +--------+--------+
                    |                 |
                 APPROVE           REVIEW
                    |                 |
                    v                 v
             TRUSTED INSIGHTS    HUMAN QUEUE
                    |
             +------+------+-------+
             |      |      |       |
             v      v      v       v
          RISK   TRENDS  EFFORT  JOURNEY
             |      |      |       |
             +------+------|-------+
                    |
                    v
              MANAGER ACTION
                    |
                    v
              EXACT AUDIO MOMENT
```

---

# 64. Final Product Principle

The most important idea in this document is:

```text
        AI INSIGHT
            ↓
        "WHY?"
            ↓
        EVIDENCE
            ↓
        TIMESTAMP
            ↓
        EXACT WORDS
            ↓
        AUDIO
            ↓
        MANAGER ACTION
```

This chain should work for:

- intent;
- mood;
- mood shift;
- resolution;
- attention score;
- repeat complaint;
- issue;
- escalation;
- contradiction;
- recommendation.

If this works reliably, the product will feel substantially more mature than a normal speech analytics demo.

---

# 65. Final Feature Checklist

## Core

- [ ] Timestamped transcript
- [ ] Agent/customer
- [ ] Intent
- [ ] Mood
- [ ] Mood shift
- [ ] Resolution
- [ ] <=40-word summary
- [ ] Attention score
- [ ] Evidence
- [ ] Customer history
- [ ] Trends
- [ ] Agent analytics

## Winning Layer

- [ ] Evidence graph
- [ ] Evidence coverage
- [ ] Hallucination firewall
- [ ] Evidence quality levels
- [ ] Conversation journey
- [ ] Mood shift detective
- [ ] Turning points
- [ ] Explainable attention score
- [ ] Counterfactual score
- [ ] Resolution reality check
- [ ] Agent/customer reality gap
- [ ] Customer effort
- [ ] Repetition index
- [ ] Hidden repeat complaint
- [ ] Repeat frustration
- [ ] Emerging issues
- [ ] Issue radar
- [ ] Team failure detection
- [ ] Agent friction map
- [ ] Dead-air intelligence
- [ ] Call reliability
- [ ] Audio quality awareness
- [ ] Audio bookmarks
- [ ] Conversation compression
- [ ] Jump-to-Why
- [ ] Manager inbox
- [ ] Manager feedback
- [ ] Model disagreement
- [ ] Uncertainty dashboard
- [ ] Natural language investigation
- [ ] Ask the Call
- [ ] Claim-to-audio API
- [ ] Evidence-backed summaries
- [ ] Complaint-to-root-cause ladder
- [ ] Recommended next action
- [ ] Human review routing

---

# 66. Final Recommendation

Do not attempt to build every feature in this document.

For the strongest hackathon submission, build this core combination extremely well:

```text
1. Evidence Graph
2. Hallucination Firewall
3. Explainable Attention Score
4. Mood Shift Detective
5. Conversation Journey
6. Resolution Reality Check
7. Customer Repetition + Effort
8. Emerging Issue Radar
9. Audio Bookmarks / Jump-to-Why
10. Manager Review Queue
```

The resulting story is simple:

> **Find the risky call → explain why → prove it → jump to the exact moment → reveal whether it is an isolated call or a larger operational problem → give the manager a next action.**

That is the product experience the team should optimize for.
