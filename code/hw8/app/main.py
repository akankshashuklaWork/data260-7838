"""Part 1 API wrapper: HTTP in, Kafka request/response out."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from app.kafka_rpc import KafkaRPC
from common import log
from config import CONFIG
from fastapi import FastAPI, Response
from pydantic import BaseModel

rpc = KafkaRPC()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await rpc.start()
    log("FASTAPI", f"FastAPI server started at http://127.0.0.1:{CONFIG.port}")
    yield
    await rpc.stop()


app = FastAPI(title="Rental Listing Kafka API", lifespan=lifespan)


class ListingRequest(BaseModel):
    operation: str
    data: dict[str, Any] = {}
    correlation_id: str | None = None  # clients may supply it; otherwise one is created


@app.get("/")
async def home() -> dict[str, Any]:
    return {"service": "rental-listing-kafka-api", "port": CONFIG.port}


@app.post("/listings")
async def listing_operation(request: ListingRequest, response: Response) -> dict[str, Any]:
    result = await rpc.call(request.operation, request.data, request.correlation_id)
    if result.get("error") == "Timed out waiting for the worker":
        response.status_code = 504
    return result
