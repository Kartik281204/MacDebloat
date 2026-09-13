"""
deblaot -- the backend engine behind MacDebloat.

This is a small local REST API wrapping the same tweak catalog as
MacDebloat.sh, so any future frontend (a native macOS app, a menu-bar app,
a web dashboard) can drive the same 30-odd tweaks over HTTP instead of
shelling out to the bash script directly.

SECURITY NOTE -- read before running this anywhere but your own machine:
This API can change system settings and will pop native admin-password
prompts on the Mac it runs on. It binds to 127.0.0.1 by default (see
run.sh) and has no authentication of its own, because it isn't meant to
be reachable from anywhere but that same machine. Do not put this behind
a public port, a tunnel, or 0.0.0.0 without adding real auth in front of
it first.
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import engine, history, system, tweaks

app = FastAPI(
    title="deblaot",
    description="Backend engine for MacDebloat -- declutter & customize macOS.",
    version="1.0.0",
)

# Local-only by design -- see the module docstring above.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ApplyBody(BaseModel):
    param: Optional[str] = None
    confirm_experimental: bool = False


def _tweak_out(t: tweaks.Tweak) -> dict:
    return {
        "id": t.id,
        "category": t.category,
        "title": t.title,
        "description": t.description,
        "requires_admin": t.requires_admin,
        "experimental": t.experimental,
        "parameters": t.parameters,
    }


@app.get("/health")
def health():
    return {"status": "ok", "is_macos": system.is_macos()}


@app.get("/system")
def get_system():
    return system.get_system_info()


@app.get("/categories")
def get_categories():
    return [
        {
            "id": cat_id,
            "title": title,
            "tweak_count": sum(1 for t in tweaks.REGISTRY.values() if t.category == cat_id),
        }
        for cat_id, title in tweaks.CATEGORIES.items()
    ]


@app.get("/tweaks")
def get_tweaks(category: Optional[str] = None):
    if category and category not in tweaks.CATEGORIES:
        raise HTTPException(404, f"Unknown category: {category}")
    items = tweaks.REGISTRY.values()
    if category:
        items = [t for t in items if t.category == category]
    return [_tweak_out(t) for t in items]


@app.get("/presets")
def get_presets():
    return {
        "recommended": {
            "description": "Privacy & clutter fixes most people want; nothing destructive.",
            "tweak_ids": tweaks.RECOMMENDED_PRESET,
        },
        "all": {
            "description": "Every non-parameterized tweak, including experimental ones and app removal.",
            "tweak_ids": [t.id for t in tweaks.REGISTRY.values() if not t.parameters],
        },
    }


@app.post("/tweaks/{tweak_id}/apply")
def apply_tweak(tweak_id: str, body: ApplyBody = ApplyBody()):
    t = tweaks.REGISTRY.get(tweak_id)
    if not t:
        raise HTTPException(404, f"Unknown tweak: {tweak_id}")
    if t.experimental and not body.confirm_experimental:
        raise HTTPException(400, "This tweak is experimental -- resend with confirm_experimental: true")
    if t.parameters and body.param not in t.parameters:
        raise HTTPException(400, f"This tweak needs 'param' to be one of {t.parameters}")

    run_id = history.new_run_id()
    ok, message = t.apply_fn(run_id, body.param)
    return {"id": tweak_id, "run_id": run_id, "success": ok, "message": message}


@app.post("/categories/{category_id}/apply")
def apply_category(category_id: str):
    if category_id not in tweaks.CATEGORIES:
        raise HTTPException(404, f"Unknown category: {category_id}")
    run_id = history.new_run_id()
    results = []
    for t in tweaks.REGISTRY.values():
        if t.category == category_id and not t.parameters and not t.experimental:
            ok, message = t.apply_fn(run_id, None)
            results.append({"id": t.id, "success": ok, "message": message})
    return {"run_id": run_id, "results": results}


@app.post("/presets/{preset_id}/apply")
def apply_preset(preset_id: str):
    presets = get_presets()
    if preset_id not in presets:
        raise HTTPException(404, f"Unknown preset: {preset_id}")
    run_id = history.new_run_id()
    results = []
    for tid in presets[preset_id]["tweak_ids"]:
        t = tweaks.REGISTRY[tid]
        ok, message = t.apply_fn(run_id, None)
        results.append({"id": tid, "success": ok, "message": message})
    return {"run_id": run_id, "results": results}


@app.get("/history/runs")
def get_runs(limit: int = 20):
    rows = history.list_runs(limit)
    return [
        {"run_id": r[0], "started": r[1], "action_count": r[2], "reverted_count": r[3] or 0}
        for r in rows
    ]


@app.get("/history/runs/{run_id}")
def get_run_detail(run_id: str):
    rows = history.get_actions_for_run(run_id)
    if not rows:
        raise HTTPException(404, f"No such run: {run_id}")
    return [
        {
            "action_id": r[0], "action": r[1], "domain": r[2], "key": r[3],
            "prior_value": r[4], "prior_type": r[5], "requires_admin": bool(r[6]),
            "reverted": bool(r[8]),
        }
        for r in rows
    ]


class RevertBody(BaseModel):
    run_id: Optional[str] = None


@app.post("/history/revert")
def revert(body: RevertBody = RevertBody()):
    run_id = body.run_id or history.latest_run_id()
    if not run_id:
        raise HTTPException(404, "No history to revert")
    rows = history.get_actions_for_run(run_id)
    if not rows:
        raise HTTPException(404, f"No such run: {run_id}")

    reverted, errors = 0, []
    for row in rows:
        if row[-1]:  # already reverted
            continue
        if engine.revert_action_row(row):
            reverted += 1
        else:
            errors.append(f"Failed to revert action {row[0]} ({row[1]} {row[2]}.{row[3]})")
    return {"run_id": run_id, "reverted_count": reverted, "errors": errors}
