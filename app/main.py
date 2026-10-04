from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

from app import database
from app.config import Settings, get_settings
from app.services.parsing import ListingParser, OpenAIParser
from app.web import api, pages
from app.web.templating import STATIC_DIR


def build_listing_parser(settings: Settings) -> ListingParser | None:
    if not settings.llm_enabled or settings.openai_api_key is None:
        return None
    client = OpenAI(api_key=settings.openai_api_key.get_secret_value())
    return OpenAIParser(client, settings.openai_model)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        with database.transaction(settings.database_path) as conn:
            database.migrate(conn)
        yield

    app = FastAPI(title="Job Tracker", lifespan=lifespan)
    app.state.settings = settings
    app.state.listing_parser = build_listing_parser(settings)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(pages.router)
    app.include_router(api.router)
    return app


app = create_app()
