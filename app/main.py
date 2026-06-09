from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import close_pool, init_pool
from app.routers import (
    admin,
    announcements,
    assessments,
    auth,
    blogs,
    chat,
    chat_ws,
    courses,
    dashboard,
    files,
    forum,
    gamification,
    health,
    notifications,
    onboarding,
    practice,
    reports,
    sections,
    teams,
    users,
)
from app.utils.cloudinary import configure_cloudinary


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_cloudinary()
    init_pool()
    yield
    close_pool()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(users.router, prefix=settings.api_prefix)
    app.include_router(notifications.router, prefix=settings.api_prefix)
    app.include_router(chat.router, prefix=settings.api_prefix)
    app.include_router(chat_ws.router, prefix=settings.api_prefix)
    app.include_router(files.router, prefix=settings.api_prefix)
    app.include_router(courses.router, prefix=settings.api_prefix)
    app.include_router(onboarding.router, prefix=settings.api_prefix)
    app.include_router(sections.router, prefix=settings.api_prefix)
    app.include_router(blogs.router, prefix=settings.api_prefix)
    app.include_router(dashboard.router, prefix=settings.api_prefix)
    app.include_router(forum.router, prefix=settings.api_prefix)
    app.include_router(reports.router, prefix=settings.api_prefix)
    app.include_router(teams.router, prefix=settings.api_prefix)
    app.include_router(assessments.router, prefix=settings.api_prefix)
    app.include_router(practice.router, prefix=settings.api_prefix)
    app.include_router(admin.router, prefix=settings.api_prefix)
    app.include_router(gamification.router, prefix=settings.api_prefix)
    app.include_router(announcements.router, prefix=settings.api_prefix)

    return app


app = create_app()
