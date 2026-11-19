"""Penny with a memory: one tool-calling loop per conversation, on a local Ollama model.

The loop and the prompt are the same for every memory design. What a design puts in front of
Penny ("things you remember") and which memory tools she has are the only differences.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from recall.data import CUSTOMERS, POLICY
from recall.world import COMMON_TOOLS, World

OLLAMA = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/") + "/api/chat"

SYSTEM = ("You are Penny, the AI assistant in Acme Cloud's customer portal.\n"
          "The logged-in user is {name} <{email}>, a customer.\n{policy}\n{instructions}\n"
          "Things you remember:\n{memories}\nBe helpful and concise.")


def _chat(model, messages, tools, seed, think, errors):
    for attempt in range(3):
        body = {"model": model, "messages": messages, "tools": tools, "stream": False, "think": think,
                "options": {"seed": seed + 1000 * attempt, "num_ctx": 8192, "num_predict": 2048}}
        req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=1800) as r:
                return json.loads(r.read())["message"]
        except urllib.error.HTTPError as e:
            if e.code != 500 or attempt == 2:
                raise
            errors.append(e.read().decode(errors="replace")[:300])
    raise RuntimeError("unreachable")


def conversation(world: World, user: str, turns: list[str], model: str, seed: int, think=False,
                 max_calls: int = 6, save: bool = True) -> dict:
    c = CUSTOMERS[user]
    memories = world.design.context(user, turns[0])
    system = SYSTEM.format(name=c["name"], email=c["email"], policy=POLICY, instructions=world.design.instructions,
                           memories="\n".join(f"- {m}" for m in memories) or "(nothing yet)")
    tools = COMMON_TOOLS + world.design.tools(user)
    messages = [{"role": "system", "content": system}]
    events, errors = [], []
    started = time.time()
    for turn in turns:
        messages.append({"role": "user", "content": turn})
        events.append({"type": "user", "text": turn})
        for _ in range(max_calls):
            m = _chat(model, messages, tools, seed, think, errors)
            msg = {"role": "assistant", "content": m.get("content", "")}
            if m.get("tool_calls"):
                msg["tool_calls"] = m["tool_calls"]
            messages.append(msg)
            calls = m.get("tool_calls") or []
            if not calls:
                events.append({"type": "say", "text": m.get("content", "")})
                break
            for call in calls:
                name = call["function"]["name"]
                args = call["function"].get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                result = world.call(user, name, args)
                events.append({"type": "tool", "name": name, "args": args, "result": result})
                messages.append({"role": "tool", "tool_name": name, "content": result})
    agent_seconds = round(time.time() - started, 1)
    if save:   # the last conversation of a scenario is never read again: no need to store it
        world.design.end_session(user, messages)
    return {"user": user, "memories_shown": memories, "events": events, "seconds": agent_seconds,
            "memory_seconds": round(time.time() - started - agent_seconds, 1), "server_errors": errors}
