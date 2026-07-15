from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.ai_studio import router as ai_studio_router
from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.health import router as health_router
from app.api.v1.imports import router as imports_router
from app.api.v1.platform import router as platform_router
from app.api.v1.personal import router as personal_router
from app.api.v1.portal_public import router as portal_public_router
from app.api.v1.realtime import router as realtime_router
from app.api.v1.reports import router as reports_router
from app.api.v1.segments import router as segments_router
from app.api.v1.resources import router as resources_router
from app.api.v1.settings import router as settings_router
from app.core.config import settings
from app.core.store import store
from app.core.observability import RequestObservabilityMiddleware
from app.db.bootstrap import initialize_database
from app.db import realtime as _realtime  # noqa: F401
from app.db.session import SessionLocal
from app.db.store_sync import hydrate_store_state


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.validate_for_process("web")
    if settings.initialize_database:
        initialize_database()
    else:
        with SessionLocal() as db:
            hydrate_store_state(db, store)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Backend API for omnichannel support operations.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestObservabilityMiddleware)
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(ai_studio_router, prefix=settings.api_prefix)
    app.include_router(campaigns_router, prefix=settings.api_prefix)
    app.include_router(conversations_router, prefix=settings.api_prefix)
    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(imports_router, prefix=settings.api_prefix)
    app.include_router(platform_router, prefix=settings.api_prefix)
    app.include_router(personal_router, prefix=settings.api_prefix)
    app.include_router(portal_public_router, prefix=settings.api_prefix)
    app.include_router(realtime_router, prefix=settings.api_prefix)
    app.include_router(reports_router, prefix=settings.api_prefix)
    app.include_router(segments_router, prefix=settings.api_prefix)
    app.include_router(settings_router, prefix=settings.api_prefix)
    app.include_router(resources_router, prefix=settings.api_prefix)

    return app


app = create_app()
