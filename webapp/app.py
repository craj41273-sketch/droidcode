"""droidcode web service.

A thin HTTP shell over the harness, small enough for a free hosting tier: it
exposes the tool surface, runs audits against the bundled scenarios, and renders
one server-side page so the project can be looked at without installing it.

    uvicorn webapp.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from droidcode.audit import Auditor
from droidcode.device.mock import MockDevice, load_scenario
from droidcode.registry import build_registry
from droidcode.tokens import DesignTokens

from .page import render_page

ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "evals" / "tasks"
TOKENS_PATH = ROOT / "evals" / "tokens.json"

app = FastAPI(
    title="droidcode",
    description="Agentic coding harness for Android phone UI/UX design and testing",
    version="0.1.0",
)


@lru_cache(maxsize=1)
def tokens() -> DesignTokens:
    return DesignTokens.load(TOKENS_PATH)


@lru_cache(maxsize=1)
def scenarios() -> dict[str, dict]:
    found: dict[str, dict] = {}
    for path in sorted(TASKS_DIR.glob("*.json")):
        task = json.loads(path.read_text())
        found[task["id"]] = task
    return found


def audit_scenario(scenario_id: str) -> dict:
    task = scenarios().get(scenario_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"unknown scenario {scenario_id!r}")
    device = MockDevice(load_scenario(task.get("scenario")))
    report = Auditor(device, tokens=tokens(), package=task.get("package", "")).run()
    payload = report.to_dict()
    payload["goal"] = task.get("goal", "")
    payload["scenario_id"] = scenario_id
    return payload


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "scenarios": len(scenarios())}


@app.get("/api/scenarios")
def list_scenarios() -> list[dict]:
    return [
        {
            "id": scenario_id,
            "goal": task.get("goal", ""),
            "widgets": len(task.get("scenario", {}).get("widgets", [])),
        }
        for scenario_id, task in scenarios().items()
    ]


@app.get("/api/audit/{scenario_id}")
def get_audit(scenario_id: str) -> JSONResponse:
    return JSONResponse(audit_scenario(scenario_id))


@app.get("/api/tools")
def list_tools() -> list[dict]:
    device = MockDevice(load_scenario(scenarios()["clean_profile_screen"].get("scenario")))
    registry = build_registry(device, tokens=tokens())
    return registry.specs()


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    reports = [audit_scenario(scenario_id) for scenario_id in scenarios()]
    return HTMLResponse(render_page(reports))
