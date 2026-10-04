from pathlib import Path

from fastapi.templating import Jinja2Templates
from jinja2 import StrictUndefined

from app.domain import FREQUENT_COMPANY_THRESHOLD, Source, Status
from app.services.dashboard import Period

APP_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"


def static_url(path: str) -> str:
    """Versioned URL so browsers pick up asset changes without a hard refresh."""
    version = int((STATIC_DIR / path).stat().st_mtime)
    return f"/static/{path}?v={version}"


templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.undefined = StrictUndefined
templates.env.globals.update(
    static_url=static_url,
    frequent_company_threshold=FREQUENT_COMPANY_THRESHOLD,
    Status=Status,
    statuses=list(Status),
    sources=list(Source),
    periods=list(Period),
)
