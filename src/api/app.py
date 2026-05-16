"""FastAPI app — wires up routers and serves the frontend."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import litellm
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

# Suppress LiteLLM's "Provider List" info spam — we don't need provider discovery hints in logs
litellm.suppress_debug_info = True

from agent.core import init_agent  # noqa: E402
from agent.db import db  # noqa: E402
from api.routers import init as init_router  # noqa: E402
from api.routers import auth, chat, dashboard, history, monitoring, sessions, settings, users  # noqa: E402


class _InterceptHandler(logging.Handler):
    """Forward stdlib logging records to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


logging.basicConfig(handlers=[_InterceptHandler()], level=logging.INFO, force=True)
for _name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
    logging.getLogger(_name).handlers = [_InterceptHandler()]


def start_event_consumer(app_instance: "FastAPI | None" = None) -> None:
    """Start the SQS event consumer as a background task (idempotent)."""
    import asyncio

    target = app_instance or app
    existing: asyncio.Task | None = getattr(target, "_consumer_task", None)
    if existing and not existing.done():
        return
    from agent.event_consumer import event_consumer_loop

    target._consumer_task = asyncio.create_task(event_consumer_loop())  # type: ignore[attr-defined]
    logger.info("Event consumer task started")


async def stop_event_consumer(app_instance: "FastAPI | None" = None) -> None:
    """Stop the SQS event consumer if it is running."""
    import asyncio

    target = app_instance or app
    existing: asyncio.Task | None = getattr(target, "_consumer_task", None)
    if not existing or existing.done():
        return
    existing.cancel()
    try:
        await existing
    except asyncio.CancelledError:
        pass
    target._consumer_task = None  # type: ignore[attr-defined]
    logger.info("Event consumer task stopped")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    import asyncio

    from config import settings as _cfg

    checkpointer = await db.init()
    from agent.init_store import refresh_init_cache_from_db

    await refresh_init_cache_from_db()
    init_agent(checkpointer)

    poller_task = None
    if _cfg.poll_interval_minutes > 0:
        from agent.poller import polling_loop

        poller_task = asyncio.create_task(polling_loop())
        logger.info("Proactive poller started (interval={}min)", _cfg.poll_interval_minutes)

    # Event consumer — started if explicitly enabled, SQS URL is set, or init wizard completed
    if _cfg.event_consumer_enabled or _cfg.sqs_queue_url:
        start_event_consumer(_app)
    else:
        try:
            from agent.init_store import is_event_infra_enabled

            if is_event_infra_enabled():
                start_event_consumer(_app)
        except Exception:
            pass

    yield

    if poller_task:
        poller_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass

    consumer_task: asyncio.Task | None = getattr(_app, "_consumer_task", None)
    if consumer_task:
        await stop_event_consumer(_app)

    await db.close()


app = FastAPI(title="OpenDevOps Agent", version="0.1.0", lifespan=lifespan)

app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(dashboard.router)
app.include_router(history.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(settings.router)
app.include_router(init_router.router)
app.include_router(monitoring.router)

_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

# Mount compiled JS/CSS assets from the Vite build
if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")


def _serve_index() -> HTMLResponse:
    path = _DIST / "index.html"
    if not path.exists():
        return HTMLResponse(
            "<p style='font-family:sans-serif;padding:2rem'>"
            "Frontend not built yet. Run: <code>cd frontend &amp;&amp; "
            "npm install &amp;&amp; npm run build</code>"
            "</p>",
            status_code=503,
        )
    return HTMLResponse(content=path.read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
async def index():
    return _serve_index()


@app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
async def spa_fallback(full_path: str):
    """Serve index.html for all client-side routes so React Router works on refresh."""
    return _serve_index()
