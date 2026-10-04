import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app import database
from app.config import Settings
from app.repository import ApplicationRepository
from app.schemas import Application
from app.services.parsing import ListingParser


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_connection(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[sqlite3.Connection]:
    with database.transaction(settings.database_path) as conn:
        yield conn


def get_repository(
    conn: Annotated[sqlite3.Connection, Depends(get_connection)],
) -> ApplicationRepository:
    return ApplicationRepository(conn)


def get_listing_parser(request: Request) -> ListingParser | None:
    parser: ListingParser | None = request.app.state.listing_parser
    return parser


RepositoryDep = Annotated[ApplicationRepository, Depends(get_repository)]
ListingParserDep = Annotated[ListingParser | None, Depends(get_listing_parser)]


def get_application_or_404(application_id: int, repo: RepositoryDep) -> Application:
    application = repo.get(application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return application


ApplicationDep = Annotated[Application, Depends(get_application_or_404)]
