"""The FastAPI app: the API under /api, and the front end (static files) at /."""

from importlib.resources import files

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from overheard import __version__
from overheard.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Overheard", version=__version__)
    app.state.settings = settings

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True, "version": __version__, "llm_mode": settings.llm_mode}

    app.mount("/", StaticFiles(directory=str(files("overheard") / "static"), html=True), name="static")
    return app
