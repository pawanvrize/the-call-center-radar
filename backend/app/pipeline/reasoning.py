"""Grounded reasoning: intent, resolution, and the <=40-word summary.

The central design decision of this whole system lives here: **the model is
never allowed to write a quote.**

The response schema has no `quote` field. The model may only point at a turn by
number; we then look up that turn's verbatim text from our own database. A
fabricated citation is therefore not something we detect and reject after the
fact — it is structurally impossible to express. The worst a bad model can do
is cite the *wrong* turn, which the support check in verifier.py catches.

Provider note: on Groq, only the `openai/gpt-oss-*` models support strict
`json_schema` structured outputs. Every other model falls back to `json_object`
mode, which guarantees syntactically valid JSON but NOT schema adherence — and
schema adherence is the entire mechanism above. Do not swap the model without
checking that list.
"""
import json
import threading
from dataclasses import dataclass

from app.config import settings
from app.pipeline.turns import Turn

MAX_SUMMARY_WORDS = 40

RESOLUTION_VALUES = ("resolved", "unresolved", "partial")

#: Strict-mode requirements: every field required, additionalProperties false.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "What the customer wanted, as a short noun phrase.",
                },
                "turn_id": {
                    "type": "integer",
                    "description": "Number of the turn that best shows this intent.",
                },
            },
            "required": ["label", "turn_id"],
            "additionalProperties": False,
        },
        "resolution": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": list(RESOLUTION_VALUES)},
                "turn_id": {
                    "type": "integer",
                    "description": "Number of the turn that shows the outcome.",
                },
            },
            "required": ["status", "turn_id"],
            "additionalProperties": False,
        },
        "summary": {
            "type": "string",
            "description": f"At most {MAX_SUMMARY_WORDS} words, plain past tense.",
        },
    },
    "required": ["intent", "resolution", "summary"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You analyse customer support calls for a consumer bank.

You will be given a call transcript with every turn numbered. Answer only from
the transcript.

For each judgment you must cite the single turn number that best justifies it.
You cannot write quotes — only turn numbers. The exact words are looked up from
the transcript afterwards, so citing a turn that does not actually support your
claim will be detected.

Rules:
- intent.turn_id must be a turn where the CUSTOMER states what they want.
- resolution.status is "resolved" only if the transcript shows the issue was
  actually settled; "partial" if promised but incomplete; "unresolved" otherwise.
- resolution.turn_id must be the turn showing that outcome.
- summary must be at most 40 words and mention the outcome."""


def loads_tolerant(text: str) -> dict:
    """Parse the first well-formed JSON object in `text`.

    Schema enforcement is supposed to make this unnecessary, and usually does.
    But Bedrock's grammar-constrained decoding for gpt-oss-120b emits a stray
    opening brace before the real object roughly 80% of the time:

        {\\n {"intent": {...}, "resolution": {...}, "summary": "..."}

    The inner object is valid and schema-conformant; only the wrapper is junk.
    Scanning for the first parseable object recovers it without loosening any
    actual validation — `_coerce` still checks every field afterwards. Also
    covers local models that wrap JSON in prose or code fences.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for i, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj:
            return obj

    raise ValueError(f"no JSON object found in model output: {text[:200]!r}")


@dataclass
class Judgment:
    label: str
    turn_index: int


@dataclass
class ReasoningResult:
    intent: Judgment
    resolution: Judgment          # label is the status string
    summary: str
    model: str


def format_transcript(turns: list[Turn]) -> str:
    """Numbered turns. The numbers are the only handle the model gets on the
    text, so they must be stable and match our list indices exactly."""
    lines = []
    for i, turn in enumerate(turns):
        stamp = f"{int(turn.start // 60):02d}:{int(turn.start % 60):02d}"
        lines.append(f"[{i}] {stamp} {turn.speaker}: {turn.text}")
    return "\n".join(lines)


def _clamp_summary(summary: str) -> str:
    words = summary.split()
    if len(words) <= MAX_SUMMARY_WORDS:
        return summary.strip()
    return " ".join(words[:MAX_SUMMARY_WORDS]).rstrip(",;:") + "…"


def _coerce(payload: dict, n_turns: int, model: str) -> ReasoningResult:
    """Validate the model's output against reality before it goes anywhere.

    Schema enforcement guarantees the shape, not the semantics — a turn_id can
    still be out of range. Clamping here means a bad index degrades to a
    citation we can verify and reject, never an IndexError mid-batch.
    """
    def turn_id(node: dict) -> int:
        raw = node.get("turn_id", 0)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return 0
        return max(0, min(value, n_turns - 1))

    intent = payload.get("intent") or {}
    resolution = payload.get("resolution") or {}

    status = str(resolution.get("status", "")).strip().lower()
    if status not in RESOLUTION_VALUES:
        status = "unresolved"

    return ReasoningResult(
        intent=Judgment(
            label=str(intent.get("label", "")).strip() or "unclear",
            turn_index=turn_id(intent),
        ),
        resolution=Judgment(label=status, turn_index=turn_id(resolution)),
        summary=_clamp_summary(str(payload.get("summary", "")).strip()),
        model=model,
    )


def analyze_call(turns: list[Turn]) -> ReasoningResult:
    """Run the reasoning layer for one call, via the configured provider."""
    if not turns:
        raise ValueError("cannot analyze a call with no turns")

    transcript = format_transcript(turns)
    provider = settings.llm_provider

    if provider == "bedrock":
        payload, model = _call_bedrock(transcript)
    elif provider == "azure":
        payload, model = _call_azure(transcript)
    elif provider == "groq":
        payload, model = _call_groq(transcript)
    elif provider == "ollama":
        payload, model = _call_ollama(transcript)
    else:
        raise ValueError(f"unknown llm_provider: {provider!r}")

    return _coerce(payload, len(turns), model)


_BEDROCK_CLIENT = None
_BEDROCK_LOCK = threading.Lock()


def _bedrock_client():
    """One boto3 bedrock-runtime client per process, shared by worker threads.

    Deliberately the Converse API rather than the Anthropic SDK's Bedrock
    client. AWS documents that structured outputs are NOT supported on the
    bedrock-mantle endpoint the Anthropic SDK targets — `output_config.format`
    there returns a 400. Converse is the endpoint that enforces schemas, and it
    is also model-agnostic, so the same code path serves Claude and OpenAI's
    open-weight gpt-oss models with only the model id changing.

    boto3 clients are documented as NOT thread-safe to create but safe to
    share once built, hence the lock around construction only.
    """
    global _BEDROCK_CLIENT
    if _BEDROCK_CLIENT is None:
        with _BEDROCK_LOCK:
            if _BEDROCK_CLIENT is None:
                import boto3
                from botocore.config import Config

                kwargs = {"region_name": settings.aws_region}
                # Explicit keys if given; otherwise fall through to the ambient
                # AWS credential chain (env, ~/.aws/credentials, instance role).
                if settings.aws_access_key_id and settings.aws_secret_access_key:
                    kwargs.update(
                        aws_access_key_id=settings.aws_access_key_id,
                        aws_secret_access_key=settings.aws_secret_access_key,
                    )
                    if settings.aws_session_token:
                        kwargs["aws_session_token"] = settings.aws_session_token

                _BEDROCK_CLIENT = boto3.client(
                    "bedrock-runtime",
                    config=Config(
                        retries={"max_attempts": 6, "mode": "adaptive"},
                        read_timeout=120,
                        max_pool_connections=32,
                    ),
                    **kwargs,
                )
    return _BEDROCK_CLIENT


def _call_bedrock(transcript: str) -> tuple[dict, str]:
    """Bedrock Converse with a compiled JSON-schema grammar.

    Bedrock compiles the schema into a grammar and constrains generation to it,
    so this is enforcement during decoding rather than validation afterwards —
    the same guarantee the design relies on everywhere else.
    """
    client = _bedrock_client()
    response = client.converse(
        modelId=settings.bedrock_model,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": [{"text": transcript}]}],
        inferenceConfig={"maxTokens": 2048, "temperature": 0},
        outputConfig={
            "textFormat": {
                "type": "json_schema",
                "structure": {
                    "jsonSchema": {
                        # NOTE: Converse wants the schema as a JSON *string*,
                        # unlike every other structured-output API. Passing the
                        # dict directly is a 400.
                        "schema": json.dumps(RESPONSE_SCHEMA),
                        "name": "call_analysis",
                        "description": "Intent, resolution and summary with turn citations",
                    }
                },
            }
        },
    )

    # Reasoning models put a `reasoningContent` block FIRST and the answer
    # second, so content[0] is not the answer — scan for the text block.
    # (gpt-oss-120b on Bedrock does exactly this; blindly indexing [0] raises
    # a KeyError that looks like an access problem rather than a parse bug.)
    blocks = response["output"]["message"]["content"]
    text = next((b["text"] for b in blocks if "text" in b), None)
    if text is None:
        kinds = [k for b in blocks for k in b]
        raise RuntimeError(
            f"Bedrock returned no text block for {settings.bedrock_model} "
            f"(saw: {kinds}); stopReason={response.get('stopReason')}"
        )
    return loads_tolerant(text), settings.bedrock_model


def _call_azure(transcript: str) -> tuple[dict, str]:
    """Azure OpenAI. Plain HTTP rather than another SDK — the request body is
    the standard OpenAI shape, so `response_format` is identical to the Groq
    path and the schema is enforced the same way.

    Two Azure-specific things that trip people up:
      * the URL carries the DEPLOYMENT name, not the model name
      * `api-version` must be recent enough for json_schema; older versions
        accept the field and quietly downgrade to unvalidated JSON
    """
    import httpx

    missing = [
        name
        for name, value in (
            ("AZURE_OPENAI_ENDPOINT", settings.azure_openai_endpoint),
            ("AZURE_OPENAI_API_KEY", settings.azure_openai_api_key),
            ("AZURE_OPENAI_DEPLOYMENT", settings.azure_openai_deployment),
        )
        if not value
    ]
    if missing:
        raise ValueError(f"Azure OpenAI is not configured — missing {', '.join(missing)}")

    endpoint = settings.azure_openai_endpoint.rstrip("/")
    url = (
        f"{endpoint}/openai/deployments/{settings.azure_openai_deployment}"
        f"/chat/completions?api-version={settings.azure_openai_api_version}"
    )

    response = httpx.post(
        url,
        headers={"api-key": settings.azure_openai_api_key},
        json={
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "call_analysis",
                    "strict": True,
                    "schema": RESPONSE_SCHEMA,
                },
            },
        },
        timeout=180,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Azure OpenAI {response.status_code}: {response.text[:300]}"
        )

    content = response.json()["choices"][0]["message"]["content"]
    return loads_tolerant(content), f"azure/{settings.azure_openai_deployment}"


def _call_groq(transcript: str) -> tuple[dict, str]:
    from groq import Groq

    if not settings.groq_api_key:
        raise ValueError(
            "GROQ_API_KEY is not set. Set it in .env, or switch to "
            "LLM_PROVIDER=ollama to run the reasoning layer offline."
        )

    # The free tier's ceiling is 8000 tokens/minute, and each call costs ~900,
    # so any useful worker count will overrun it. Rather than hand-tuning a
    # pacer, lean on the SDK's 429 backoff: it honours retry-after, so the
    # batch self-throttles to whatever the account is actually allowed.
    client = Groq(api_key=settings.groq_api_key, max_retries=10)
    completion = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "call_analysis",
                "strict": True,
                "schema": RESPONSE_SCHEMA,
            },
        },
    )
    return loads_tolerant(completion.choices[0].message.content), settings.groq_model


def _call_ollama(transcript: str) -> tuple[dict, str]:
    """Offline fallback. Ollama accepts a JSON schema in `format` directly."""
    from ollama import Client

    client = Client(host=settings.ollama_host)
    response = client.chat(
        model=settings.ollama_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
        format=RESPONSE_SCHEMA,
        options={"temperature": 0},
    )

    # Local models often wrap JSON in prose or fences; the tolerant
    # parser handles that the same way it handles Bedrock's stray brace.
    return loads_tolerant(response["message"]["content"]), settings.ollama_model
