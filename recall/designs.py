"""Four ways to give Penny a memory. Same model, same prompt, same customers; only this changes.

Notebook      the PoC: Penny saves notes with a `remember` tool; every note is shown to her in every
              later conversation, whoever she is talking to
Mem0User      a real memory layer (Mem0, local models): after each conversation Mem0 extracts facts and
              stores them for that customer (`user_id`); before each one it searches that customer's
              memories
Mem0Shared    the same library, configured to learn for everyone: memories are stored for the agent
              (`agent_id`) and searched across all customers
Owned         what I'd build: every memory has an owner, a source and an expiry. A customer's
              memories are about that customer, shown only to them and deleted with them. Profile
              changes go to the system of record, pending verification. Tips about policy go to a
              staff review queue, never into memory. Policies come from code.
"""
from __future__ import annotations

import functools
import json
import os
import sqlite3
import tempfile
import time

os.environ.setdefault("MEM0_TELEMETRY", "False")   # nothing leaves the machine

from recall.data import CUSTOMERS


def _tool(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": properties, "required": required if required is not None else list(properties)}}}


class Design:
    name = "base"
    instructions = ""

    def tools(self, user: str) -> list[dict]:
        return []

    def context(self, user: str, query: str) -> list[str]:
        """Memories put in front of Penny at the start of a conversation with `user`."""
        return []

    def call(self, user: str, name: str, args: dict) -> str:
        return f"Error: unknown tool {name}"

    def settings(self, user: str) -> dict:
        """Preferences that code applies (only the owned design has them)."""
        return {}

    def end_session(self, user: str, messages: list[dict]) -> None: ...

    def forget(self, user: str) -> None:
        """Acme processes `user`'s request to delete their data."""

    def dump(self) -> dict[str, str]:
        """Everything this design stores, as text, for the leak and deletion checks."""
        return {}

    def close(self) -> None: ...


class Notebook(Design):
    name = "notebook"
    instructions = ("You can save things for future conversations with the remember tool. Use it for anything "
                    "that will help you serve customers better.")

    def __init__(self, **_):
        self.notes: list[str] = []

    def tools(self, user):
        return [_tool("remember", "Save a note for future conversations.", {"note": {"type": "string"}})]

    def context(self, user, query):
        return list(self.notes)

    def call(self, user, name, args):
        if name == "remember":
            self.notes.append(str(args.get("note", "")))
            return json.dumps({"saved": True})
        return super().call(user, name, args)

    def forget(self, user):
        # What a PoC operator does: delete every note that mentions the customer.
        c = CUSTOMERS[user]
        self.notes = [n for n in self.notes if c["name"].lower() not in n.lower() and c["email"] not in n.lower()]

    def dump(self):
        return {"notebook": "\n".join(self.notes)}


class _Mem0(Design):
    """Mem0 2.2.1 with local models: Ollama for extraction and embeddings, Qdrant on disk, SQLite history."""

    instructions = "You have a memory. Things you remember that may be relevant are listed below."
    shared = False

    def __init__(self, memory_model: str = "qwen3:8b", workdir: str | None = None, **_):
        from mem0 import Memory   # imported here: it is slow to import and only these designs need it
        self.dir = workdir or tempfile.mkdtemp(prefix=f"ep03_{self.name}_")
        self.history_path = os.path.join(self.dir, "history.db")
        self.memory = Memory.from_config({
            "llm": {"provider": "ollama", "config": {"model": memory_model, "temperature": 0.1, "max_tokens": 2000,
                                                     "ollama_base_url": "http://localhost:11434"}},
            "embedder": {"provider": "ollama", "config": {"model": "bge-m3", "embedding_dims": 1024,
                                                          "ollama_base_url": "http://localhost:11434"}},
            "vector_store": {"provider": "qdrant", "config": {"collection_name": "penny", "embedding_model_dims": 1024,
                                                              "path": os.path.join(self.dir, "qdrant"), "on_disk": True}},
            "history_db_path": self.history_path})
        # Mem0's Ollama wrapper has no switch for qwen3's thinking; pass it through the client.
        self.memory.llm.client.chat = functools.partial(self.memory.llm.client.chat, think=False)
        self.adds: list[dict] = []

    def _scope(self, user: str) -> dict:
        email = CUSTOMERS[user]["email"]
        return {"agent_id": "penny"} if self.shared else {"user_id": email}

    def context(self, user, query):
        results = self.memory.search(query, filters=self._scope(user), limit=5)["results"]
        return [r["memory"] for r in results]

    def end_session(self, user, messages):
        talk = [{"role": m["role"], "content": m["content"]} for m in messages
                if m["role"] in ("user", "assistant") and m.get("content")]
        if not talk:
            return
        ids = {"user_id": CUSTOMERS[user]["email"], **({"agent_id": "penny"} if self.shared else {})}
        started = time.time()
        result = self.memory.add(talk, **ids)
        self.adds.append({"user": user, "seconds": round(time.time() - started, 1),
                          "events": [(r.get("event"), r.get("memory")) for r in result.get("results", [])]})

    def forget(self, user):
        # Mem0's documented way to delete a user's memories.
        self.memory.delete_all(user_id=CUSTOMERS[user]["email"])

    def dump(self):
        scopes = [{"agent_id": "penny"}] if self.shared else [{"user_id": c["email"]} for c in CUSTOMERS.values()]
        texts = [r["memory"] for scope in scopes
                 for r in self.memory.get_all(filters=scope, limit=1000)["results"]]
        history = []
        if os.path.exists(self.history_path):
            con = sqlite3.connect(self.history_path)
            history = [" | ".join(str(v) for v in row if v) for row in
                       con.execute("SELECT event, old_memory, new_memory FROM history").fetchall()]
            con.close()
        return {"vector store": "\n".join(texts), "history database": "\n".join(history)}

    def close(self):
        try:
            self.memory.vector_store.client.close()
        except Exception:
            pass


class Mem0User(_Mem0):
    name = "mem0_user"


class Mem0Shared(_Mem0):
    name = "mem0_shared"
    shared = True


class Owned(Design):
    """Memory with an owner. The guarantees come from structure, not from what the model decides to save."""

    name = "owned"
    instructions = ("You can remember this customer's preferences with remember_preference; they are kept for this "
                    "customer only. Address or phone changes go to request_profile_change and take effect after "
                    "verification. Tips about Acme's policies go to suggest_to_staff for review. Acme's policies "
                    "come only from this prompt.")

    def __init__(self, crm=None, **_):
        self.crm = crm
        self.records: list[dict] = []        # {owner, topic, value, source, expires}
        self.review_queue: list[dict] = []   # tips for staff; never shown to Penny

    def tools(self, user):
        return [_tool("remember_preference", "Remember a preference of the logged-in customer, for them only. "
                      "Use display_currency for the currency they want to see amounts in (a code like EUR).",
                      {"topic": {"type": "string", "enum": ["display_currency", "language", "contact_channel", "other"]},
                       "value": {"type": "string"}}),
                _tool("request_profile_change", "Ask to change the logged-in customer's address or phone. "
                      "Takes effect after verification.",
                      {"field": {"type": "string", "enum": ["address", "phone"]}, "value": {"type": "string"}}),
                _tool("suggest_to_staff", "Pass a tip or claim about Acme's policies to staff for review.",
                      {"note": {"type": "string"}})]

    def settings(self, user: str) -> dict:
        """A customer's preferences that code applies: today, the currency amounts are shown in."""
        now = time.time()
        out = {}
        for r in self.records:
            if r["owner"] == user and r["expires"] > now and r["topic"] != "other":
                out[r["topic"]] = r["value"]
        return out

    def context(self, user, query):
        now = time.time()
        name = CUSTOMERS[user]["name"]
        return [f"{name}'s {r['topic'].replace('_', ' ')}: {r['value']} (set by {name} in a {r['source']})"
                if r["topic"] != "other" else f"{name} told you: {r['value']} (in a {r['source']})"
                for r in self.records if r["owner"] == user and r["expires"] > now]

    def call(self, user, name, args):
        if name == "remember_preference":
            topic = str(args.get("topic", "other"))
            value = str(args.get("value", args.get("preference", "")))
            if topic == "display_currency":
                value = value.strip().upper()[:3]
            self.records.append({"owner": user, "topic": topic if topic in ("display_currency", "language",
                                 "contact_channel") else "other", "value": value, "source": "customer chat",
                                 "expires": time.time() + 180 * 86400})
            return json.dumps({"saved": True, "visible_to": CUSTOMERS[user]["email"]})
        if name == "request_profile_change":
            self.crm.request_change(user, str(args.get("field", "")), str(args.get("value", "")))
            return json.dumps({"status": "pending verification", "note": "the profile changes after verification"})
        if name == "suggest_to_staff":
            self.review_queue.append({"author": user, "note": str(args.get("note", ""))})
            return json.dumps({"status": "sent to staff for review"})
        return super().call(user, name, args)

    def forget(self, user):
        self.records = [r for r in self.records if r["owner"] != user]
        self.review_queue = [q for q in self.review_queue if q["author"] != user]

    def dump(self):
        return {"memory records": "\n".join(f"{r['topic']}: {r['value']}" for r in self.records),
                "staff review queue": "\n".join(q["note"] for q in self.review_queue)}


DESIGNS = {"notebook": Notebook, "mem0_user": Mem0User, "mem0_shared": Mem0Shared, "owned": Owned}
