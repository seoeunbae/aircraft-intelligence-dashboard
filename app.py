import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from db import create_datastore
from api.chat import get_runner, router as chat_router
from api.data import router as data_router

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.datastore = create_datastore(settings)
    get_runner()  # warm up ADK runner at startup
    yield

app = FastAPI(title="Aircraft Intelligence Dashboard", lifespan=lifespan)
app.include_router(chat_router, prefix="/api")
app.include_router(data_router, prefix="/api")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
