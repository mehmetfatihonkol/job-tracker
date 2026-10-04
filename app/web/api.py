from datetime import date

from fastapi import APIRouter, HTTPException, Response, status

from app.schemas import (
    Application,
    ApplicationCreate,
    ApplicationUpdate,
    BulkCreateRequest,
    BulkCreateResponse,
    CompanyStats,
    ParseRequest,
    ParseResponse,
)
from app.services.parsing import parse_listings
from app.web.dependencies import ApplicationDep, ListingParserDep, RepositoryDep

router = APIRouter(prefix="/api", tags=["api"])


@router.post("/parse")
def parse(body: ParseRequest, llm: ListingParserDep) -> ParseResponse:
    result = parse_listings(body.text, date.today(), llm)
    return ParseResponse(jobs=result.jobs, parser=result.parser, error=result.error)


@router.get("/companies")
def list_companies(repo: RepositoryDep) -> list[CompanyStats]:
    return repo.company_stats()


@router.post("/applications", status_code=status.HTTP_201_CREATED)
def create_application(body: ApplicationCreate, repo: RepositoryDep) -> Application:
    return repo.create(body)


@router.post("/applications/bulk", status_code=status.HTTP_201_CREATED)
def create_applications(body: BulkCreateRequest, repo: RepositoryDep) -> BulkCreateResponse:
    created = repo.create_many(body.items)
    return BulkCreateResponse(ids=[app.id for app in created], count=len(created))


@router.patch("/applications/{application_id}")
def update_application(
    application: ApplicationDep, body: ApplicationUpdate, repo: RepositoryDep
) -> Application:
    updated = repo.update(application.id, body)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return updated


@router.delete("/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application: ApplicationDep, repo: RepositoryDep) -> Response:
    repo.delete(application.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
