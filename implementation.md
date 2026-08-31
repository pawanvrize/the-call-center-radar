# Call-Centre Radar — Detailed Local-First Implementation Plan

## 0. Purpose

This document is the implementation blueprint for the **Call-Centre Radar** hackathon project.

The target is not a generic speech-to-text demo. The system should take the supplied recorded support calls, reconstruct the conversation, extract actionable call intelligence, and expose that intelligence through a production-style backend API and dashboard.

The challenge requires:

- audio recordings as the source of truth;
- speaker-aware, timestamped transcripts;
- customer intent;
- customer mood and the point where mood shifts;
- resolution status;
- a summary of no more than 40 words;
- a ranked `needs manager attention` score;
- evidence for every judgment in the form of a timestamp and the words spoken at that moment;
- customer history;
- call-level views;
- cross-call issue trends;
- per-agent volume, handle-time and outcome analytics;
- an API and dashboard;
- preprocessing that happens before requests, rather than re-transcribing on every API request.

The supplied challenge data contains 1,441 banking support calls. The recordings are telephone-quality 8 kHz MP3 files, metadata is supplied separately, and each recording has two channels: **left = agent, right = customer**.

---

# 1. Research Basis: Existing Projects to Learn From

The architecture below deliberately combines the strongest practical ideas found across the following repositories.

## 1.1 SpeechBrain Call Center Analytics

Repository:
https://github.com/backblaze-b2-samples/speechbrain-call-center-analytics

Important ideas worth adopting:

- local/on-device processing;
- VAD → ASR → speaker handling → emotion/sentiment;
- one source recording producing separate derived artifacts;
- timestamped `transcript.jsonl`;
- per-call `analytics.json`;
- call library;
- call detail page with transcript + audio;
- FastAPI backend;
- `/health` and `/metrics`;
- polling and caching;
- structural backend tests;
- model caching;
- CPU/GPU device detection;
- avoiding a mandatory gated diarization model by using SpeechBrain speaker embeddings + clustering.

The repository explicitly describes a local pipeline using VAD, ASR, speaker embeddings/diarization and per-segment emotion, with timestamped speaker-labeled transcript artifacts. It also provides a layered FastAPI API and dashboard structure.

**Use for our project:** pipeline organization, artifact format, API layering, model caching, health/metrics, and local-first processing.

License reported by the repository: MIT.

Source:
https://github.com/backblaze-b2-samples/speechbrain-call-center-analytics

---

## 1.2 Amazon Transcribe Post Call Analytics

Repository:
https://github.com/aws-samples/amazon-transcribe-post-call-analytics

Important ideas:

- post-call processing as a workflow;
- asynchronous ingestion;
- durable derived analysis;
- sentiment trends;
- talk/non-talk time;
- configurable phrase/compliance detection;
- issue detection;
- entity detection;
- interruptions;
- searchable transcripts;
- batch processing;
- archive processing without blocking new calls;
- retention strategy;
- call metadata indexed separately from large artifacts;
- separation between processing pipeline and dashboard reads.

The AWS sample uses an event-driven flow around ingestion, workflow processing, durable JSON results, metadata indexing, and a call-detail UI.

**Use for our project:** asynchronous architecture, job state management, analytics schema, search, evidence artifacts, and operational robustness.

We will reproduce these concepts locally with open-source components rather than AWS managed services.

The repository currently reports an Apache-2.0 license.

Source:
https://github.com/aws-samples/amazon-transcribe-post-call-analytics

---

## 1.3 AWS Conversation Intelligence using AI/ML

Repository:
https://github.com/aws-samples/conversation-intelligence-using-aiml-on-aws

Important ideas:

- modular AI pipeline;
- diarization before transcription;
- speaker-based audio splitting;
- Faster-Whisper;
- sentiment and entity analysis;
- generative analysis after transcription;
- configurable prompts for quality/compliance;
- conversation list → call detail → workflow administration;
- support for open-source/custom models.

This is especially useful for the model-provider abstraction: transcription, NLP analysis, and business rules should be replaceable modules.

**Use for our project:** modular AI services, Faster-Whisper direction, configurable prompts/rules, and clean separation between speech processing and generative analysis.

Source:
https://github.com/aws-samples/conversation-intelligence-using-aiml-on-aws

---

## 1.4 CustomerSupportHelper

Repository:
https://github.com/Gosho69/CustomerSupportHelper

Important ideas:

- asynchronous call analysis;
- Celery + Redis;
- PostgreSQL-backed call records;
- Dockerized local deployment;
- WhisperX;
- diarization;
- emotion + sentiment;
- emotional journey;
- silence and response-time metrics;
- interruptions;
- WPM;
- topic tracking;
- CSAT prediction;
- agent performance reports;
- role-based access;
- structured APIs.

The repo describes a multi-stage AI pipeline and runs the analysis asynchronously in workers. It also preloads expensive AI models to avoid a cold-start cost on each call.

**Use for our project:** queue-based processing, PostgreSQL persistence, worker process, emotional timeline, behavioral metrics, performance aggregation, and preloading/caching expensive models.

The repository's documented local setup uses Docker Compose, PostgreSQL, Redis, Celery and Hugging Face models.

Source:
https://github.com/Gosho69/CustomerSupportHelper

**Important:** before copying any source code or assets, verify the repository's current license and the licenses of every model it uses. This blueprint uses the architecture/ideas, not a copy of implementation.

---

## 1.5 InsightX Conversation Intelligence

Repository:
https://github.com/AbhijithPM507/insightx-conversation-intelligence

Important ideas:

- FastAPI + React;
- structured JSON output;
- domain rule engine;
- risk/impact engine;
- deterministic post-processing;
- compliance/risk scoring;
- escalation probability;
- agent performance;
- explainable output;
- a unified response schema.

This is the most useful inspiration for the **evidence-first backend contract**.

**Use for our project:** structured schemas, deterministic validation after model output, configurable banking-domain rules, risk scoring, and explainability.

The repository currently reports an MIT license.

Source:
https://github.com/AbhijithPM507/insightx-conversation-intelligence

---

## 1.6 Callytics

Repository:
https://github.com/bunyaminergen/Callytics

Important ideas:

- speech preprocessing;
- VAD;
- diarization;
- forced alignment;
- sentiment analysis;
- conflict detection;
- topic detection;
- profanity detection;
- transcript/topic tables;
- SQLite/PostgreSQL-style persistence;
- separate audio and text processing modules.

**Use for our project:** audio preprocessing, quality checks, alignment concepts, topic modeling, conflict/negative-language detection and simple database organization.

The repository reports GPL-3.0.

**Recommendation:** use this as technical inspiration, but do not copy GPL-licensed code into a permissively licensed hackathon implementation unless the team explicitly chooses to comply with the GPL obligations.

Source:
https://github.com/bunyaminergen/Callytics

---

# 2. Core Design Decision: Exploit the Supplied Stereo Channels

This is one of the highest-value implementation decisions.

The challenge states that each recording has:

- left channel = agent;
- right channel = customer.

Therefore, for the supplied dataset, **generic speaker diarization is not the first-choice path**.

Instead:

```text
Stereo MP3
   |
   +---- Left channel  ----> Agent audio ----> ASR
   |
   +---- Right channel ----> Customer audio -> ASR
```

Then merge both transcripts by timestamp.

### Why this is better

It avoids:

- unnecessary diarization errors;
- ambiguity between agent/customer;
- additional GPU/CPU model cost;
- speaker-clustering failure on short utterances;
- speaker-label correction logic.

The final system can still support a mono fallback:

```text
if stereo:
    use channel identity
else:
    VAD -> speaker embeddings -> clustering/diarization
```

This means our system is robust for both the hackathon data and future recordings.

---

# 3. Proposed Product Architecture

## 3.1 High-Level

```text
                         ┌───────────────────────┐
                         │   1,441 MP3 Calls     │
                         │  + metadata JSON      │
                         └──────────┬────────────┘
                                    |
                                    v
                         ┌───────────────────────┐
                         │    Ingestion API      │
                         │ validation + metadata │
                         └──────────┬────────────┘
                                    |
                                    v
                         ┌───────────────────────┐
                         │    Job Queue          │
                         │ Redis + Celery        │
                         └──────────┬────────────┘
                                    |
                 ┌──────────────────┼──────────────────┐
                 |                  |                  |
                 v                  v                  v
        Audio Preprocessor       ASR Worker      Metadata Worker
                 |
                 v
       Channel-aware transcript
                 |
                 v
       ┌─────────────────────┐
       │ Analysis Orchestrator│
       └─────────┬───────────┘
                 |
       ┌─────────┼────────────────────────────┐
       |         |            |               |
       v         v            v               v
     Intent    Mood       Resolution      Summary
       |         |            |               |
       └─────────┼────────────┼───────────────┘
                 v
       ┌─────────────────────┐
       │ Evidence Validator  │
       │ Rule + confidence   │
       └─────────┬───────────┘
                 |
                 v
       ┌─────────────────────┐
       │ Attention Scoring   │
       │ + Trends + Metrics  │
       └─────────┬───────────┘
                 |
        ┌────────┴─────────┐
        v                  v
   PostgreSQL          Object Storage
   metadata/results    audio/artifacts
        |                  |
        └────────┬─────────┘
                 v
              FastAPI
                 |
        ┌────────┴─────────┐
        v                  v
   Dashboard UI       API consumers
```

---

# 4. Recommended Tech Stack

## Backend

- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Redis
- Celery
- Uvicorn/Gunicorn
- FFmpeg
- NumPy
- librosa/soundfile
- scikit-learn
- PyTorch

## Speech

### Primary

- Faster-Whisper for local ASR
- VAD before transcription when useful
- channel-aware transcription for stereo calls

### Fallback

- SpeechBrain VAD;
- SpeechBrain ECAPA speaker embeddings + clustering for mono calls;
- optional WhisperX/pyannote adapter for environments where their model/license requirements are acceptable.

## NLP / Intelligence

Provider abstraction:

```text
Local LLM provider
       |
       +---- Ollama
       |
       +---- vLLM
       |
       +---- llama.cpp
       |
       +---- optional remote provider
```

Use a local instruction-tuned model for:

- intent;
- resolution;
- summary;
- evidence selection;
- issue classification;
- manager rationale.

The application must not depend on one LLM vendor.

## Database

PostgreSQL for:

- customers;
- agents;
- calls;
- transcripts;
- segments;
- analysis;
- evidence;
- jobs;
- aggregated metrics.

## Object storage

MinIO locally.

Store:

```text
calls/{date}/{call_id}/
    source.mp3
    normalized.wav
    agent.wav
    customer.wav
    transcript.json
    analytics.json
    analysis.json
```

This mirrors the useful artifact fan-out concept from the SpeechBrain/AWS solutions while remaining completely local.

## Frontend

- Next.js
- React
- Tailwind
- shadcn/ui
- Recharts
- TanStack Query

---

# 5. Repository Structure

```text
call-centre-radar/
│
├── apps/
│   ├── api/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── dependencies.py
│   │   │   │
│   │   │   ├── api/
│   │   │   │   ├── calls.py
│   │   │   │   ├── customers.py
│   │   │   │   ├── agents.py
│   │   │   │   ├── dashboard.py
│   │   │   │   ├── trends.py
│   │   │   │   ├── search.py
│   │   │   │   └── health.py
│   │   │   │
│   │   │   ├── db/
│   │   │   │   ├── session.py
│   │   │   │   ├── models/
│   │   │   │   └── repositories/
│   │   │   │
│   │   │   ├── schemas/
│   │   │   ├── services/
│   │   │   │   ├── ingestion.py
│   │   │   │   ├── processing.py
│   │   │   │   ├── transcript.py
│   │   │   │   ├── analysis.py
│   │   │   │   ├── evidence.py
│   │   │   │   ├── scoring.py
│   │   │   │   ├── trends.py
│   │   │   │   └── metrics.py
│   │   │   │
│   │   │   ├── ai/
│   │   │   │   ├── asr/
│   │   │   │   ├── diarization/
│   │   │   │   ├── sentiment/
│   │   │   │   ├── llm/
│   │   │   │   └── prompts/
│   │   │   │
│   │   │   ├── workers/
│   │   │   │   ├── celery_app.py
│   │   │   │   └── tasks.py
│   │   │   │
│   │   │   └── utils/
│   │   │
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── web/
│       ├── app/
│       ├── components/
│       ├── lib/
│       ├── hooks/
│       └── types/
│
├── pipelines/
│   ├── ingest/
│   ├── audio/
│   ├── transcription/
│   ├── diarization/
│   ├── analysis/
│   └── aggregation/
│
├── storage/
│   ├── raw/
│   ├── normalized/
│   ├── transcripts/
│   └── analytics/
│
├── migrations/
├── scripts/
│   ├── bootstrap.py
│   ├── import_dataset.py
│   ├── process_all.py
│   └── rebuild_metrics.py
│
├── docker-compose.yml
├── .env.example
├── Makefile
├── README.md
└── implementation.md
```

---

# 6. Data Model

## 6.1 customers

```sql
CREATE TABLE customers (
    id UUID PRIMARY KEY,
    external_id TEXT UNIQUE,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## 6.2 agents

```sql
CREATE TABLE agents (
    id UUID PRIMARY KEY,
    external_id TEXT UNIQUE,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## 6.3 calls

```sql
CREATE TABLE calls (
    id UUID PRIMARY KEY,
    external_call_id TEXT UNIQUE NOT NULL,

    customer_id UUID NOT NULL REFERENCES customers(id),
    agent_id UUID REFERENCES agents(id),

    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,

    audio_uri TEXT NOT NULL,
    metadata_uri TEXT,

    status TEXT NOT NULL,
    processing_error TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Recommended status values:

```text
INGESTED
QUEUED
PREPROCESSING
TRANSCRIBING
ANALYZING
VALIDATING
COMPLETED
FAILED
```

---

# 7. Transcript Schema

Use one canonical transcript format.

```json
{
  "call_id": "abc123",
  "language": "en",
  "duration_seconds": 318.4,
  "segments": [
    {
      "id": 1,
      "start": 0.31,
      "end": 4.82,
      "speaker": "customer",
      "text": "My card was declined again.",
      "emotion": "frustrated",
      "sentiment": -0.72,
      "words": [
        {
          "start": 0.31,
          "end": 0.55,
          "text": "My"
        }
      ]
    }
  ]
}
```

Store the **word timestamps whenever the ASR engine supports them**.

This makes evidence navigation much more reliable.

---

# 8. Audio Pipeline

## Stage 1 — Validate

Check:

- file exists;
- supported extension;
- decodable by FFmpeg;
- duration > 0;
- expected number of channels;
- sample rate;
- corrupted-file detection.

Record:

```text
duration
sample_rate
channels
codec
bitrate
file_size
checksum
```

## Stage 2 — Normalize

Convert to a canonical WAV representation for model processing:

```text
PCM
mono per processing channel
16 kHz or model-required rate
float32/int16 as required
```

Do not replace the original recording.

## Stage 3 — Split channels

For stereo input:

```text
input.mp3
   |
   +---- agent.wav
   +---- customer.wav
```

Maintain timestamps relative to the original call.

---

# 9. Transcription Strategy

## Recommended approach

Run Faster-Whisper against each logical speaker channel independently.

```python
agent_segments = transcribe(agent_audio)
customer_segments = transcribe(customer_audio)
merged = merge_by_timestamp(agent_segments, customer_segments)
```

Each output segment should contain:

```text
start
end
speaker
text
confidence
word timestamps
```

## Why two-pass/channel transcription

For this challenge:

- channel assignment is deterministic;
- no speaker clustering is required;
- agent/customer labels become trustworthy;
- evidence selection becomes easier;
- computation is lower;
- debugging is much easier.

---

# 10. Mono-Audio Fallback

For future calls where only one channel exists:

```text
audio
 ↓
VAD
 ↓
speaker embeddings
 ↓
clustering
 ↓
speaker_0 / speaker_1
 ↓
role assignment
```

Role assignment can use:

1. known metadata;
2. first-speaker/interaction heuristics;
3. lexical agent phrases;
4. optional LLM classification.

Do not make mono diarization part of the critical path for the supplied dataset.

---

# 11. Transcript Merge Algorithm

Inputs:

```text
Agent:
00.2 - 01.5
02.0 - 04.1

Customer:
01.2 - 02.2
04.0 - 05.0
```

Sort all segments by:

```text
start_time
```

Then apply:

- stable tie-breaker by speaker;
- overlap detection;
- tiny-gap tolerance;
- segment normalization.

Result:

```text
00.2 Agent
01.2 Customer
02.0 Agent
04.0 Customer
```

Do not merge speakers into one text paragraph. Turn-level granularity is essential for evidence.

---

# 12. Analysis Architecture

The intelligence layer should be **hybrid**, not "LLM does everything".

```text
Transcript
    |
    +--------------------------+
    |                          |
    v                          v
Deterministic analytics     LLM analysis
    |                          |
    |                          |
    +------------+-------------+
                 |
                 v
         Evidence validation
                 |
                 v
         Final call analysis
```

---

# 13. Deterministic Analytics

Compute these without an LLM:

## Call duration

```text
ended_at - started_at
```

## Agent talk time

```text
sum(agent_segment_duration)
```

## Customer talk time

```text
sum(customer_segment_duration)
```

## Talk ratio

```text
agent_talk / total_talk
customer_talk / total_talk
```

## Silence

Find gaps between consecutive segments.

Store:

```text
total_silence_seconds
max_silence_seconds
silence_ratio
```

## Interruptions

When segment intervals overlap or a new speaker starts before the previous turn ends, record an interruption candidate.

## Response time

For each customer turn followed by an agent response:

```text
agent_start - customer_end
```

## Words per minute

```text
word_count / speaking_minutes
```

These metrics are cheap, reproducible and useful for agent performance.

---

# 14. Mood / Sentiment

Use two signals.

## 14.1 Per-turn sentiment

Run a local classifier on each transcript turn.

Store:

```json
{
  "label": "negative",
  "score": 0.88
}
```

## 14.2 Call mood timeline

Bucket turns into intervals, for example 10–20 seconds.

Calculate:

```text
bucket_sentiment =
weighted average of turn scores
```

Use weights based on:

- duration;
- model confidence;
- optionally customer-only weighting for customer mood.

---

# 15. Detecting the Mood Shift

The challenge specifically asks for the **point where mood shifted**.

Do not ask the LLM to invent the timestamp.

Instead:

### Step 1

Calculate a timeline:

```text
t=0    +0.40
t=20   +0.20
t=40   -0.05
t=60   -0.45
t=80   -0.70
```

### Step 2

Find a significant slope/change point.

Possible method:

```text
delta = current_bucket - previous_bucket
```

Flag a shift when:

```text
delta <= -threshold
```

and require persistence across subsequent buckets.

### Step 3

Map the shift to the nearest customer turn.

```text
mood_shift_time = 64.8
evidence_segment_id = 23
```

The LLM may explain why the shift happened, but the timestamp must come from transcript data.

---

# 16. Intent Detection

Create a controlled banking intent taxonomy.

Example:

```text
CARD_DECLINED
CARD_LOST_STOLEN
ATM_CASH_NOT_RECEIVED
ATM_CARD_RETAINED
TRANSFER_FAILED
TRANSFER_PENDING
PAYMENT_REVERSED
PAYMENT_NOT_RECOGNIZED
FRAUD_SUSPICION
ACCOUNT_ACCESS
PASSWORD_RESET
FEE_OR_CHARGE
REFUND_STATUS
BALANCE_QUERY
ACCOUNT_CLOSURE
GENERAL_SUPPORT
OTHER
```

The exact taxonomy should be configurable.

LLM output:

```json
{
  "label": "CARD_DECLINED",
  "confidence": 0.94,
  "evidence_segment_ids": [8, 10]
}
```

Never persist only a raw prose answer.

---

# 17. Resolution Detection

Use a three-state model:

```text
RESOLVED
PARTIALLY_RESOLVED
UNRESOLVED
```

Optional confidence:

```json
{
  "status": "RESOLVED",
  "confidence": 0.92,
  "evidence_segment_ids": [41]
}
```

### Resolution signals

Positive:

- problem fixed;
- customer confirms;
- agent confirms completion;
- replacement/order/refund completed.

Negative:

- customer still reports problem;
- agent says follow-up is required;
- customer requests escalation;
- interaction ends without clear closure;
- unresolved callback promised.

Use both deterministic phrase rules and LLM reasoning.

---

# 18. Summary

The summary must be <= 40 words.

Enforce this programmatically:

```python
if word_count(summary) > 40:
    regenerate_or_trim()
```

LLM schema:

```json
{
  "summary": "Customer's card was repeatedly declined; agent verified the account, explained the decline and initiated a replacement."
}
```

The API should expose a character/word count for debugging.

---

# 19. Evidence-First Design

This is the most important differentiator.

Every AI claim must reference one or more transcript segments.

Canonical structure:

```json
{
  "claim_type": "intent",
  "claim": "Customer's card payment was declined.",
  "evidence": [
    {
      "segment_id": 12,
      "start": 87.42,
      "end": 91.04,
      "speaker": "customer",
      "text": "My card was declined again."
    }
  ],
  "confidence": 0.94
}
```

The system should never accept:

```json
{
  "intent": "CARD_DECLINED"
}
```

without evidence.

---

# 20. Evidence Validator

The validator checks:

### Rule 1 — timestamp exists

```text
start >= 0
end > start
end <= call_duration
```

### Rule 2 — segment exists

`segment_id` must belong to this call.

### Rule 3 — evidence text matches source

The stored evidence text must be identical to the transcript segment or a known normalized form.

### Rule 4 — semantic support

For high-value claims, run a lightweight entailment check or deterministic keyword/rule validation.

Example:

Claim:

```text
Customer threatened to close account.
```

Evidence:

```text
"If this isn't fixed, I'll close my account."
```

Valid.

But:

```text
"I need this fixed."
```

should not independently support the closure-threat claim.

### Rule 5 — unsupported claims are rejected

If evidence validation fails:

```text
claim.status = NEEDS_REVIEW
```

and the attention score should increase.

---

# 21. Manager Attention Score

Use a deterministic score from 0–100.

Suggested components:

```text
resolution risk             0-25
customer negative mood      0-20
mood deterioration          0-15
fraud/security indicators   0-15
explicit escalation         0-10
repeat contact indicator    0-10
evidence/model uncertainty   0-5
----------------------------------
TOTAL                      100
```

Example:

```python
score = (
    resolution_risk +
    mood_risk +
    mood_shift_risk +
    security_risk +
    escalation_risk +
    repeat_contact_risk +
    uncertainty_risk
)
```

Then map:

```text
0-29   LOW
30-59  MEDIUM
60-79  HIGH
80-100 CRITICAL
```

Important:

**The score must be explainable.**

Return:

```json
{
  "score": 87,
  "priority": "CRITICAL",
  "reasons": [
    "Customer mood deteriorated sharply",
    "Issue remained unresolved",
    "Customer requested escalation"
  ]
}
```

Each reason should itself have evidence.

---

# 22. Example Attention Record

```json
{
  "call_id": "call-001",
  "score": 92,
  "priority": "CRITICAL",
  "reasons": [
    {
      "type": "unresolved",
      "reason": "Issue was not resolved during the call.",
      "evidence": {
        "timestamp": 301.7,
        "speaker": "customer",
        "text": "So I still cannot use my card."
      }
    },
    {
      "type": "mood_shift",
      "reason": "Customer became strongly frustrated.",
      "evidence": {
        "timestamp": 244.9,
        "speaker": "customer",
        "text": "I've told you this three times already."
      }
    }
  ]
}
```

---

# 23. Topic / Issue Trends Across Calls

This should be implemented in two layers.

## Layer 1 — Controlled intent aggregation

Group calls by intent:

```text
CARD_DECLINED    143
TRANSFER_FAILED   92
FRAUD              61
...
```

## Layer 2 — Emerging issues

For less structured issues:

1. create embeddings for customer problem statements;
2. cluster similar statements;
3. label clusters using a local LLM;
4. compare counts by time window.

Example:

```text
Trending issue: "Cash withdrawal reversed"

This week:     38
Last week:     17
Change:       +124%
```

The dashboard should allow drilling from trend → calls → evidence.

---

# 24. Trend Data Model

```sql
CREATE TABLE issue_clusters (
    id UUID PRIMARY KEY,
    label TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE call_issue_clusters (
    call_id UUID REFERENCES calls(id),
    cluster_id UUID REFERENCES issue_clusters(id),
    confidence FLOAT,
    PRIMARY KEY (call_id, cluster_id)
);
```

Daily aggregate table:

```sql
CREATE TABLE issue_daily_metrics (
    issue_id UUID REFERENCES issue_clusters(id),
    metric_date DATE NOT NULL,
    call_count INTEGER NOT NULL,
    unresolved_count INTEGER NOT NULL,
    negative_count INTEGER NOT NULL,
    avg_attention_score FLOAT NOT NULL,
    PRIMARY KEY (issue_id, metric_date)
);
```

---

# 25. Agent Analytics

Required:

- call volume;
- average handle time;
- outcomes.

Recommended additional metrics:

- average customer sentiment;
- unresolved rate;
- escalation rate;
- customer talk ratio;
- average response time;
- interruptions;
- silence ratio;
- average attention score;
- compliance flags.

Agent aggregate endpoint:

```json
{
  "agent_id": "a1",
  "agent_name": "Agent A",
  "calls": 182,
  "avg_handle_time": 311.4,
  "resolved_rate": 0.84,
  "escalation_rate": 0.07,
  "avg_customer_sentiment": -0.11,
  "avg_attention_score": 31
}
```

---

# 26. Customer History

Customer page:

```text
Customer
Name
Total calls
Open/unresolved issues
Last contact

Call history
------------------------------------------------
Date     Agent     Intent          Outcome
------------------------------------------------
Aug 22   A12       Card declined   Resolved
Aug 27   A07       Card declined   Unresolved
Aug 30   A07       Card declined   Unresolved
```

This makes repeated-contact patterns visible.

---

# 27. Backend API

## Health

```http
GET /health
```

Response:

```json
{
  "status": "ok",
  "database": "ok",
  "redis": "ok",
  "object_store": "ok",
  "workers": "ok"
}
```

---

## Upload call

```http
POST /api/v1/calls
Content-Type: multipart/form-data
```

Inputs:

```text
audio
metadata
```

Return immediately:

```json
{
  "call_id": "abc",
  "status": "QUEUED"
}
```

Do not process the full call inside the HTTP request.

---

## Job status

```http
GET /api/v1/calls/{call_id}/status
```

```json
{
  "call_id": "abc",
  "status": "TRANSCRIBING",
  "stage": "asr",
  "progress": 45
}
```

---

## Full call

```http
GET /api/v1/calls/{call_id}
```

Return:

- metadata;
- customer;
- agent;
- duration;
- transcript;
- analysis;
- attention score;
- evidence;
- processing information.

---

## Transcript

```http
GET /api/v1/calls/{call_id}/transcript
```

Support:

```text
speaker
start
end
page
page_size
```

---

## Audio streaming

```http
GET /api/v1/calls/{call_id}/audio
```

Must support HTTP Range requests so the browser can jump directly to evidence timestamps.

This is important for a professional call-review experience.

---

## Customer history

```http
GET /api/v1/customers/{customer_id}/calls
```

---

## Manager queue

```http
GET /api/v1/dashboard/attention
```

Parameters:

```text
limit
min_score
agent_id
intent
date_from
date_to
```

Sorted by score descending.

---

## Trends

```http
GET /api/v1/dashboard/trends
```

Parameters:

```text
date_from
date_to
group_by=day|week
```

---

## Agents

```http
GET /api/v1/dashboard/agents
```

Optional filters:

```text
date_from
date_to
agent_id
```

---

## Search

```http
GET /api/v1/search/calls?q=card+declined
```

Search across:

- customer;
- agent;
- intent;
- transcript;
- issue;
- evidence.

---

## Reprocess

```http
POST /api/v1/calls/{call_id}/reprocess
```

Optional:

```text
stage=all|transcription|analysis|aggregation
```

This avoids re-running expensive stages unnecessarily.

---

# 28. Job Orchestration

Use Celery.

Recommended chain:

```text
ingest_call
   |
   v
validate_audio
   |
   v
preprocess_audio
   |
   v
transcribe_call
   |
   v
compute_transcript_metrics
   |
   v
analyze_call
   |
   v
validate_evidence
   |
   v
calculate_attention_score
   |
   v
update_aggregates
```

For analysis subcomponents that do not depend on one another:

```text
                  analyze_call
                       |
         +-------------+-------------+
         |             |             |
      intent         mood        summary
         |             |             |
         +-------------+-------------+
                       |
                 resolution
                       |
                 evidence
```

---

# 29. Idempotency

The pipeline must be safe to retry.

Use:

```text
SHA-256(file)
```

or a stable external call ID.

Do not create a duplicate call if the same source file is submitted twice.

Each processing stage should have a persisted status:

```text
PENDING
RUNNING
COMPLETED
FAILED
```

and a checksum/model-version record.

Example:

```sql
stage_runs(
    id,
    call_id,
    stage_name,
    status,
    model_name,
    model_version,
    input_hash,
    started_at,
    ended_at,
    error
)
```

---

# 30. Model Versioning

Every analysis result should store:

```text
asr_model
asr_model_version
sentiment_model
llm_provider
llm_model
prompt_version
rule_version
```

Example:

```json
{
  "models": {
    "asr": "faster-whisper/<configured-model>",
    "sentiment": "<configured-local-model>",
    "llm": "<configured-local-model>"
  },
  "prompt_version": "v3",
  "rule_version": "v5"
}
```

This makes results reproducible.

---

# 31. Structured LLM Output

Never parse free-form prose if avoidable.

Require JSON:

```json
{
  "intent": {
    "label": "CARD_DECLINED",
    "confidence": 0.94,
    "evidence_segment_ids": [12, 14]
  },
  "resolution": {
    "status": "UNRESOLVED",
    "confidence": 0.91,
    "evidence_segment_ids": [33]
  },
  "mood": {
    "overall": "FRUSTRATED",
    "evidence_segment_ids": [22, 23]
  },
  "summary": "Customer reports repeated card declines; issue remains unresolved after troubleshooting.",
  "manager_reasons": [
    {
      "type": "unresolved",
      "evidence_segment_ids": [33]
    }
  ]
}
```

Validate with Pydantic.

If invalid:

```text
retry -> repair prompt -> reject to review
```

Do not allow malformed model output into the database.

---

# 32. Prompt Design

Prompt should contain:

1. system role;
2. domain taxonomy;
3. transcript;
4. exact output schema;
5. evidence rules;
6. "do not infer unsupported facts";
7. "every claim must cite segment IDs";
8. maximum summary length.

Example rule:

```text
You may only use information explicitly supported by transcript segments.
Every non-trivial judgment MUST cite at least one segment_id.
Do not invent timestamps or quote text that is not present.
If evidence is insufficient, return NEEDS_REVIEW.
```

---

# 33. Evidence Quality Levels

Add:

```text
DIRECT
INFERRED
WEAK
UNSUPPORTED
```

Only:

```text
DIRECT
```

should be eligible as strong evidence for a manager-facing claim.

This can be a useful visual indicator:

```text
Evidence quality: DIRECT
```

---

# 34. PII Handling

Because the domain is banking/customer support, design the system so PII handling is possible.

Local redaction layer:

- phone numbers;
- email addresses;
- card-like numbers;
- account numbers;
- government identifiers.

Store both:

```text
raw transcript
redacted transcript
```

but make redacted data the dashboard default.

Never log:

- full card numbers;
- credentials;
- raw audio paths containing sensitive identifiers;
- API secrets.

---

# 35. Search Design

Minimum viable search:

PostgreSQL full-text search over transcript text.

Later upgrade:

- pgvector embeddings;
- semantic issue search;
- "show calls similar to this problem".

Suggested tables:

```text
transcript_segments
issue_clusters
call_analysis
```

Search result should include:

```json
{
  "call_id": "abc",
  "timestamp": 92.1,
  "speaker": "customer",
  "snippet": "card was declined..."
}
```

Clicking the result should seek audio to `92.1`.

---

# 36. Caching

Cache:

- call list;
- dashboard metrics;
- agent metrics;
- trend aggregates;
- frequently accessed transcript metadata.

Do not cache mutable job state too aggressively.

Recommended frontend:

- TanStack Query;
- polling every few seconds for QUEUED/RUNNING calls;
- invalidate queries on completion.

---

# 37. Database Indexes

At minimum:

```sql
CREATE INDEX idx_calls_customer ON calls(customer_id);
CREATE INDEX idx_calls_agent ON calls(agent_id);
CREATE INDEX idx_calls_status ON calls(status);
CREATE INDEX idx_calls_started_at ON calls(started_at);

CREATE INDEX idx_transcript_call ON transcript_segments(call_id);
CREATE INDEX idx_transcript_speaker ON transcript_segments(speaker);

CREATE INDEX idx_attention_score
ON call_analysis(needs_attention_score DESC);
```

For search:

```sql
GIN index on transcript text
```

For trends:

```text
(date, intent)
(date, agent_id)
```

---

# 38. Analytics Materialization

Do not calculate every dashboard metric from raw transcript rows on every request.

After processing a call:

```text
call completed
    |
    v
update daily agent metrics
    |
    v
update intent metrics
    |
    v
update issue metrics
```

This is the same principle as the AWS post-call architecture: process once, serve many times.

---

# 39. Dashboard Pages

## Page 1 — Executive Radar

Top cards:

```text
Total calls
Needs attention
Unresolved
Negative mood
Trending issue
```

Main section:

```text
Needs Manager Attention
----------------------------------------------
Score   Customer    Issue          Agent
98      John        Fraud          A12
91      Sarah       Card Declined  A07
84      Mike        Transfer       A03
```

---

## Page 2 — Calls

Filters:

```text
date
agent
intent
mood
resolution
attention
```

Table:

```text
Customer
Date
Duration
Intent
Mood
Resolution
Attention
```

---

## Page 3 — Customer

Show:

```text
Customer summary
Call count
Unresolved count
Last contact
```

Then full history.

---

## Page 4 — Call Detail

Layout:

```text
--------------------------------------------------
Call metadata
Agent | Customer | Duration | Outcome | Score
--------------------------------------------------

Audio player
[----------●--------------------]

Mood timeline
+0.8 ─────────────╮
+0.2              ╰───────
-0.5                       ╰─────
     00:00  01:00  02:00  03:00

--------------------------------------------------
Summary
...
--------------------------------------------------

Intent
CARD_DECLINED
Evidence: 01:26

Resolution
UNRESOLVED
Evidence: 04:18

--------------------------------------------------
Transcript

00:10 AGENT    Hello...
00:16 CUSTOMER  My card...
...
```

Clicking a transcript segment should seek audio.

Clicking an evidence timestamp should seek audio.

---

# 40. Evidence UX

For every claim:

```text
INTENT
Card declined

Evidence
02:17
CUSTOMER
"My card was declined again."
[Jump to audio]
```

Do the same for:

- mood shift;
- resolution;
- manager attention reasons;
- issue;
- escalation.

This satisfies the central challenge rule: judgments need auditable support.

---

# 41. Demo Workflow

The demo should be designed around one compelling call.

## Step 1

Open dashboard.

## Step 2

Show:

```text
1,441 calls
```

## Step 3

Show the "Needs Manager Attention" ranking.

## Step 4

Open the highest-scoring call.

## Step 5

Show:

- summary;
- intent;
- unresolved status;
- score;
- mood timeline.

## Step 6

Click "Mood shifted at 03:42".

Audio jumps to:

```text
03:42 CUSTOMER:
"I've already called three times about this."
```

## Step 7

Click "Why needs attention?"

Show all evidence.

## Step 8

Return to Trends.

Show:

```text
Card decline issues +42%
```

## Step 9

Open Agent Analytics.

Show handle time + resolution rates.

This gives the evaluator an end-to-end story rather than individual technical screens.

---

# 42. Local Deployment

Use one command:

```bash
docker compose up --build
```

Services:

```text
api
worker
scheduler
postgres
redis
minio
web
```

Optional:

```text
ollama
```

or:

```text
vllm
```

depending on the local machine.

---

# 43. Docker Compose Layout

Conceptual:

```yaml
services:

  postgres:
    image: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis

  minio:
    image: minio/minio
    volumes:
      - minio_data:/data

  api:
    build: ./apps/api
    depends_on:
      - postgres
      - redis
      - minio

  worker:
    build: ./apps/api
    command: celery -A app.workers.celery_app worker
    depends_on:
      - postgres
      - redis

  scheduler:
    build: ./apps/api
    command: celery -A app.workers.celery_app beat
    depends_on:
      - redis

  web:
    build: ./apps/web
    depends_on:
      - api
```

Do not mount the entire dataset into every container. Give processing workers access only to the required input/artifact paths.

---

# 44. Environment Variables

`.env.example`:

```env
APP_ENV=development

POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=callradar
POSTGRES_USER=callradar
POSTGRES_PASSWORD=change_me

REDIS_URL=redis://redis:6379/0

MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=minio
MINIO_SECRET_KEY=miniosecret
MINIO_BUCKET=callradar

ASR_PROVIDER=faster_whisper
ASR_MODEL=<configured-model>

LLM_PROVIDER=ollama
LLM_MODEL=<configured-model>
OLLAMA_BASE_URL=http://ollama:11434

SENTIMENT_MODEL=<configured-model>

MAX_UPLOAD_MB=500
SUMMARY_MAX_WORDS=40
```

---

# 45. Processing the 1,441 Calls

Do not launch 1,441 transcription processes simultaneously.

Use bounded concurrency.

Example:

```text
ingest metadata
      |
      v
enqueue 1,441 jobs
      |
      v
Celery worker pool
      |
      +-- GPU worker: 1-2 concurrent ASR jobs
      |
      +-- CPU analysis workers
```

The exact concurrency should be benchmarked against the available hardware.

---

# 46. Batch Import

Implement:

```bash
python scripts/import_dataset.py \
    --audio-dir ./callradar-data/audio \
    --metadata-dir ./callradar-data/metadata
```

The importer should:

1. verify matching call IDs;
2. create customers;
3. create agents;
4. create call rows;
5. upload audio to MinIO;
6. queue processing jobs;
7. print progress.

Example:

```text
Imported: 1441
Queued:   1441
Errors:      0
```

---

# 47. Error Handling

Every stage should raise structured exceptions.

Example:

```python
class AudioDecodeError(Exception):
    pass

class TranscriptionError(Exception):
    pass

class AnalysisSchemaError(Exception):
    pass

class EvidenceValidationError(Exception):
    pass
```

Persist errors in:

```text
processing_error
stage_runs.error
```

Failed jobs should be retryable.

---

# 48. Observability

Implement:

```text
/health
/ready
/metrics
```

Metrics:

```text
calls_ingested_total
calls_completed_total
calls_failed_total
processing_duration_seconds
transcription_duration_seconds
analysis_duration_seconds
queue_depth
attention_critical_total
```

Log fields:

```text
call_id
stage
status
duration
model
error
```

Never log transcript/audio content by default.

---

# 49. Testing Strategy

## Unit tests

Test:

- stereo channel split;
- transcript merge;
- talk time;
- silence;
- interruptions;
- response time;
- mood change detection;
- attention score;
- summary word limit;
- evidence validation.

## API tests

Test:

```text
POST /calls
GET /calls/{id}
GET /calls/{id}/transcript
GET /calls/{id}/status
GET /dashboard/attention
GET /dashboard/agents
GET /dashboard/trends
```

## Pipeline tests

Use a short fixture recording.

Expected:

```text
audio -> transcript -> analysis -> evidence -> score
```

## Failure tests

Test:

- corrupted audio;
- missing metadata;
- duplicate call;
- model timeout;
- malformed LLM JSON;
- missing evidence;
- worker restart;
- retry after partial completion.

---

# 50. Evidence Evaluation Tests

Create deliberately incorrect model outputs.

Example:

```json
{
  "intent": "FRAUD",
  "evidence_segment_ids": [4]
}
```

where segment 4 is unrelated.

Expected:

```text
REJECT
```

Another:

```json
{
  "intent": "CARD_DECLINED",
  "evidence_segment_ids": [8]
}
```

where segment 8 says:

```text
"My card was declined."
```

Expected:

```text
ACCEPT
```

This is very important for the hackathon because the brief explicitly says unsupported evidence should not receive credit.

---

# 51. Security

Minimum:

- CORS restricted to frontend;
- upload MIME/type validation;
- file-size limit;
- path traversal protection;
- UUID-based object names;
- signed/internal object-store URLs;
- API rate limiting;
- no secrets in source;
- no raw transcript logging;
- optional authentication;
- PII redaction.

For hackathon demo mode, authentication can be simple but the service boundaries should not assume trusted clients.

---

# 52. Performance Optimizations

## ASR

- use GPU if available;
- use Faster-Whisper;
- cache model weights;
- process channels independently;
- avoid re-transcription;
- persist transcript.

## Analysis

- deterministic metrics first;
- batch local NLP where possible;
- call LLM once per call for structured analysis;
- use small/local model where acceptable;
- cache summaries if input hash is unchanged.

## Database

- bulk inserts;
- indexes;
- materialized aggregates.

## UI

- pagination;
- cached dashboard queries;
- virtualized transcript when necessary;
- audio range requests.

---

# 53. Optional Advanced Features

These should be added only after the required features are stable.

## A. Semantic Search

Use pgvector:

```text
"customers complaining they were charged twice"
```

→ retrieves semantically similar calls.

## B. Similar-Call Detection

On call detail:

```text
Similar calls:
- Call 124
- Call 891
- Call 1022
```

## C. Agent Coaching

Generate:

```text
What went well
What could improve
Evidence
```

## D. Compliance Scorecards

Configurable rules:

```yaml
greeting:
  phrases:
    - "hello"
    - "good morning"

closing:
  phrases:
    - "anything else"
    - "thank you"
```

## E. Repeat-Contact Risk

Customer has several unresolved calls with the same intent.

Increase attention score.

---

# 54. What NOT to Build

To stay focused, do not spend the first phase on:

- real-time call analysis;
- telephony integration;
- video;
- multi-tenant SaaS;
- complex authentication;
- cloud deployment;
- custom deep-learning training;
- custom ASR fine-tuning.

Those are distractions from the actual judging criteria.

---

# 55. Implementation Priority

## P0 — Must Work

1. Dataset importer.
2. Stereo audio processing.
3. Local ASR.
4. Timestamped transcript.
5. Customer/agent mapping.
6. Call-level intent.
7. Mood.
8. Mood shift timestamp.
9. Resolution.
10. <=40-word summary.
11. Evidence objects.
12. Attention score.
13. Customer history.
14. Agent metrics.
15. Trends.
16. FastAPI endpoints.
17. Call-detail dashboard.
18. Audio seek from evidence.
19. Persistent storage.
20. Background processing.

## P1 — Makes It Strong

1. PII redaction.
2. Search.
3. Issue clustering.
4. Retry/reprocess.
5. Metrics endpoint.
6. role-based access.
7. advanced quality scorecards.

## P2 — Stretch

1. Semantic search.
2. coaching suggestions.
3. predicted CSAT.
4. repeat-contact risk.
5. mono diarization fallback.
6. model benchmarking page.

---

# 56. Suggested Development Sequence

## Phase 1 — Backend skeleton

Build:

```text
FastAPI
PostgreSQL
Redis
Celery
MinIO
```

Verify:

```text
docker compose up
GET /health
```

## Phase 2 — Dataset ingestion

Implement:

```text
metadata import
customer/agent creation
call creation
MinIO upload
queueing
```

## Phase 3 — Audio pipeline

Implement:

```text
validate
split stereo
normalize
```

## Phase 4 — ASR

Implement:

```text
Faster-Whisper adapter
timestamped words
channel labels
merged transcript
```

## Phase 5 — Deterministic metrics

Implement:

```text
talk time
silence
response time
interruptions
WPM
```

## Phase 6 — AI analysis

Implement:

```text
intent
mood
resolution
summary
```

## Phase 7 — Evidence

Implement:

```text
evidence schema
validator
claim-level evidence
```

## Phase 8 — Attention engine

Implement:

```text
risk components
0-100 score
reasons
```

## Phase 9 — Aggregations

Implement:

```text
agent metrics
intent counts
issue trends
customer history
```

## Phase 10 — UI

Implement:

```text
dashboard
calls
customer
call detail
agent
trends
```

## Phase 11 — Hardening

Implement:

```text
tests
retry
idempotency
logging
metrics
README
one-command startup
```

---

# 57. Recommended First Version of the Intelligence Pipeline

For a hackathon, this is the best balance of accuracy, explainability and implementation time:

```text
STEREO MP3
   |
   v
Channel split
   |
   v
Faster-Whisper
   |
   v
Timestamped transcript
   |
   +-----------------------+
   |                       |
   v                       v
Rule/ML metrics          Local LLM
   |                       |
   |               intent / resolution /
   |               summary / claim reasons
   |                       |
   +-----------+-----------+
               |
               v
       Evidence Validator
               |
               v
       Attention Scoring
               |
               v
           PostgreSQL
```

This is intentionally simpler than reproducing a complete AWS architecture.

---

# 58. Important Engineering Principle

The AI model should **not** be the system of record.

The system of record should be:

```text
audio
+
timestamped transcript
+
deterministic metrics
+
evidence references
```

The LLM should be a reasoning layer on top.

This gives:

- reproducibility;
- explainability;
- easier debugging;
- lower hallucination risk;
- easier model replacement;
- better judging/demo confidence.

---

# 59. Final Backend Contract

Every completed call should be representable as:

```json
{
  "call_id": "abc123",

  "customer": {
    "id": "cust1",
    "name": "John Smith"
  },

  "agent": {
    "id": "agent1",
    "name": "Agent A"
  },

  "duration_seconds": 318.4,

  "transcript": {
    "segments": []
  },

  "analysis": {
    "intent": {
      "label": "CARD_DECLINED",
      "confidence": 0.94,
      "evidence": []
    },

    "mood": {
      "overall": "FRUSTRATED",
      "shift": {
        "timestamp": 244.9,
        "evidence": []
      }
    },

    "resolution": {
      "status": "UNRESOLVED",
      "confidence": 0.91,
      "evidence": []
    },

    "summary": "Customer's card remains unusable after repeated declines; the issue was not resolved during the call.",

    "attention": {
      "score": 92,
      "priority": "CRITICAL",
      "reasons": []
    }
  },

  "metrics": {
    "agent_talk_seconds": 112.2,
    "customer_talk_seconds": 154.1,
    "silence_seconds": 52.1,
    "interruptions": 3,
    "agent_wpm": 129,
    "customer_wpm": 153
  },

  "processing": {
    "status": "COMPLETED",
    "asr_model": "<configured>",
    "llm_model": "<configured>",
    "prompt_version": "v3",
    "rule_version": "v5"
  }
}
```

---

# 60. Definition of Done

The project is ready for the hackathon demo when:

### Data

- [ ] all supplied metadata is imported;
- [ ] 1,441 calls can be indexed;
- [ ] duplicate ingestion is safe.

### Speech

- [ ] MP3 files decode successfully;
- [ ] stereo channels are mapped to agent/customer;
- [ ] transcripts contain timestamps;
- [ ] transcripts are persisted.

### Intelligence

- [ ] intent exists;
- [ ] mood exists;
- [ ] mood shift timestamp exists when a meaningful shift is detected;
- [ ] resolution exists;
- [ ] summary <= 40 words;
- [ ] every judgment has evidence;
- [ ] unsupported evidence is rejected.

### Analytics

- [ ] attention ranking works;
- [ ] issue trends work;
- [ ] agent volume works;
- [ ] handle time works;
- [ ] outcome metrics work;
- [ ] customer history works.

### API

- [ ] Swagger works;
- [ ] call list works;
- [ ] call detail works;
- [ ] transcript works;
- [ ] audio streaming works;
- [ ] attention endpoint works;
- [ ] trend endpoint works;
- [ ] agent endpoint works;
- [ ] job status works.

### UI

- [ ] dashboard works;
- [ ] calls table works;
- [ ] customer history works;
- [ ] call detail works;
- [ ] mood timeline works;
- [ ] evidence click seeks audio;
- [ ] attention queue works.

### Operations

- [ ] Docker Compose starts the whole stack;
- [ ] health checks work;
- [ ] failed jobs can be retried;
- [ ] README allows a clean-machine setup;
- [ ] no API key is required for the local speech pipeline;
- [ ] local LLM operation is supported.

---

# 61. Recommended Implementation Philosophy

Use the existing repositories as architectural references, not as a codebase to blindly copy.

The strongest combination for this challenge is:

```text
SpeechBrain
    -> local speech processing + artifact organization

AWS PCA
    -> asynchronous workflow + analytics + durable processing

AWS Conversation Intelligence
    -> Faster-Whisper + modular AI pipeline

CustomerSupportHelper
    -> Celery/Redis/PostgreSQL + behavioral analytics

InsightX
    -> deterministic rule engine + explainable structured JSON

Callytics
    -> preprocessing + alignment/topic/conflict ideas

Our key addition
    -> evidence-first judgments + exact audio seek
    -> stereo-channel exploitation for the supplied dataset
```

The resulting product should feel like:

```text
"Every call becomes searchable evidence."
```

rather than:

```text
"An LLM summarized some audio."
```

---

# 62. Source Links

1. SpeechBrain Call Center Analytics  
   https://github.com/backblaze-b2-samples/speechbrain-call-center-analytics

2. Amazon Transcribe Post Call Analytics  
   https://github.com/aws-samples/amazon-transcribe-post-call-analytics

3. AWS Conversation Intelligence using AI/ML  
   https://github.com/aws-samples/conversation-intelligence-using-aiml-on-aws

4. CustomerSupportHelper  
   https://github.com/Gosho69/CustomerSupportHelper

5. InsightX Conversation Intelligence  
   https://github.com/AbhijithPM507/insightx-conversation-intelligence

6. Callytics  
   https://github.com/bunyaminergen/Callytics

---

# 63. Licensing Note

Before importing code, copied UI assets, model weights, prompts, or other artifacts from any third-party repository, verify the repository's current license and the specific license of each dependency/model.

This design intentionally favors:

- original implementation;
- replaceable interfaces;
- local/open tooling;
- inspiration from architecture and publicly documented techniques.

Do not assume that "public GitHub repository" means "free to copy into any project."

