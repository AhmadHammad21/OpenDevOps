"""FastAPI app — wires up routers and serves the frontend."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from loguru import logger

from agent.core import init_agent
from agent.db import db
from api.routers import chat, sessions


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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    checkpointer = await db.init()
    init_agent(checkpointer)
    yield
    await db.close()


app = FastAPI(title="OpenDevOps Agent", version="0.1.0", lifespan=lifespan)

app.include_router(chat.router)
app.include_router(sessions.router)

_STATIC = Path(__file__).parent.parent.parent / "frontend"


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=(_STATIC / "index.html").read_text(encoding="utf-8"))
