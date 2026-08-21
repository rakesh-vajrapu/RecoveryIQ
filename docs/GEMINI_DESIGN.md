# Gemini Design

## Purpose and authority boundary

Gemini makes structured recovery evidence easier for humans to understand and operate. It will support four bounded capabilities in later phases: decision explanations, degradation-incident summaries, customer-nudge drafts, and exception investigations. Phase 1 proves only the provider boundary and a `DecisionExplanation` schema.

Gemini is not a financial authority. It may not determine payment or subscription status, infer that money moved, set transaction amounts, approve policy, bypass stopping rules, choose authoritative retry counts, execute actions, or attribute revenue. Those facts come from verified provider events, application state, deterministic calculations, and policy.

## Configuration

The official `google-genai` SDK is isolated in the Gemini provider. Configuration is environment-driven:

- `GEMINI_ENABLED` defaults to false;
- `GEMINI_API_KEY` is optional at application startup;
- `GEMINI_MODEL` defaults to `gemini-3.7-flash` but is configurable;
- `GEMINI_API_VERSION`, timeout, maximum retries, and thinking level are typed settings.

No call occurs during import or application startup. An explicit health check or feature invocation raises a clear configuration error if Gemini is enabled without a key. The key is represented as a secret type and never included in health responses, logs, prompts, or exceptions.

## Provider abstraction

```text
LLMProvider protocol
├── GeminiLLMProvider              networked, SDK-specific implementation
├── FakeLLMProvider                deterministic fixtures and tests
└── DeterministicFallbackProvider  evidence-derived local explanation
```

Business code accepts the protocol and Pydantic input/output models. It does not import Google SDK types. `FakeLLMProvider` proves consumers can use a valid structured response without network access. The fallback uses only supplied evidence and never generates missing numerical facts.

## Structured output

Machine-consumed responses are validated, never scraped from arbitrary prose. The Phase 1 schema is:

```text
DecisionExplanation
  headline: string
  summary: string
  key_factors: list[string]
  uncertainty: string | null
```

The Gemini implementation requests JSON with the Pydantic response schema and validates the parsed response again. A later phase will add versioned prompts and `IncidentSummary`, `CustomerNudgeDraft`, and `ExceptionInvestigation` schemas.

## Reliability and rate limits

Production behavior will use bounded timeouts, exponential backoff with jitter, a concurrency limit, short-lived circuit breaking after repeated failures, and caching keyed by use case, prompt version, requested model, and normalized input. HTTP 429 and retryable 5xx responses may be retried up to the configured maximum. Invalid structured output may be retried once. Exhaustion returns a deterministic fallback and records a safe enrichment failure; it never stops ingestion, scoring, policy, scheduling, or attribution.

No silent model substitution is allowed. Any future fallback model must record requested model, actual model, and reason.

## Data minimization

Each capability will have an explicit allowlist serializer. Allowed evidence may include anonymous identifiers, amount in minor units, payment-method category, normalized failure category, aggregate health statistics, candidate scores, selected action, confidence, and policy result. Forbidden data includes credentials, raw headers, complete webhooks, tokens, PAN, CVV, OTP, raw bank data, unnecessary customer identifiers, and free-form internal notes.

Safe metrics record use case, prompt version, model, latency, token counts when provided, cache/fallback status, and error category. They do not record secrets or raw sensitive inputs.

## Prompt-injection resistance

All provider, payment, and customer text is untrusted data. Prompts will state that embedded instructions must not be followed and that the model cannot authorize recovery or request secrets. Structured inputs will be serialized as delimited data, and externally supplied message values such as payment links will be deterministic placeholders filled by application code only after validation.

Regression tests will include fields containing instructions such as “ignore previous instructions” and assert that secret fields never reach the provider payload.

## Testing strategy

Normal tests use fake or fallback providers and require neither credentials nor network. Tests cover schema validity, disabled configuration, missing-key errors on explicit invocation, invalid structured output fallback, timeouts/429/5xx, prompt injection strings treated as data, allowlist redaction, and the invariant that provider output cannot mutate financial state or bypass policy. Live Gemini smoke tests are explicit, opt-in, and skipped unless a developer deliberately supplies a key.

