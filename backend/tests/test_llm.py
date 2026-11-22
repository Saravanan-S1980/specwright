"""Tests for llm.py. No API key needed: we swap in a fake Anthropic client."""

import json
from types import SimpleNamespace

import pytest

from app import llm
from app.schemas import ProblemList

GOOD_INPUT = {
    "problems": [{
        "title": "Reminders arrive late",
        "description": "Patients get the reminder after the visit.",
        "persona": "patient",
        "severity": "high",
        "evidence_ids": ["T-1", "T-2"],
    }]
}


def tool_response(tool_input, name="submit_problemlist"):
    """Build an object shaped like an Anthropic Message with one tool call."""
    block = SimpleNamespace(type="tool_use", id="toolu_1", name=name, input=tool_input)
    return SimpleNamespace(
        content=[block],
        stop_reason="tool_use",
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
    )


def text_response(text="Here are the problems..."):
    """A reply where Claude wrote prose instead of calling the tool."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
    )


class FakeClient:
    """Returns the queued responses in order and records every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = self  # so client.messages.create(...) works

    def create(self, **kwargs):
        # Copy the messages list: llm.py keeps appending to the same list.
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


@pytest.fixture
def fake(monkeypatch, tmp_path):
    """Install a fake client and point traces at a temp file."""
    monkeypatch.setattr(llm, "TRACE_PATH", tmp_path / "calls.jsonl")

    def install(*responses):
        client = FakeClient(responses)
        monkeypatch.setattr(llm, "_get_client", lambda: client)
        return client

    return install


def read_traces(tmp_path):
    lines = (tmp_path / "calls.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines]


def test_returns_validated_model(fake):
    client = fake(tool_response(GOOD_INPUT))
    result = llm.call_structured("m", "sys", "user text", ProblemList)

    assert isinstance(result, ProblemList)
    assert result.problems[0].evidence_ids == ["T-1", "T-2"]
    assert len(client.calls) == 1


def test_request_defines_one_strict_tool_from_the_schema(fake):
    client = fake(tool_response(GOOD_INPUT))
    llm.call_structured("my-model", "sys", "user text", ProblemList)

    call = client.calls[0]
    assert call["model"] == "my-model"
    assert call["tool_choice"] == {"type": "auto"}
    [tool] = call["tools"]
    assert tool["name"] == "submit_problemlist"
    assert tool["strict"] is True
    assert "problems" in tool["input_schema"]["properties"]
    assert "submit_problemlist" in call["system"]


def test_schema_is_strict_compatible():
    schema = llm.tool_schema(ProblemList)
    text = json.dumps(schema)
    # Problem.evidence_ids has min_length=1, which strict mode can't enforce.
    assert "minItems" not in text
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["Problem"]["additionalProperties"] is False


def test_retries_once_on_validation_error(fake):
    bad = {"problems": [{**GOOD_INPUT["problems"][0], "evidence_ids": []}]}
    client = fake(tool_response(bad), tool_response(GOOD_INPUT))

    result = llm.call_structured("m", "sys", "user text", ProblemList)

    assert result.problems[0].title == "Reminders arrive late"
    assert len(client.calls) == 2
    # The retry tells Claude what was wrong, as a tool_result marked as an error.
    feedback = client.calls[1]["messages"][-1]["content"][0]
    assert feedback["type"] == "tool_result"
    assert feedback["is_error"] is True


def test_retries_when_claude_skips_the_tool(fake):
    client = fake(text_response(), tool_response(GOOD_INPUT))
    result = llm.call_structured("m", "sys", "user text", ProblemList)

    assert isinstance(result, ProblemList)
    assert len(client.calls) == 2


def test_raises_after_second_failure(fake):
    bad = {"problems": "not a list"}
    fake(tool_response(bad), tool_response(bad))

    with pytest.raises(llm.StructuredOutputError):
        llm.call_structured("m", "sys", "user text", ProblemList)


def test_logs_every_call(fake, tmp_path):
    bad = {"problems": "not a list"}
    fake(tool_response(bad), tool_response(GOOD_INPUT))
    llm.call_structured("my-model", "sys", "user text", ProblemList)

    traces = read_traces(tmp_path)
    assert [t["attempt"] for t in traces] == [1, 2]
    first = traces[0]
    assert first["model"] == "my-model"
    assert first["input_tokens"] == 100
    assert first["output_tokens"] == 50
    assert first["latency_ms"] >= 0


def test_client_gets_key_from_settings(monkeypatch):
    seen = {}
    monkeypatch.setattr(llm, "Anthropic", lambda api_key: seen.setdefault("key", api_key))
    monkeypatch.setattr(llm, "settings", SimpleNamespace(api_key="sk-test"))
    llm._get_client()
    assert seen["key"] == "sk-test"
