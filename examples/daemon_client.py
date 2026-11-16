"""Talk to a running droidcode daemon.

    droidcode daemon --socket /tmp/droidcode.sock &
    python examples/daemon_client.py /tmp/droidcode.sock
"""

import json
import sys

from droidcode.client import DaemonClient


def main(socket_path: str) -> None:
    client = DaemonClient(socket_path)
    print("device:", client.ping()["device"])
    print("tools:", ", ".join(spec["name"] for spec in client.tools()))

    session_id = client.create_session("audit the checkout screen")
    result = client.run_session(session_id, script=[{"name": "design.audit"}])
    findings = result["steps"][0]["result"]["output"]["findings"]
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/droidcode.sock")
