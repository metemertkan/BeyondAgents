"""The tool-calling loop both agents use: Penny's loop from Episode 1, with its own tools and prompt."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Callable

from penny.agent import OLLAMA


def chat(model: str, messages: list[dict], tools: list[dict], seed: int, usage: list[dict],
         server_errors: list[str], think=False) -> dict:
    for attempt in range(3):
        body = {"model": model, "messages": messages, "tools": tools, "stream": False, "think": think,
                "options": {"seed": seed + 1000 * attempt, "num_ctx": 8192, "num_predict": 2048}}
        req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=1800) as r:
                answer = json.loads(r.read())
            usage.append({"prompt_tokens": answer.get("prompt_eval_count", 0),
                          "output_tokens": answer.get("eval_count", 0)})
            return answer["message"]
        except urllib.error.HTTPError as e:
            if e.code != 500 or attempt == 2:
                raise
            server_errors.append(e.read().decode(errors="replace")[:300])
    raise RuntimeError("unreachable")


def run(model: str, system: str, user: str, tools: list[dict], execute: Callable[[str, dict], str], seed: int,
        nudge: str | None = None, finished: Callable[[], bool] | None = None, max_calls: int = 16) -> dict:
    """Run until the model stops calling tools. With `nudge`, a stop before `finished()` gets up to two nudges."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    transcript, usage, server_errors = [], [], []
    nudges, final = 0, ""
    started = time.time()
    for _ in range(max_calls):
        m = chat(model, messages, tools, seed, usage, server_errors)
        msg = {"role": "assistant", "content": m.get("content", "")}
        if m.get("tool_calls"):
            msg["tool_calls"] = m["tool_calls"]
        messages.append(msg)
        calls = m.get("tool_calls") or []
        if not calls:
            final = m.get("content", "")
            transcript.append({"type": "note", "text": final})
            if nudge and nudges < 2 and finished is not None and not finished():
                nudges += 1
                transcript.append({"type": "operator", "text": nudge})
                messages.append({"role": "user", "content": nudge})
                continue
            break
        for c in calls:
            name = c["function"]["name"]
            args = c["function"].get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_raw": args}
            result = execute(name, args)
            transcript.append({"type": "tool", "name": name, "args": args, "result": result})
            messages.append({"role": "tool", "tool_name": name, "content": result})
    return {"seconds": round(time.time() - started, 1), "transcript": transcript, "final": final,
            "server_errors": server_errors, "model_calls": len(usage),
            "tokens": {"prompt": sum(u["prompt_tokens"] for u in usage),
                       "output": sum(u["output_tokens"] for u in usage)}}
