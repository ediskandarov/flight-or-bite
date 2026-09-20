# Jev API notes

Read on **2026-09-19** from the official sources listed at the bottom. Nothing here is inferred:
every statement is marked with its source page, and anything the documentation does not say is
listed under [Not documented](#not-documented). Quoted text is verbatim.

Status: **verified against the live API** through OpenRouter (§1a, §11).

> **Scope after decisions D10–D13 (2026-09-20):** OpenRouter Decisions (§1a) is the project's only
> access path; the model is pinned to `typesafe/jev-1.13`; only client-side `t_wall` is measured.
> §1 (TypeSafe direct, Cloudflare), §5 (server time) and the connect / first-byte findings are
> kept below as a record of what was read, **not** as things the project uses.

## 1a. Third path, the one we use: OpenRouter Decisions (alpha)

Found while reading OpenRouter's docs: "Jev is available on OpenRouter as `typesafe/jev-1.13`
through the Decisions endpoint, so the agent model and the check run on the same API key." [or-cookbook]

| | OpenRouter Decisions |
|---|---|
| Endpoint | `POST https://openrouter.ai/api/alpha/decisions` [or-decisions] |
| Auth | "API key as bearer token in Authorization header" — `OPENROUTER_API_KEY` |
| Body | `{"model": "typesafe/jev-1.13", "state", "questions"}` — same shape as TypeSafe direct; optional `provider` routing preferences |
| Response | TypeSafe's `model` / `answers` / `usage`, plus `id` (generation id), `provider`, `usage.cost` (USD) |
| Response headers | `x-generation-id`, `x-provider-name` (observed live) |
| Errors | 400, 401, 402 (no credits), 403, 404, 413, 429, 500, 502, 503, 524, 529 [or-decisions] |
| Status | **alpha** — may change without notice. `typesafe/jev-1.13` is *not* listed in `GET /api/v1/models` |
| Response cache | OpenRouter's response cache is opt-in and its supported-endpoints list does not include Decisions [or-cache]. `JevClient` still sends `X-OpenRouter-Cache: false` |

Not documented for this path: rate limits specific to Decisions; whether TypeSafe's 1,200 req/min
applies per OpenRouter customer or to OpenRouter as a whole.

## 1. Two further documented access paths (untested)

| | TypeSafe direct | Cloudflare AI |
|---|---|---|
| Endpoint | `POST https://api.typesafe.ai/v1/systemone` | `POST https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/ai/run` |
| Auth | `Authorization: Bearer <API_KEY>` | `Authorization: Bearer $CLOUDFLARE_API_TOKEN` |
| Body | `{"state", "model", "questions"}` | `{"model": "typesafe/jev", "input": {"state", "questions"}}` |
| Model name | `jev-latest`, `jev-preview`, or versioned `jev-1.13.0` | `typesafe/jev` (no version selection documented) |
| Context | 64k total; 32k for `state` + longest question | "32,000 tokens" |
| Rate limits | 250,000 tok/s and 1,200 req/min | not stated on the model page |
| Pricing | $0.042 / Mtok input, output free | "View pricing in the Cloudflare dashboard" |

Sources: [api], [models], [cf].

The response body has the same shape on both paths (`model`, `answers`, `usage`); the Cloudflare
examples report `"model": "jev-1.13.0"`.

**Project choice (M0, reversible):** `JevClient` has two backends, `typesafe` (direct) and
`openrouter` (Decisions). `--backend auto` prefers the direct path when its key exists, because it
removes one intermediary from `t_wall`; today only the OpenRouter key exists. Cloudflare is not
implemented. Consequence for SPEC §6.1: Jev's `t_wall` includes the OpenRouter hop, and the report
must say so.

## 2. Authentication

- Header `Authorization: Bearer <API_KEY>`, plus `Content-Type: application/json`. [api]
- Keys come from the dashboard: https://console.typesafe.ai/keys. [quickstart]
- Access is gated: "Early access" with a waitlist. [blog]
- The vendor's SDKs and examples read the key from **`TYPESAFE_API_KEY`**. [constants] SPEC §4.3
  names `JEV_API_KEY`. `JevClient` reads `JEV_API_KEY` first and falls back to `TYPESAFE_API_KEY`.

## 3. Request

```json
{
  "state": "Help! My payouts have been failing for 3 days.",
  "model": "jev-latest",
  "questions": {
    "department": {
      "type": "choice",
      "instructions": "Which team should handle this?",
      "criteria": {
        "billing": "Payments, invoicing, refunds",
        "technical": "Bugs, outages, integrations",
        "sales": "Pricing, upgrades, new accounts"
      }
    }
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `state` | `string \| object \| array`, required | "A plain string for text, or structured data (object/array)". Text only. [api], [state] |
| `model` | `string`, required | "Use `"jev-latest"`". [api] |
| `questions` | `map<string, Question>`, required | Keys are ours; "The key is not sent to the underlying model and is not used in inference." [api] |

Guidance on `state`: "Use an object for most requests so each part of the state has a descriptive
name and its relationships remain clear." [state]

### Question types

All share `type` and `instructions` (`string | object | array`, required). [api]

| `type` | `criteria` | Returns |
|---|---|---|
| `noul` | optional object with `"true"` / `"false"` descriptions | probability that the answer is yes |
| `choice` | **required** `map<string, string \| null>` — option → rubric; "use null when an option needs no extra detail" | chosen option + full distribution |
| `score` | **required** ordered array, at least two levels | probability-weighted level + distribution |

We use **`choice`** with options `EAT`, `ESCAPE`, `IDLE` (SPEC §4.3).

Cardinality: "Jev supports a cardinality up to 255." [blog] (We need 3.)

Multiple questions per request are supported and evaluated independently against the same state.
[state] We send one.

## 4. Response

```json
{
  "model": "jev-latest",
  "answers": {
    "department": {
      "type": "choice",
      "choice": "technical",
      "probabilities": { "billing": 0.08, "technical": 0.85, "sales": 0.07 },
      "confidence": 0.82
    }
  },
  "usage": { "input_tokens": 312, "output_tokens": 48 }
}
```

| Field | Type | Notes |
|---|---|---|
| `model` | string, required | "The model that performed the evaluation." |
| `answers` | `map<string, Answer>`, required | same ids as in `questions` |
| `usage.input_tokens`, `usage.output_tokens` | integer | |

Choice answer [api]:

| Field | Type | Notes |
|---|---|---|
| `type` | `"choice"` | |
| `choice` | string | "The highest-probability option." |
| `probabilities` | `map<string, number>` | "Every option mapped to its probability (floats that sum to 1)." |
| `confidence` | number, 0..1 | "How certain the model is, derived from probabilities." |

- `choice` is an **argmax**, not a sample. SPEC requires `Decision.action` to be *sampled* from
  `probs`, so the arbiter must sample from `probabilities` itself and ignore `choice`.
- `confidence` is "a statistic computed from the probability distribution"; **the formula is not
  published**. [confidence] The project does not use it; `MockJevClient` fills it with a placeholder.
- Documented example probabilities are rounded (e.g. `0.87 / 0 / 0.13`). Whether live values sum to
  exactly 1 is unverified → the arbiter should renormalise and log the raw sum.
- Exact zeros appear in documented examples (`"sales": 0`). Jensen–Shannon divergence and the
  Brier score are well defined with zeros, so the SPEC §7 metrics need no smoothing; any metric
  added later that takes `log p` directly (KL, log-loss) would need an epsilon rule fixed
  **before** preregistration.

Response headers: `x-typesafe-request-id` — documented in the SDK references ("The
`x-typesafe-request-id` response header, or `None` if absent"). `JevClient` records it. [sdk-responses]

## 5. Server-side processing time — **not provided**

SPEC §4.3 asks explicitly. Neither the HTTP reference, the Cloudflare page and its JSON schemas,
nor the SDK response types document any server timing: no body field, no timing header. A search
of the complete docs export (`llms-full.txt`, 874 KB) for server-timing / processing-time /
latency / duration fields found only `x-typesafe-request-id`, `Retry-After` and `retry-after-ms`.

**Consequence:** `Decision.t_server_ms` stays `None` for Jev, and `t_server` rows in analysis 6.3-A
are reported as "not provided by the API". To be re-checked on the first live call by dumping all
response headers (an undocumented `server-timing` header is possible; if found it would be recorded
as undocumented and flagged to the human before use).

## 6. Models and versions [models]

| Name | Resolves to | Meaning |
|---|---|---|
| `jev-1.13.0` | — | the only current model |
| `jev-latest` | `jev-1.13.0` | "most recent stable, official release"; SDK default |
| `jev-preview` | `jev-1.13.0` | currently identical to `jev-latest` |

- "An alias moves when a new release ships, so the answers behind it can change without a change on
  your side. The response's `model` field reports the versioned ID that answered". The vendor
  advises: "pin that version's ID instead of the alias".
- **Doc inconsistency:** [models] says the response `model` field reports the versioned ID, and the
  Cloudflare examples show `"jev-1.13.0"`, but every example response in [api] and [quickstart]
  shows `"model": "jev-latest"`. To be settled by the first live call. `JevClient` logs both the
  requested name (`meta.requested_model`) and the reported one (`JevResponse.model`).
- `GET /v1/models` lists the names an account may use (`name`, `description`, `release_date`).
- "the same weights serve every account"; no fine-tuning. "Jev is not trained on customer requests
  or responses."
- Determinism: the docs say only that `jev-1.13` "is extremely consistent, meaning you should
  expect quantitatively similar outputs for semantically similar inputs." [jagged] No sampling
  parameters (temperature, seed) are documented. Bit-exact repeatability is **unverified**; this
  matters for the disk cache and the "live vs. table" check in SPEC §7.

## 7. Limits, errors, cost

- Rate limits: **250,000 tokens/s and 1,200 requests/min**; over either → `429`. [models]
- "**Rate limits are adjusting dynamically** ... the limits above can change without notice".
- Errors [api]: `401` bad key · `422` validation (body names the field) · `429` rate limit ·
  `529` overloaded. Advice: "retry the request with exponential backoff". SDKs retry by default and
  honour `Retry-After` / `retry-after-ms`.
- SDK default timeout: 10.0 s per HTTP operation. [constants] `JevClient` uses the same default.
- Price: $0.042 per million **input** tokens; output free. [models] Documented examples use
  ~300–430 input tokens for short states. At an assumed ~500 tokens per call, the full
  `--max-calls` budget of 30,000 calls ≈ 15 Mtok ≈ **$0.63**. Cost is not a constraint; the
  request-rate limit is.

### Fit with the SPEC §6.2 protocol

- Sequential keep-alive calls: at the vendor's claimed "70ms-500ms" end-to-end [blog] this is
  2–14 req/s = 120–860 req/min — **under** 1,200/min. OK.
- Throughput test with 8 parallel requests: at 70 ms each this could reach ~6,800 req/min —
  **over** the limit. It must be rate-capped below 20 req/s, or it will measure 429s. This does not
  block the protocol (SPEC says "if limits allow") but the cap must be part of `configs/timing.yaml`.
- Policy-table build (450 calls) and 50 live episodes × ≤500 trials × 2 modes (≤50,000 calls
  worst case) — the live episodes alone can **exceed `--max-calls` = 30,000**. See open questions.

## 8. Documented weaknesses that touch our design [jagged]

"Jev 1.13 jaggedness", last reviewed by the vendor 2026-09-17:

- "It struggles with tasks that require numeric precision."
- "`jev-1.13` will perform better on semantic representations than numeric. ... **Instead:** do the
  conversion in code and pass in either the computed number or a named bucket."
- "Jev is not a calculator. We strongly recommend implementing any mathematical logic in code."
- "`jev-1.13` answers the question you wrote, not the one you meant."
- "Accuracy falls as the state grows with content unrelated to the decision."

This bears directly on SPEC §4.3: the `naive` mode is "only fields and numbers" — the input format
the vendor documents as weak. It is not a reason to change the design silently (SPEC rule 4: no
tuning toward a result), but the human should decide knowingly; see open questions.

## 9. Speed claims (context only — not tested by this project, SPEC §6.1)

[blog]: "End-to-end response time is 70ms-500ms"; compared with LLMs at "3 to 329 seconds";
"40x-200x faster". These are claims relative to LLMs.

## 10. Client decisions (current)

| Decision | Why |
|---|---|
| Own `httpx` client, no SDK | SDKs retry by default; a retried call would count as one latency sample |
| **No retries** in `JevClient` | One latency sample = one HTTP exchange. Retry policy for table building belongs to the caller (M4); retried samples are excluded from latency |
| One `httpx.Client` per `JevClient` | Keep-alive session (SPEC §4.3) |
| **Single timer**: `t_wall_ns` around the HTTP exchange | D10. No trace hooks, no server or gateway time |
| `X-OpenRouter-Cache: false` on every request | D15: a timed call can never be served from a cache |
| Model pinned to the `typesafe/jev-1.13` family, checked on every response | D13 |
| Canonical JSON body (`sort_keys`, compact) | Byte-stable; `request_bytes` logged (SPEC §4.3) |
| `CallBudget` counts attempts | A failed request may still be billed. In-process for now; a cross-run ledger is due at M4 (D8) |
| `MockJevClient` busy-waits instead of `time.sleep` | `sleep(10 ms)` was measured at up to 110 ms on this Mac; busy-wait overshoots by < 30 µs |

## 11. Live findings, 2026-09-19 (`fob jev smoke --n 20`, OpenRouter backend)

21 identical requests (1 `curl` probe + 20 via `JevClient`): state
`{"sugar":0.7,"bitter":0.05,"looming":0.6,"hunger":0.5}`, one Choice question, options with `null`
criteria. This is a smoke-test prompt, **not** an experiment prompt.

| Finding | Evidence | Consequence |
|---|---|---|
| **Jev is not deterministic** | 20 identical requests → 11 distinct probability vectors; P(EAT) 0.52–0.62. The `curl` probe of the same body returned ESCAPE 0.58 / EAT 0.40 — **the argmax flipped**. OpenRouter's cookbook reports the same ("moved the probabilities by up to eight hundredths") | One call per grid point (SPEC §4.5: 450 calls) cannot define `π`. Jev needs `N_rep` like the connectome. The disk cache must store *all* repeats, never deduplicate by request bytes. "Live vs. table" JS divergence (SPEC §7) has a non-zero noise floor that must be measured |
| Response `model` is a dated versioned id | `typesafe/jev-1.13-20260917` for requested `typesafe/jev-1.13` | Settles the doc inconsistency in §6 for this path. Log it per call; fail if it changes mid-run |
| Probabilities are rounded to 2 decimals; option order varies between calls | see smoke output | Never rely on key order. Sums were 1.00 in all 21 responses; renormalise anyway |
| No server-timing header | headers: `x-generation-id`, `x-provider-name`, CORS, security, `server: cloudflare` | §5 stands for the response itself |
| OpenRouter records a per-request `latency` | `GET /api/v1/generation?id=<x-generation-id>` → `latency: 349` (ms, "Total latency in milliseconds"), `generation_time: 0` (not populated for `api_type: decisions`), `provider_name: TypeSafe` for a call whose client-side total was 603 ms | A candidate for `t_server_ms`, with caveats: it is OpenRouter's measurement of its upstream call, not TypeSafe's processing time, and needs a second HTTP request (must happen outside the timed region, after the benchmark). Human decision — see open questions |
| Latency, 20 sequential keep-alive calls | cold 772 ms (connect+TLS 36 ms); p50 405, p90 480, max 772 ms | Indicative only: measured from a throttled agent process (see `sources.md`), HTTP/1.1, via OpenRouter |
| Keep-alive works | `connect_ns` present on call 0 only | |
| Cost | $0.000281 for 20 calls (≈ $0.000014 each, 334 input tokens) | 100,000 calls ≈ $1.40. `--max-calls` is a safety fuse, not a budget constraint |

## 12. Full request body for each state mode (templates v1)

Generated by `scripts/jev_templates_report.py` from `configs/jev_prompts/` for the observation
sugar 0.6, bitter 0.05, looming 0.5, hunger 0.5. Wire format is compact JSON with sorted keys;
it is pretty-printed here. In the informed modes the rules precede the question inside
`instructions`, and `state` carries the observation only (decision D46).

### `naive`

```json
{
  "model": "typesafe/jev-1.13",
  "questions": {
    "action": {
      "criteria": {
        "EAT": null,
        "ESCAPE": null,
        "IDLE": null
      },
      "instructions": "Which action should the agent take on this trial?",
      "type": "choice"
    }
  },
  "state": {
    "bitter": 0.05,
    "hunger": 0.5,
    "looming": 0.5,
    "sugar": 0.6
  }
}
```

### `informed`

```json
{
  "model": "typesafe/jev-1.13",
  "questions": {
    "action": {
      "criteria": {
        "EAT": "Eat the food that is present on this trial.",
        "ESCAPE": "Flee from a possible predator.",
        "IDLE": "Do nothing on this trial."
      },
      "instructions": "An agent lives through a sequence of trials and tries to stay alive for as many trials as possible, up to 500. On every trial it observes four numbers between 0 and 1 and takes one action. `sugar` is the amount of food present; 0 means there is no food. Food is present on 30% of trials. `bitter` is the bitterness of the food. 25% of food is toxic. Toxic food has bitterness between 0.3 and 1; safe food has bitterness between 0 and 0.1. `looming` is a noisy visual cue of a predator. A predator is really present on 20% of trials. When a predator is present, looming is drawn from a normal distribution with mean 0.7 and standard deviation 0.2; when no predator is present, from a normal distribution with mean 0.2 and standard deviation 0.2. The value is clipped to the range 0 to 1. hunger = 1 − (energy / 100): 0 means full energy, 1 means about to starve. Energy starts at 50, cannot exceed 100, and the agent dies when energy reaches 0. Every trial costs 1 energy. EAT adds 8 times sugar to energy. If the food is toxic, EAT also subtracts 15 times bitter from energy. If a predator is present, an agent that eats dies with probability 0.6. ESCAPE costs an additional 1 energy. A predator cannot kill an agent that escapes. IDLE has no additional cost. If a predator is present, an idle agent dies with probability 0.3.\n\nWhich action should the agent take on this trial?",
      "type": "choice"
    }
  },
  "state": {
    "bitter": 0.05,
    "hunger": 0.5,
    "looming": 0.5,
    "sugar": 0.6
  }
}
```

### `bucketed`

```json
{
  "model": "typesafe/jev-1.13",
  "questions": {
    "action": {
      "criteria": {
        "EAT": null,
        "ESCAPE": null,
        "IDLE": null
      },
      "instructions": "Which action should the agent take on this trial?",
      "type": "choice"
    }
  },
  "state": {
    "bitter": "very low",
    "hunger": "medium",
    "looming": "medium",
    "sugar": "high"
  }
}
```

### `informed_bucketed`

```json
{
  "model": "typesafe/jev-1.13",
  "questions": {
    "action": {
      "criteria": {
        "EAT": "Eat the food that is present on this trial.",
        "ESCAPE": "Flee from a possible predator.",
        "IDLE": "Do nothing on this trial."
      },
      "instructions": "An agent lives through a sequence of trials and tries to stay alive for as many trials as possible, up to 500. On every trial it observes four quantities and takes one action. Each quantity lies between 0 and 1 and is reported as a level: none (exactly 0), very low (above 0 and below 0.2), low (0.2 to 0.4), medium (0.4 to 0.6), high (0.6 to 0.8) or very high (0.8 to 1). `sugar` is the amount of food present; 0 means there is no food. Food is present on 30% of trials. `bitter` is the bitterness of the food. 25% of food is toxic. Toxic food has bitterness between 0.3 and 1; safe food has bitterness between 0 and 0.1. `looming` is a noisy visual cue of a predator. A predator is really present on 20% of trials. When a predator is present, looming is drawn from a normal distribution with mean 0.7 and standard deviation 0.2; when no predator is present, from a normal distribution with mean 0.2 and standard deviation 0.2. The value is clipped to the range 0 to 1. hunger = 1 − (energy / 100): 0 means full energy, 1 means about to starve. Energy starts at 50, cannot exceed 100, and the agent dies when energy reaches 0. Every trial costs 1 energy. EAT adds 8 times sugar to energy. If the food is toxic, EAT also subtracts 15 times bitter from energy. If a predator is present, an agent that eats dies with probability 0.6. ESCAPE costs an additional 1 energy. A predator cannot kill an agent that escapes. IDLE has no additional cost. If a predator is present, an idle agent dies with probability 0.3.\n\nWhich action should the agent take on this trial?",
      "type": "choice"
    }
  },
  "state": {
    "bitter": "very low",
    "hunger": "medium",
    "looming": "medium",
    "sugar": "high"
  }
}
```

## Not documented

Things the official docs do not state; none of these may be assumed:

1. Any server-side processing time (field or header).
2. The formula for `confidence`.
3. Sampling parameters, seeds, or a bit-exact determinism guarantee.
4. Rate-limit response headers other than `Retry-After` / `retry-after-ms`.
5. Whether HTTP/2 is supported by `api.typesafe.ai`.
6. Server region(s) / anycast behaviour — relevant to interpreting `t_wall`.
7. Rate limits on the Cloudflare path.
8. The error body schema beyond "a JSON body describing what went wrong".

## Sources

| Tag | URL |
|---|---|
| [api] | https://docs.typesafe.ai/api.md |
| [models] | https://docs.typesafe.ai/models.md |
| [quickstart] | https://docs.typesafe.ai/introduction/quickstart.md |
| [state] | https://docs.typesafe.ai/concepts/state.md |
| [confidence] | https://docs.typesafe.ai/confidence.md |
| [jagged] | https://docs.typesafe.ai/model-jaggedness/jev-1.13.md |
| [constants] | https://docs.typesafe.ai/sdk/python/api/constants.md |
| [sdk-responses] | https://docs.typesafe.ai/sdk/python/api/types/responses.md |
| [cf] | https://developers.cloudflare.com/ai/models/typesafe/jev/ (+ `schema-input.json`, `schema-output.json`) |
| [blog] | https://typesafe.ai/blog/introducing-system-one-models-and-jev |
| [or-decisions] | https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-questions-and-answers-request.md |
| [or-cookbook] | https://openrouter.ai/docs/cookbook/building-agents/gate-tool-calls-with-jev |
| [or-cache] | https://openrouter.ai/docs/guides/features/response-caching.md |
| [or-generation] | https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation.md |
| [or-latency] | https://openrouter.ai/docs/guides/best-practices/latency-and-performance.md |
| [langchain] | https://www.langchain.com/blog/building-a-harness-with-jev — `langchain-typesafe`, `TypeSafeClassifier().invoke(state=..., questions=...)`; not used by this project |
| index | https://docs.typesafe.ai/llms.txt · https://docs.typesafe.ai/llms-full.txt |
