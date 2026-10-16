"""Gemma on this computer: describing skills as tools, the tool-calling loop, and picking a model."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from gemlin import models  # noqa: E402


def biggest(top_n: int = 5, folder: str = "~") -> list:
    """Find big files. Use this when the user asks what is eating the disk."""
    return [f"{folder}/a.iso"] * top_n


def needs_name(name: str) -> str:
    """Say hi. Use this when the user wants a greeting."""
    return f"hi {name}"


def test_tool_schema_comes_from_the_signature_and_docstring():
    schema = models.tool_schema(biggest)["function"]
    assert schema["name"] == "biggest" and "eating the disk" in schema["description"]
    assert schema["parameters"]["properties"] == {"top_n": {"type": "integer"}, "folder": {"type": "string"}}
    assert schema["parameters"]["required"] == []
    assert models.tool_schema(needs_name)["function"]["parameters"]["required"] == ["name"]


class FakeBrain:
    """Plays a local model: first asks for a tool, then answers with what it got back."""

    def __init__(self, calls):
        self.calls, self.seen = list(calls), []

    def complete(self, messages, tools=None):
        self.seen.append([dict(m) for m in messages])
        if self.calls:
            name, args = self.calls.pop(0)
            return {"content": "", "tool_calls": [{"id": "call_1", "type": "function",
                                                   "function": {"name": name, "arguments": json.dumps(args)}}]}
        return {"content": "<think>hmm</think>You have 2 big files: " + messages[-1]["content"]}


def test_the_local_chat_runs_tools_and_answers():
    brain = FakeBrain([("biggest", {"top_n": 2})])
    chat = models.LocalChat(brain, "You are Gemlin.", [biggest, needs_name])
    reply = chat.send_message("what's eating my disk?")
    assert reply.text == 'You have 2 big files: ["~/a.iso", "~/a.iso"]'  # thinking removed, tool result used
    roles = [m["role"] for m in chat.get_history()]
    assert roles == ["user", "assistant", "tool", "assistant"]


def test_a_broken_tool_call_is_reported_to_the_model_not_crashed():
    brain = FakeBrain([("biggest", {"nope": 1}), ("no_such_tool", {})])
    chat = models.LocalChat(brain, "You are Gemlin.", [biggest])
    chat.send_message("hi")
    tool_results = [m["content"] for m in chat.get_history() if m["role"] == "tool"]
    assert "didn't work" in tool_results[0] and "no tool called no_such_tool" in tool_results[1]


def test_too_many_tool_rounds_gives_up_politely():
    brain = FakeBrain([("biggest", {})] * 20)
    reply = models.LocalChat(brain, "sys", [biggest]).send_message("loop forever")
    assert "tangled" in reply.text


@pytest.mark.parametrize("ids, wanted, picked", [
    (["text-embedding-nomic", "google/gemma-4-e4b", "google/gemma-4-12b"], None, "google/gemma-4-12b"),
    (["google/gemma-4-e4b", "google/gemma-4-12b"], "google/gemma-4-e4b", "google/gemma-4-e4b"),
    (["gemma4:latest", "llama3"], None, "gemma4:latest"),  # Ollama-style names
    (["qwen3-8b", "text-embedding-nomic"], None, "qwen3-8b"),  # no Gemma: still something that chats
    (["text-embedding-nomic"], None, None),
])
def test_picking_a_local_model(ids, wanted, picked):
    assert models.pick_model(ids, wanted) == picked


def test_no_local_server_explains_what_to_install(monkeypatch):
    monkeypatch.setattr(models, "find_server", lambda start=True: None)
    with pytest.raises(models.LocalError, match="LM Studio"):
        models.Local()
