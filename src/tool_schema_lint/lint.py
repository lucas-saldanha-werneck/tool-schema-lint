"""Rules that check tool definitions (Anthropic or OpenAI style) offline."""
from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import combinations

VAGUE_NAMES = {"run", "do", "execute", "handle", "process", "action", "tool", "call", "helper", "main"}
ENUM_HINTS = {"status", "type", "mode", "kind", "state", "priority", "format", "level", "channel"}
MUTATING = ("create", "delete", "remove", "send", "update", "pay", "cancel", "book", "refund", "transfer", "post")
IDEMPOTENCY_PARAMS = {"idempotency_key", "request_id", "client_request_id", "dedupe_key"}
STOPWORDS = {"the", "a", "an", "to", "of", "for", "and", "or", "in", "on", "is", "this", "that", "with", "by", "from", "use", "when"}


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str  # "error" | "warn" | "info"
    tool: str
    message: str


def _normalize(raw: dict) -> dict:
    """Return {name, description, schema} for either supported format."""
    if raw.get("type") == "function" and isinstance(raw.get("function"), dict):
        fn = raw["function"]
        return {"name": fn.get("name", ""), "description": fn.get("description", ""),
                "schema": fn.get("parameters") or {}}
    return {"name": raw.get("name", ""), "description": raw.get("description", ""),
            "schema": raw.get("input_schema") or raw.get("parameters") or {}}


def load_tools(data) -> list[dict]:
    if isinstance(data, dict) and "tools" in data:
        data = data["tools"]
    if not isinstance(data, list):
        raise ValueError("expected a list of tools or an object with a 'tools' list")
    return [_normalize(t) for t in data]


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in STOPWORDS and len(w) > 2}


def _tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[_\-\s]+|(?<=[a-z])(?=[A-Z])", name) if t]


def lint_tools(tools: list[dict], overlap_threshold: float = 0.6) -> list[Finding]:
    out: list[Finding] = []
    seen: dict[str, int] = {}
    for t in tools:
        name = t["name"] or "<unnamed>"
        seen[name] = seen.get(name, 0) + 1
        desc = (t["description"] or "").strip()
        schema = t["schema"]
        props = schema.get("properties", {}) or {}
        required = schema.get("required")

        if not t["name"]:
            out.append(Finding("TS000", "error", name, "Tool has no name."))
        toks = [x.lower() for x in _tokens(t["name"])]
        if t["name"] and (set(toks) <= VAGUE_NAMES or re.fullmatch(r"(tool|function|fn)_?\d+", t["name"].lower())):
            out.append(Finding("TS001", "warn", name, "Name says nothing about what the tool does."))
        if len(desc.split()) < 5:
            out.append(Finding("TS002", "error", name, "Description is missing or shorter than 5 words."))
        for p, spec in props.items():
            spec = spec if isinstance(spec, dict) else {}
            if not (spec.get("description") or "").strip():
                out.append(Finding("TS003", "warn", name, f"Parameter '{p}' has no description."))
            if spec.get("type") == "string" and "enum" not in spec and p.lower() in ENUM_HINTS:
                out.append(Finding("TS004", "warn", name, f"Parameter '{p}' is a free string; it looks like it should be an enum."))
        if props and not required:
            out.append(Finding("TS005", "warn", name, "Has parameters but no 'required' list."))
        for r in required or []:
            if r not in props:
                out.append(Finding("TS006", "error", name, f"'required' names '{r}', which is not in properties."))
        if toks and toks[0] in MUTATING and not (IDEMPOTENCY_PARAMS & set(props)):
            out.append(Finding("TS007", "info", name,
                               "Changes state but has no idempotency key; a retry may run it twice."))

    for n, c in seen.items():
        if c > 1:
            out.append(Finding("TS008", "error", n, f"Tool name is defined {c} times."))

    named = [t for t in tools if t["name"]]
    for a, b in combinations(named, 2):
        if a["name"] == b["name"]:
            continue
        wa, wb = _words(a["description"] or ""), _words(b["description"] or "")
        if wa and wb:
            score = len(wa & wb) / len(wa | wb)
            if score >= overlap_threshold:
                out.append(Finding("TS009", "warn", a["name"],
                                   f"Description overlaps {score:.0%} with '{b['name']}'; an agent may pick the wrong one."))
    return out
