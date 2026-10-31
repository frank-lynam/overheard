"""The FastAPI app: the API under /api, and the front end (static files) at /."""

import sqlite3
from importlib.resources import files

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from overheard import __version__
from overheard.api.routes import router
from overheard.config import Settings
from overheard.data import db
from overheard.llm import ResponseStore, build_provider
from overheard.pipeline.simulate import Assumptions


def open_db(settings: Settings) -> sqlite3.Connection:
    """The seeded database (seeded now if it isn't there yet), plus the table for people's own work."""
    if not settings.db_path.exists():
        from overheard.data.generator import seed

        seed(settings.db_path, settings.seed)
    con = db.connect(settings.db_path)
    con.execute("CREATE TABLE IF NOT EXISTS entries (id TEXT PRIMARY KEY, entry TEXT)")
    con.commit()
    return con


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Overheard", version=__version__)
    app.state.settings = settings
    app.state.db = open_db(settings)
    app.state.today = app.state.db.execute("SELECT value FROM meta WHERE key='today'").fetchone()[0]
    app.state.assumptions = Assumptions()
    app.state.store = ResponseStore(settings.llm_responses_path)
    app.state.provider = build_provider(settings, app.state.store)

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True, "version": __version__, "llm_mode": settings.llm_mode}

    app.include_router(router)
    app.mount("/", StaticFiles(directory=str(files("overheard") / "static"), html=True), name="static")
    return app
