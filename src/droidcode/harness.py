"""The harness object: owns a device, a registry, and the sessions that use them.

Both the CLI and the daemon drive this; keeping it in one place is what stops
the two front ends from drifting apart.
"""

from __future__ import annotations

from pathlib import Path

from .audit import Auditor, run_matrix, summarise
from .device.base import DeviceBackend
from .device.mock import MockDevice, load_scenario
from .registry import PermissionPolicy, ToolRegistry, build_registry
from .session import AuditFirstModel, Session, run_session
from .tokens import DesignTokens


class Harness:
    def __init__(
        self,
        device: DeviceBackend,
        tokens: DesignTokens | None = None,
        package: str = "",
        screenshots_dir: str | Path = "artifacts/screens",
        policy: PermissionPolicy | None = None,
    ) -> None:
        self.device = device
        self.tokens = tokens or DesignTokens()
        self.package = package
        self.screenshots_dir = screenshots_dir
        self.registry: ToolRegistry = build_registry(
            device,
            tokens=self.tokens,
            package=package,
            screenshots_dir=screenshots_dir,
            policy=policy,
        )
        self.sessions: dict[str, Session] = {}
        # The device is the expensive resource; the harness starts it once.
        self.device.start()

    # -- construction ------------------------------------------------------
    @classmethod
    def from_scenario(
        cls,
        scenario: str | Path | dict | None,
        tokens: DesignTokens | None = None,
        **kwargs,
    ) -> "Harness":
        data = load_scenario(scenario)
        return cls(MockDevice(data), tokens=tokens, package=data.get("package", ""), **kwargs)

    # -- operations --------------------------------------------------------
    def audit(self, screenshots_dir: str | Path | None = None) -> dict:
        report = Auditor(self.device, tokens=self.tokens, package=self.package).run(
            screenshots_dir=screenshots_dir or self.screenshots_dir
        )
        return report.to_dict()

    def audit_matrix(self, scenarios: list[dict]) -> dict:
        devices = [MockDevice(scenario) for scenario in scenarios]
        reports = run_matrix(devices, tokens=self.tokens, package=self.package)
        return {
            "reports": [report.to_dict() for report in reports],
            "summary": summarise(reports),
        }

    def start_session(self, goal: str, budget_tokens: int = 200_000) -> Session:
        session = Session(goal=goal, budget_tokens=budget_tokens)
        self.sessions[session.id] = session
        return session

    def run_session(self, session: Session, model=None, max_turns: int = 12) -> Session:
        return run_session(session, model or AuditFirstModel(), self.registry, max_turns=max_turns)

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        return self.registry.call(name, arguments or {}).to_dict()
