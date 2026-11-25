"""Create the FastAPI application for Ask Your Repo."""

from fastapi import FastAPI

from ask_repo.api.routes.health import router as health_router


def create_app() -> FastAPI:
    """Build the application and register its HTTP routes."""
    app = FastAPI(title="Ask Your Repo")
    app.include_router(health_router)
    return app


app = create_app()
