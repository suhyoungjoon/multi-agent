from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from studio import compact_action, tmux_control, watchdog_loop, wiki_bridge
from studio.auth import require_token
from studio.roles import load_roles

app = FastAPI(title="Advanced Agent Studio")


@app.get("/api/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/status", dependencies=[Depends(require_token)])
def get_status() -> dict:
    watchdog_loop.tick()
    return {"panes": watchdog_loop.STATE.panes}


class WatchdogSettings(BaseModel):
    stuck_check_enabled: bool


@app.get("/api/watchdog/settings", dependencies=[Depends(require_token)])
def get_watchdog_settings() -> dict:
    return {"stuck_check_enabled": watchdog_loop.STATE.stuck_check_enabled}


@app.post("/api/watchdog/settings", dependencies=[Depends(require_token)])
def set_watchdog_settings(settings: WatchdogSettings) -> dict:
    watchdog_loop.STATE.stuck_check_enabled = settings.stuck_check_enabled
    return {"stuck_check_enabled": watchdog_loop.STATE.stuck_check_enabled}


@app.post("/api/pane/{idx}/check", dependencies=[Depends(require_token)])
def check_pane(idx: int) -> dict:
    return watchdog_loop.check_pane_now(idx)


@app.post("/api/pane/{idx}/wake", dependencies=[Depends(require_token)])
def wake_pane(idx: int) -> dict:
    tmux_control.wake(idx)
    return {"ok": True}


@app.post("/api/pane/{idx}/restart", dependencies=[Depends(require_token)])
def restart_pane(idx: int) -> dict:
    role_text = load_roles().get(idx)
    if role_text is None:
        raise HTTPException(status_code=404, detail=f"no role text defined for pane {idx} in roles.yaml")
    tmux_control.reinject_role(idx, role_text)
    return {"ok": True}


@app.post("/api/pane/{idx}/compact", dependencies=[Depends(require_token)])
def compact_pane(idx: int) -> dict:
    return compact_action.trigger_compact(idx)


@app.get("/api/wiki/hot", dependencies=[Depends(require_token)])
def get_hot_cache() -> dict:
    return {"content": wiki_bridge.read_hot_cache()}


@app.get("/api/wiki/search", dependencies=[Depends(require_token)])
def get_wiki_search(q: str) -> dict:
    return {"results": wiki_bridge.search_wiki(q)}


class SaveNoteRequest(BaseModel):
    domain: str
    title: str
    content: str
    tags: list[str] = []


@app.post("/api/wiki/save", dependencies=[Depends(require_token)])
def post_wiki_save(req: SaveNoteRequest) -> dict:
    path = wiki_bridge.save_note(req.domain, req.title, req.content, req.tags)
    return {"path": str(path)}


# Static file mount MUST be registered last. Starlette matches routes in
# registration order and Mount("/") matches every path — mounting it before
# the /api/... routes above would swallow every request (including
# /api/health) before those routes ever got a chance to match.
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
