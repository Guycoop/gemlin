"""Gemlin's brain: Gemma on Google's servers, or Gemma on this computer.

Both look the same to the rest of Gemlin:
  brain.new_chat(system, tools, history)  a chat with .send_message(text) -> reply.text and .get_history()
  brain.ask(prompt, system)               one question, one answer (used by `gemlin develop`)

"local" talks to LM Studio (https://lmstudio.ai) or Ollama (https://ollama.com) on this computer,
through the OpenAI-style API they both serve. No API key, nothing leaves your machine.
Pick with `gemlin model local` / `gemlin model google`, or "Think on this computer" in Gemlin's menu.
"""
import inspect
import json
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace

from . import paths

SERVERS = {"LM Studio": "http://localhost:1234/v1", "Ollama": "http://localhost:11434/v1"}
PREFERRED = ("gemma-4-12b", "gemma-4-e4b", "gemma-4-26b", "gemma4", "gemma-4", "gemma")  # first match wins
LMS = Path.home() / ".lmstudio" / "bin" / "lms"


class LocalError(Exception):
    """Something went wrong talking to the model on this computer (the message says what to do)."""


def source():
    """"local" or "google": where Gemlin thinks, from `gemlin model` (Google unless you chose local)."""
    return "local" if paths.config().get("brain") == "local" else "google"


def use(where, model=None):
    paths.save_config(brain=where, **({"local_model": model} if model else {}))


# ---------- Google ----------

class Google:
    def __init__(self, key, model):
        from google import genai
        self.client, self.model = genai.Client(api_key=key), model
        self.label = f"{model} on Google"

    def new_chat(self, system, tools, history=None):
        from google.genai import types
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=list(tools),  # plain Python functions = automatic function calling
            thinking_config=types.ThinkingConfig(thinking_level="minimal"),  # "high" = smarter, slower
        )
        return self.client.chats.create(model=self.model, config=config, history=history or [])

    def ask(self, prompt, system):
        from google.genai import types
        reply = self.client.models.generate_content(model=self.model, contents=prompt,
                                                    config=types.GenerateContentConfig(system_instruction=system))
        return reply.text or ""


# ---------- this computer ----------

def get_json(url, body=None, timeout=5):
    request = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def find_server(start=True):
    """(name, url, model ids) for LM Studio or Ollama running here, or None. If LM Studio is
    installed but its server is off, start it."""
    for name, url in SERVERS.items():
        with suppress(OSError, ValueError):
            return name, url, [m["id"] for m in get_json(f"{url}/models", timeout=1.5).get("data", [])]
    if start and LMS.exists():
        subprocess.run([str(LMS), "server", "start"], capture_output=True, timeout=30)
        for _ in range(10):
            time.sleep(0.5)
            if found := find_server(start=False):
                return found
    return None


def pick_model(ids, wanted=None):
    if wanted and wanted in ids:
        return wanted
    for name in PREFERRED:
        for model_id in ids:
            if name in model_id.lower() and "embed" not in model_id.lower():
                return model_id
    return next((m for m in ids if "embed" not in m.lower()), None)


def tool_schema(fn):
    """Describe a Python function the way OpenAI-style tool calling expects, from its signature
    and docstring (the same things Google's SDK reads)."""
    kinds = {int: "integer", float: "number", bool: "boolean", str: "string", list: "array", dict: "object"}
    properties, required = {}, []
    for name, param in inspect.signature(fn).parameters.items():
        properties[name] = {"type": kinds.get(param.annotation, "string")}
        if param.default is inspect.Parameter.empty:
            required.append(name)
    doc = inspect.cleandoc(fn.__doc__ or fn.__name__)
    return {"type": "function", "function": {"name": fn.__name__, "description": doc,
                                             "parameters": {"type": "object", "properties": properties,
                                                            "required": required}}}


class LocalChat:
    """A chat with the same shape as Google's, that runs the tool calls itself."""

    def __init__(self, brain, system, tools, history=None):
        self.brain, self.tools = brain, {t.__name__: t for t in tools}
        self.schemas = [tool_schema(t) for t in tools]
        self.messages = [{"role": "system", "content": system}, *(history or [])]

    def send_message(self, text):
        self.messages.append({"role": "user", "content": text})
        for _ in range(10):  # at most 10 rounds of tool calls per message
            message = self.brain.complete(self.messages, self.schemas)
            calls = message.get("tool_calls") or []
            self.messages.append({"role": "assistant", "content": message.get("content") or "",
                                  **({"tool_calls": calls} if calls else {})})
            if not calls:
                return SimpleNamespace(text=clean(message.get("content") or ""))
            for call in calls:
                self.messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                      "content": self.run(call.get("function", {}))})
        return SimpleNamespace(text="(I got tangled up in my tools. Try asking another way?)")

    def run(self, call):
        fn = self.tools.get(call.get("name"))
        if fn is None:
            return f"There is no tool called {call.get('name')}."
        try:
            args = call.get("arguments") or {}
            result = fn(**(json.loads(args) if isinstance(args, str) else args))
        except Exception as e:  # tell the model, so it can try again or explain
            result = f"That didn't work: {e!r}"
        return json.dumps(result, default=str)[:8000]

    def get_history(self):
        return self.messages[1:]


def clean(text):  # some local models show their thinking; Gemlin only says the answer
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


class Local:
    def __init__(self, model=None):
        found = find_server()
        if not found:
            raise LocalError("I can't find Gemma on this computer. Install LM Studio (lmstudio.ai) or "
                             "Ollama (ollama.com), download a Gemma model, and start it. Then try again.")
        self.server, self.url, ids = found
        self.model = pick_model(ids, model or paths.config().get("local_model"))
        if not self.model:
            raise LocalError(f"{self.server} is running but has no models. Download Gemma in it first.")
        self.label = f"{self.model} on this computer ({self.server})"

    def complete(self, messages, tools=None):
        body = {"model": self.model, "messages": messages, "temperature": 0.7, **({"tools": tools} if tools else {})}
        try:
            reply = get_json(f"{self.url}/chat/completions", body, timeout=300)  # the first answer loads the model
        except urllib.error.HTTPError as e:
            raise LocalError(f"{self.server} said: {e.read().decode('utf-8', 'replace')[:200]}") from e
        except OSError as e:
            raise LocalError(f"I lost {self.server}. Is it still running? ({e})") from e
        return reply["choices"][0]["message"]

    def new_chat(self, system, tools, history=None):
        return LocalChat(self, system, tools, history)

    def ask(self, prompt, system):
        return clean(self.complete([{"role": "system", "content": system}, {"role": "user", "content": prompt}])
                     .get("content") or "")


def lms_installed():
    return LMS.exists() or shutil.which("lms") is not None
