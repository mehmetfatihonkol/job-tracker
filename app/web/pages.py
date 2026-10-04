from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.schemas import ApplicationFilters
from app.services.dashboard import Period, build_dashboard
from app.web.dependencies import ApplicationDep, RepositoryDep
from app.web.templating import templates

RECENT_LIMIT = 8

router = APIRouter(default_response_class=HTMLResponse)


@router.get("/")
def dashboard(
    request: Request,
    repo: RepositoryDep,
    period: Annotated[Period, Query(alias="range")] = Period.LAST_30_DAYS,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "dashboard": build_dashboard(repo, period, date.today()),
            "recent": repo.search(limit=RECENT_LIMIT),
        },
    )


@router.get("/applications")
def applications(
    request: Request,
    repo: RepositoryDep,
    filters: Annotated[ApplicationFilters, Query()],
) -> HTMLResponse:
    companies = repo.company_stats()
    selected = filters.company.casefold() if filters.company else None
    return templates.TemplateResponse(
        request,
        "applications.html",
        {
            "rows": repo.search(status=filters.status, company=filters.company, query=filters.q),
            "filters": filters,
            "companies": companies,
            "selected_company": next(
                (c for c in companies if c.company.casefold() == selected), None
            ),
        },
    )


@router.get("/applications/{application_id}")
def application_detail(
    request: Request, application: ApplicationDep, repo: RepositoryDep
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "detail.html",
        {
            "item": application,
            "company_total": len(repo.search(company=application.company)),
        },
    )


@router.get("/paste")
def paste(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "paste.html")


@router.post("/applications/{application_id}/delete")
def delete_application(application: ApplicationDep, repo: RepositoryDep) -> RedirectResponse:
    repo.delete(application.id)
    return RedirectResponse("/applications", status_code=status.HTTP_303_SEE_OTHER)
