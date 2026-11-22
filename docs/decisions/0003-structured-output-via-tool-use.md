# 0003: Structured output through one strict tool, not a forced tool

Date: 2026-11-22

## Context
Every stage needs Claude to return data that fits a Pydantic model. The session 1 plan said to force the call with `tool_choice={"type": "tool", "name": ...}`.

I tested that against our models. Haiku 5.5 accepts it. Sonnet 5.5, our main model, returns a 400: `tool_choice: type "tool" and "any" are not supported for this model.` Opus 5.5, our deep model, rejects it too.

## Decision
`llm.call_structured` defines one tool whose `input_schema` is the model's JSON schema, with `strict: true`. It sets `tool_choice` to `auto` and tells Claude in the system prompt to answer by calling that tool once.

If Claude skips the tool or Pydantic rejects the arguments, we send the error back and retry once.

Strict mode can't enforce `minLength`, `minItems` and similar keywords, so `tool_schema()` strips them before sending. Pydantic still checks them on the way back.

## Alternatives considered
- Forced `tool_choice`: works only on Haiku. We'd need different code per model.
- JSON outputs (`output_config.format` or `client.messages.parse()`): also fine, and arguably simpler. We kept tool use because it's the pattern the learning plan teaches, and it carries over to later stages where Claude calls real tools.
- No `strict`: Claude usually gets the shape right anyway, but strict mode turns "usually" into a guarantee at the API level.

## Consequences
One code path works on all three models. A skipped tool call costs one retry, which the trace log will show. If retries pile up in the traces, switch to `output_config.format`.
