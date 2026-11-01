"""The FastAPI app: the API under /api, and the front end (static files) at /."""

import sqlite3
import threading
from importlib.resources import files

from fastapi import FastAPI
from fastapi.responses import FileResponse
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
    con.execute(
        "CREATE TABLE IF NOT EXISTS analysis (voicemail TEXT NOT NULL, task TEXT NOT NULL, model TEXT, "
        "data TEXT NOT NULL, provenance TEXT NOT NULL, PRIMARY KEY (voicemail, task))"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS corrections (id INTEGER PRIMARY KEY AUTOINCREMENT, voicemail TEXT NOT NULL, "
        "task TEXT NOT NULL, field TEXT NOT NULL, value TEXT, provenance TEXT NOT NULL, at TEXT)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS resolutions (voicemail TEXT PRIMARY KEY, state TEXT NOT NULL, reply TEXT, "
        "provenance TEXT, at TEXT)"
    )
    con.commit()
    return con


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Overheard", version=__version__)
    app.state.settings = settings
    app.state.db = open_db(settings)
    app.state.today = app.state.db.execute("SELECT value FROM meta WHERE key='today'").fetchone()[0]
    app.state.assumptions = Assumptions()
    # The analysis cache (message id -> bundle) and the lock that guards the shared
    # connection while a bundle is (re)computed: sync routes run in worker threads,
    # so a sqlite connection must never be touched by two of them at once.
    app.state.analysis_cache = {}
    app.state.analyze_lock = threading.Lock()
    app.state.mode2 = None  # the day-2 computation, computed up front on first request
    app.state.store = ResponseStore(settings.llm_responses_path)
    app.state.provider = build_provider(settings, app.state.store)

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True, "version": __version__, "llm_mode": settings.llm_mode}

    app.include_router(router)
    static_dir = files("overheard") / "static"

    @app.get("/present", include_in_schema=False)
    async def present() -> FileResponse:
        # The presenter deck. StaticFiles(html=True) only serves /present.html, so /present needs a route.
        return FileResponse(str(static_dir / "present.html"))

    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    return app
