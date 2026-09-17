"""
deblaot -- the backend engine behind MacDebloat.

This is a small local REST API wrapping the same tweak catalog as
MacDebloat.sh, so any frontend -- the desktop PyQt5 app, the mobile web UI
this server also hosts, or anything else -- can drive the same 30-odd
tweaks over HTTP instead of shelling out to the bash script directly.

SECURITY NOTE -- read before running this anywhere but your own machine:
This API can change system settings and will pop native admin-password
prompts on the Mac it runs on. By default it binds to 127.0.0.1 and has no
authentication, because it isn't meant to be reachable from anywhere but
that same machine.

run.sh also supports binding beyond localhost (DEBLAOT_HOST=0.0.0.0), so
you can drive it from an iPhone on the same Wi-Fi via the mobile UI at
'/'. Doing that WITHOUT protection would mean anyone else on that network
could too, so the moment DEBLAOT_TOKEN is set, every request from a
non-localhost address must carry it as `Authorization: Bearer <token>` --
run.sh generates one automatically the first time you ask it to bind
beyond loopback. Requests from 127.0.0.1/::1 (this Mac, including the
desktop GUI) are always trusted and never need the token. If DEBLAOT_TOKEN
is never set, this whole check is a no-op and behavior is exactly what it
was before this existed.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import engine, history, system, tweaks

app = FastAPI(
    title="deblaot",
    description="Backend engine for MacDebloat -- declutter & customize macOS.",
    version="1.0.0",
)

# Kept permissive for local development against the API directly (e.g. a
# tool hitting it from a plain `http://localhost` page). The mobile UI is
# served from this same origin, so it never triggers CORS at all.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEBLAOT_TOKEN = os.environ.get("DEBLAOT_TOKEN", "").strip()
TRUSTED_HOSTS = {"127.0.0.1", "::1"}
# Only these prefixes can read or change anything -- everything else (the
# mobile UI's own HTML/JS/CSS/icons, '/', '/health', API docs) is served
# freely with no token, because a phone has to be able to load the page
# that lets it *enter* the token before it has one, and static assets
# can't change system state regardless of who fetches them. Listing what
# to PROTECT (rather than what to exempt) means a new static file never
# accidentally ends up behind the token check just because nobody added
# it to an allowlist -- the mistake that let this exact bug happen once
# already (static assets were 401ing because '/static/' was allowlisted
# while the files are actually mounted at '/').
PROTECTED_PREFIXES = ("/categories", "/tweaks", "/presets", "/system", "/history")


@app.middleware("http")
async def require_token_for_remote_clients(request: Request, call_next):
    if not DEBLAOT_TOKEN:
        return await call_next(request)  # token never configured -> localhost-only behavior, unchanged

    path = request.url.path
    if not path.startswith(PROTECTED_PREFIXES):
        return await call_next(request)

    client_host = request.client.host if request.client else ""
    if client_host in TRUSTED_HOSTS:
        return await call_next(request)

    auth_header = request.headers.get("authorization", "")
    if auth_header != f"Bearer {DEBLAOT_TOKEN}":
        return JSONResponse({"detail": "Missing or invalid access token"}, status_code=401)
    return await call_next(request)


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


# Serve the mobile web UI from this same origin -- registered last so it
# only catches whatever the API routes above didn't already claim.
# html=True makes it serve static/index.html for '/' itself.
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="mobile-ui")
