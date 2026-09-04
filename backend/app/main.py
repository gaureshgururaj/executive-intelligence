from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.articles import router as articles_router
from app.api.health import router as health_router
from app.api.papers import router as papers_router
from app.api.recommendations import router as recommendations_router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="AI Executive Intelligence Platform")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    application.include_router(articles_router)
    application.include_router(papers_router)
    application.include_router(recommendations_router)
    return application


app = create_app()
