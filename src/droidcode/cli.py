"""`droidcode` command line: audit a screen, run a session, serve a daemon, score evals."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .daemon import serve
from .harness import Harness
from .tokens import DesignTokens


def _harness(args) -> Harness:
    tokens = DesignTokens.load(args.tokens) if args.tokens else DesignTokens()
    if args.adb:
        from .device.adb import AdbDevice

        device = AdbDevice(serial=args.serial)
    else:
        device = None
    if device is not None:
        return Harness(device, tokens=tokens, package=args.package, screenshots_dir=args.screenshots)
    return Harness.from_scenario(args.scenario, tokens=tokens, screenshots_dir=args.screenshots)


def cmd_tools(args) -> int:
    harness = _harness(args)
    print(json.dumps(harness.registry.specs(), indent=2))
    return 0


def cmd_audit(args) -> int:
    harness = _harness(args)
    report = harness.audit(args.screenshots)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        from .audit import AuditReport
        from .protocol import Finding

        findings = [Finding.from_dict(item) for item in report["findings"]]
        printable = AuditReport(
            device_key=report["device_key"],
            spec=report["spec"],
            findings=findings,
            nodes_seen=report["nodes_seen"],
        )
        print(printable.to_markdown())
    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2))
        print(f"\nwrote {target}", file=sys.stderr)
    return 0 if report["by_severity"]["critical"] == 0 else 1


def cmd_session(args) -> int:
    harness = _harness(args)
    session = harness.start_session(args.goal, budget_tokens=args.budget)
    harness.run_session(session, max_turns=args.max_turns)
    print(json.dumps(session.to_dict(), indent=2))
    return 0


def cmd_daemon(args) -> int:
    harness = _harness(args)
    print(f"droidcode daemon listening on {args.socket}", file=sys.stderr)
    serve(harness, args.socket)
    return 0


def cmd_eval(args) -> int:
    from .evals.runner import run_evals

    result = run_evals(Path(args.dir), tokens_path=args.tokens)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] == result["tasks"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="droidcode", description=__doc__)
    parser.add_argument("--version", action="version", version=f"droidcode {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(target: argparse.ArgumentParser) -> None:
        target.add_argument("--scenario", help="mock device scenario JSON (default: empty screen)")
        target.add_argument("--tokens", help="design tokens JSON")
        target.add_argument("--screenshots", default="artifacts/screens", help="screenshot output directory")
        target.add_argument("--package", default="", help="app package, enables frame statistics")
        target.add_argument("--adb", action="store_true", help="use a real device over adb")
        target.add_argument("--serial", default=None, help="adb serial")

    tools = sub.add_parser("tools", help="list the tool surface")
    common(tools)
    tools.set_defaults(func=cmd_tools)

    audit = sub.add_parser("audit", help="audit one screen configuration")
    common(audit)
    audit.add_argument("--json", action="store_true", help="emit JSON instead of Markdown")
    audit.add_argument("--out", help="write the JSON report here")
    audit.set_defaults(func=cmd_audit)

    session = sub.add_parser("session", help="run a goal through the turn loop")
    common(session)
    session.add_argument("--goal", required=True)
    session.add_argument("--budget", type=int, default=200_000)
    session.add_argument("--max-turns", type=int, default=12)
    session.set_defaults(func=cmd_session)

    daemon = sub.add_parser("daemon", help="serve the harness on a unix socket")
    common(daemon)
    daemon.add_argument("--socket", default="/tmp/droidcode.sock")
    daemon.set_defaults(func=cmd_daemon)

    evals = sub.add_parser("eval", help="score the harness against eval tasks")
    evals.add_argument("--dir", default="evals/tasks")
    evals.add_argument("--tokens", default=None)
    evals.set_defaults(func=cmd_eval)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
