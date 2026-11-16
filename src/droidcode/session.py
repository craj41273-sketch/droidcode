"""Sessions and the turn loop.

A session is a goal, a transcript, and a context budget. The loop is
model-agnostic: it asks a `Model` for the next tool call, executes it through
the registry, records the result, and stops when the model returns nothing.
Real providers plug in by implementing `Model`; `ScriptedModel` and
`AuditFirstModel` make the loop testable without a network call.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from .registry import ToolRegistry, ToolResult


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"name": self.name, "arguments": self.arguments}


@dataclass
class Step:
    index: int
    thought: str = ""
    call: ToolCall | None = None
    result: ToolResult | None = None

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "thought": self.thought,
            "call": self.call.to_dict() if self.call else None,
            "result": self.result.to_dict() if self.result else None,
        }


def estimate_tokens(payload: Any) -> int:
    """Rough 4-chars-per-token estimate; replaced by the provider's count later."""
    return max(1, len(json.dumps(payload, default=str)) // 4)


@dataclass
class Session:
    goal: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    steps: list[Step] = field(default_factory=list)
    budget_tokens: int = 200_000
    status: str = "open"
    stop_reason: str = ""

    @property
    def used_tokens(self) -> int:
        return sum(estimate_tokens(step.to_dict()) for step in self.steps)

    @property
    def over_budget(self) -> bool:
        return self.used_tokens > self.budget_tokens

    def record(self, thought: str, call: ToolCall | None, result: ToolResult | None) -> Step:
        step = Step(index=len(self.steps), thought=thought, call=call, result=result)
        self.steps.append(step)
        return step

    def observations(self) -> list[dict]:
        return [
            {"call": step.call.name, "output": step.result.output, "ok": step.result.ok}
            for step in self.steps
            if step.call and step.result
        ]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status,
            "stop_reason": self.stop_reason,
            "used_tokens": self.used_tokens,
            "budget_tokens": self.budget_tokens,
            "steps": [step.to_dict() for step in self.steps],
        }


class Model(Protocol):
    def propose(self, session: Session) -> ToolCall | None: ...


class ScriptedModel:
    """Plays back a fixed list of calls; used by tests and evals."""

    def __init__(self, calls: list[ToolCall]) -> None:
        self.calls = list(calls)
        self._index = 0

    def propose(self, session: Session) -> ToolCall | None:
        if self._index >= len(self.calls):
            return None
        call = self.calls[self._index]
        self._index += 1
        return call


class AuditFirstModel:
    """A deterministic policy: audit, then capture evidence, then stop.

    It stands in for an LLM during CI so the harness itself is testable, and it
    doubles as the fallback path when no provider is configured.
    """

    def __init__(self) -> None:
        self._stage = 0

    def propose(self, session: Session) -> ToolCall | None:
        self._stage += 1
        if self._stage == 1:
            return ToolCall("design.audit", {})
        if self._stage == 2:
            return ToolCall("screen.capture", {"name": f"session-{session.id}"})
        return None


def run_session(
    session: Session,
    model: Model,
    registry: ToolRegistry,
    max_turns: int = 12,
) -> Session:
    session.status = "running"
    for _ in range(max_turns):
        if session.over_budget:
            session.status = "stopped"
            session.stop_reason = "context budget exhausted"
            return session
        call = model.propose(session)
        if call is None:
            session.status = "done"
            session.stop_reason = "model finished"
            return session
        result = registry.call(call.name, call.arguments)
        session.record("", call, result)
    session.status = "stopped"
    session.stop_reason = f"hit max_turns={max_turns}"
    return session
