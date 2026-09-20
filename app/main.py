from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db
from app.parse import parse_jobs
from app.schemas import ApplicationIn, ApplicationPatch, BulkSaveRequest, ParseRequest

load_dotenv()

APP_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Job Tracker", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def _ctx(request: Request, **extra):
    return {
        "request": request,
        "statuses": db.STATUSES,
        "sources": db.SOURCES,
        **extra,
    }


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        _ctx(request, stats=db.dashboard_stats(), recent=db.list_applications()[:8]),
    )


@app.get("/applications", response_class=HTMLResponse)
def applications_page(
    request: Request,
    status: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
):
    if status and status not in db.STATUSES:
        status = None
    rows = db.list_applications(status=status, q=q)
    return templates.TemplateResponse(
        "applications.html",
        _ctx(request, rows=rows, status_filter=status or "", q=q or ""),
    )


@app.get("/applications/{app_id}", response_class=HTMLResponse)
def application_detail(request: Request, app_id: int):
    row = db.get_application(app_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return templates.TemplateResponse(
        "detail.html",
        _ctx(request, item=row),
    )


@app.get("/paste", response_class=HTMLResponse)
def paste_page(request: Request):
    return templates.TemplateResponse("paste.html", _ctx(request))


@app.post("/api/parse")
def api_parse(body: ParseRequest):
    jobs, parser, error = parse_jobs(body.text)
    return {"jobs": jobs, "parser": parser, "error": error}


@app.post("/api/applications/bulk")
def api_bulk_save(body: BulkSaveRequest):
    ids = db.insert_many([item.model_dump() for item in body.items])
    return {"ids": ids, "count": len(ids)}


@app.post("/api/applications")
def api_create(body: ApplicationIn):
    app_id = db.insert_application(body.model_dump())
    return db.get_application(app_id)


@app.patch("/api/applications/{app_id}")
def api_patch(app_id: int, body: ApplicationPatch):
    if not db.get_application(app_id):
        raise HTTPException(status_code=404, detail="Not found")
    payload = body.model_dump(exclude_unset=True)
    updated = db.update_application(app_id, payload)
    return updated


@app.delete("/api/applications/{app_id}")
def api_delete(app_id: int):
    if not db.delete_application(app_id):
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@app.post("/applications/{app_id}/delete")
def html_delete(app_id: int):
    db.delete_application(app_id)
    return RedirectResponse("/applications", status_code=303)
