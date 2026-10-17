"""FastAPI application entry point for DATA 260 Homework 6."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import ensure_database_schema, get_client
from .routes.listings import router as listings_router
from .routes.memory_routes import router as memory_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_database_schema()
    yield
    get_client().close()


settings = get_settings()
app = FastAPI(title="Rental Housing Listings Memory API", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(listings_router)
app.include_router(memory_router)


@app.get("/")
def health() -> dict:
    return {
        "status": "ok",
        "service": "rental-housing-memory",
        "database": settings.mongodb_db,
        "port": settings.port_base,
        "model": settings.model_name,
    }
