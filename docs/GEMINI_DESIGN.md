# Explanation Provider Design

## Purpose and authority boundary

The explanation layer makes structured recovery evidence easier for humans to understand and operate. Phase 7 supports bounded decision-trace and recovery-case explanations through Groq, optional Gemini, fake, and deterministic providers.

An explanation provider is not a financial authority. It may not determine payment or subscription status, infer that money moved, set transaction amounts, approve policy, bypass stopping rules, choose authoritative retry counts, execute actions, or attribute revenue. Those facts come from verified provider events, application state, deterministic calculations, and policy.

## Configuration

Groq uses the OpenAI-compatible client with `https://api.groq.com/openai/v1`. Configuration is environment-driven:

- `EXPLANATION_PROVIDER` defaults to `fallback` and may select `groq`, `gemini`, or `fallback`;
- `GROQ_API_KEY` is optional at application startup;
- `GROQ_MODEL` defaults to `openai/gpt-oss-120b`; model, timeout, and maximum retries are typed settings;
- `GEMINI_ENABLED` defaults to false;
- `GEMINI_API_KEY` is optional at application startup;
- `GEMINI_MODEL` defaults to `gemini-3.7-flash` but is configurable;
- `GEMINI_API_VERSION`, timeout, maximum retries, and thinking level are typed settings.

No call occurs during import or application startup. Keys are represented as secret types and never included in health responses, logs, prompts, or exceptions. Missing keys, provider failures, timeouts, network errors, and invalid responses resolve to deterministic explanations.

## Provider abstraction

```text
ExplanationProvider protocol
├── GroqExplanationProvider        primary OpenAI-compatible adapter
├── GeminiLLMProvider              optional Google SDK adapter
├── FakeLLMProvider                deterministic fixtures and tests
├── ResilientExplanationProvider   failure isolation
└── DeterministicFallbackProvider  evidence-derived local explanation
```

Business code accepts the protocol and Pydantic input/output models. It does not import provider SDK types. `FakeLLMProvider` proves consumers can use a valid structured response without network access. The fallback uses only supplied evidence and never generates missing numerical facts.

## Structured output

Machine-consumed responses are validated, never scraped from arbitrary prose. The Phase 7 schema is:

```text
DecisionExplanation
  summary: string
  factors: list[string]
  confidence: number [0, 1]
  limitations: list[string]
```

Groq uses JSON Object Mode and includes the Pydantic JSON schema in the prompt. Every response is validated locally with `DecisionExplanation`, including `extra="forbid"`. Gemini retains its schema request and local Pydantic validation. Neither provider can return an action, policy result, execution command, or recovery outcome field.

## Reliability and rate limits

Provider calls use bounded timeouts and bounded SDK retries. Missing configuration, authentication failures, timeouts, network failures, and invalid structured output return a deterministic fallback. Explanation failure never stops ingestion, scoring, policy, scheduling, execution, or attribution.

No silent model substitution is allowed. Provider failure selects the deterministic local explanation, not another remote model.

## Data minimization

Each capability will have an explicit allowlist serializer. Allowed evidence may include anonymous identifiers, amount in minor units, payment-method category, normalized failure category, aggregate health statistics, candidate scores, selected action, confidence, and policy result. Forbidden data includes credentials, raw headers, complete webhooks, tokens, PAN, CVV, OTP, raw bank data, unnecessary customer identifiers, and free-form internal notes.

Safe metrics record use case, prompt version, model, latency, token counts when provided, cache/fallback status, and error category. They do not record secrets or raw sensitive inputs.

## Prompt-injection resistance

All provider, payment, and customer text is untrusted data. Prompts will state that embedded instructions must not be followed and that the model cannot authorize recovery or request secrets. Structured inputs will be serialized as delimited data, and externally supplied message values such as payment links will be deterministic placeholders filled by application code only after validation.

Regression tests include authority-field rejection and assert that secret fields never reach the provider payload.

## Testing strategy

Normal tests use fake clients or fallback providers and require neither credentials nor network. Tests cover schema validity, disabled configuration, missing keys, invalid credentials, invalid structured output, timeouts, network errors, secret isolation, and the invariant that provider output cannot mutate financial state or bypass policy. Live provider validation is explicit and never runs during startup or the ordinary test suite.
