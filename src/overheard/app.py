"""The FastAPI app: the API under /api, and the front end (static files) at /."""

import contextlib
import sqlite3
import threading
from importlib.resources import files
from types import SimpleNamespace

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
    con.execute("PRAGMA journal_mode=WAL")  # readers in other threads don't wait on a writer
    con.commit()
    return con


class ThreadConnections:
    """One sqlite connection per thread: requests run in worker threads at the same time, and a single
    shared connection hands garbled rows to concurrent queries."""

    def __init__(self, path) -> None:
        self.path = path
        self.local = threading.local()

    def get(self) -> sqlite3.Connection:
        c = getattr(self.local, "con", None)
        if c is None:
            c = self.local.con = db.connect(self.path)
        return c


@contextlib.asynccontextmanager
async def warm_up(app: FastAPI):
    """The day is computed up front: when the server starts (in mock or replay mode, where it costs nothing),
    a background thread works out every message's analysis and the day's mode-2 reasoning, so the first click
    on Mode 1 or 2 doesn't wait seconds for it. Live mode stays lazy: warming would call the model on every start."""
    if app.state.settings.llm_mode in ("mock", "replay"):
        from overheard.api.routes import mode2_messages

        def warm() -> None:
            try:
                mode2_messages(SimpleNamespace(app=app))
            except Exception:  # a failure here shows up again, properly, on the first real request
                pass

        threading.Thread(target=warm, name="warm-up", daemon=True).start()
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Overheard", version=__version__, lifespan=warm_up)
    app.state.settings = settings
    setup = open_db(settings)
    app.state.today = setup.execute("SELECT value FROM meta WHERE key='today'").fetchone()[0]
    setup.close()
    app.state.db = ThreadConnections(settings.db_path)
    app.state.assumptions = Assumptions()
    # The analysis cache (message id -> bundle) and the lock that keeps one bundle from
    # being computed twice at once: sync routes run in worker threads.
    app.state.analysis_cache = {}
    app.state.analyze_lock = threading.Lock()
    app.state.mode2 = None  # the day-2 computation (and with it every message's analysis); see warm()
    app.state.mode2_messages = None  # each message's mode-2 section, for the queue
    app.state.mode2_lock = threading.Lock()
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
