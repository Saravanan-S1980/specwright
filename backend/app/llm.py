"""The only module that calls the Anthropic API.

Every pipeline stage goes through `call_structured`. Keeping the API in one
place means one spot for retries, tracing and (later) cost tracking.

How we get structured output with tool use:
1. We describe one "tool" whose input_schema is the Pydantic model's JSON schema.
2. We tell Claude to answer by calling that tool. Claude then writes its answer
   as the tool's arguments, which is JSON shaped like our schema.
3. We never run the tool. We just read its arguments and validate them with
   Pydantic. If they don't fit, we retry once.

Why not force the tool with tool_choice={"type": "tool"}? Our main and deep
models (Sonnet 5.5, Opus 5.5) reject forced tool choice with a 400. We use
tool_choice "auto" plus strict mode and a clear instruction instead.
See docs/decisions/0003-structured-output-via-tool-use.md.
"""

import copy
import json
import logging
import time
from pathlib import Path
from typing import Any, TypeVar

from anthropic import Anthropic
from pydantic import BaseModel, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Where every call gets logged, one JSON object per line. traces/ is gitignored.
TRACE_PATH = Path("traces/calls.jsonl")

# One retry is enough to fix most slips without hiding a broken prompt.
MAX_ATTEMPTS = 2

# Plenty of room for a ranked problem list. Too low and the JSON gets cut off.
MAX_TOKENS = 16000

# Strict mode can't enforce these keywords, so we drop them from the schema we
# send. Pydantic still checks them when it validates the answer.
_UNSUPPORTED_KEYWORDS = {
    "minLength", "maxLength", "minimum", "maximum", "exclusiveMinimum",
    "exclusiveMaximum", "multipleOf", "minItems", "maxItems", "pattern",
}


class StructuredOutputError(Exception):
    """Claude didn't return valid data after every attempt."""


def _get_client() -> Anthropic:
    # Pass the key explicitly. Cloud sessions don't expose ANTHROPIC_API_KEY,
    # so the SDK's default lookup would fail there (see ADR 0002).
    return Anthropic(api_key=settings.api_key)


def tool_schema(output_model: type[BaseModel]) -> dict[str, Any]:
    """Turn a Pydantic model into a JSON schema that strict tool use accepts."""
    schema = copy.deepcopy(output_model.model_json_schema())

    def clean(node: Any) -> None:
        if isinstance(node, dict):
            for key in _UNSUPPORTED_KEYWORDS & node.keys():
                del node[key]
            # Strict mode needs every object to forbid extra keys.
            if node.get("type") == "object":
                node["additionalProperties"] = False
            for value in node.values():
                clean(value)
        elif isinstance(node, list):
            for item in node:
                clean(item)

    clean(schema)
    return schema


def _tool_name(output_model: type[BaseModel]) -> str:
    # e.g. ProblemList -> "submit_problemlist". Tool names must be simple.
    return f"submit_{output_model.__name__.lower()}"


def _write_trace(record: dict[str, Any]) -> None:
    # A trace failure should never break the pipeline, so we only log it.
    try:
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as exc:
        logger.warning("could not write trace: %s", exc)


def call_structured(model: str, system: str, user: str, output_model: type[T]) -> T:
    """Ask Claude for data shaped like `output_model` and return it validated.

    Retries once if Claude skips the tool or returns data Pydantic rejects.
    Raises StructuredOutputError if both attempts fail.
    """
    client = _get_client()
    name = _tool_name(output_model)
    tool = {
        "name": name,
        "description": f"Submit your final answer as a {output_model.__name__}.",
        "input_schema": tool_schema(output_model),
        "strict": True,  # the API checks the arguments match the schema
    }
    # The instruction does the job a forced tool_choice used to do.
    full_system = f"{system}\n\nAlways answer by calling the {name} tool exactly once."
    messages: list[dict[str, Any]] = [{"role": "user", "content": user}]

    last_error = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        start = time.perf_counter()
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=full_system,
            messages=messages,
            tools=[tool],
            tool_choice={"type": "auto"},
        )
        latency_ms = round((time.perf_counter() - start) * 1000)

        _write_trace({
            "ts": time.time(),
            "model": model,
            "output_model": output_model.__name__,
            "attempt": attempt,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "latency_ms": latency_ms,
            "stop_reason": response.stop_reason,
        })

        tool_use = next(
            (b for b in response.content if b.type == "tool_use" and b.name == name), None
        )
        if tool_use is None:
            last_error = f"no {name} call (stop_reason={response.stop_reason})"
            feedback = f"You didn't call the {name} tool. Call it now with your answer."
        else:
            try:
                return output_model.model_validate(tool_use.input)
            except ValidationError as exc:
                last_error = str(exc)
                feedback = f"Your {name} input failed validation:\n{exc}\nCall it again, fixed."

        logger.warning("attempt %d failed: %s", attempt, last_error)
        # Show Claude its own answer plus what was wrong, so the retry can fix it.
        messages.append({"role": "assistant", "content": response.content})
        if tool_use is not None:
            # A tool_use block must be answered by a tool_result block.
            messages.append({"role": "user", "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": feedback,
                "is_error": True,
            }]})
        else:
            messages.append({"role": "user", "content": feedback})

    raise StructuredOutputError(f"no valid {output_model.__name__} after "
                                f"{MAX_ATTEMPTS} attempts: {last_error}")
