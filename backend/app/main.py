import hashlib
import json
import logging
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import router
from app.core.config import settings
from app.core.db import Session, engine
from app.models import Base
from app.retrieval import vector_client

logging.basicConfig(level=logging.INFO, format="%(message)s")
# Avoid provider request bodies and credentials in ordinary logs.
for name in ("httpx", "httpcore", "openai", "huggingface_hub"):
    logging.getLogger(name).setLevel(logging.WARNING)
log = logging.getLogger("papermind.requests")
cfg = settings()
redis = Redis.from_url(cfg.redis_url, decode_responses=True)
windows: dict = defaultdict(lambda: [0, 0])


@asynccontextmanager
async def lifespan(app):
    if cfg.environment != "production":
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    yield
    await redis.aclose()
    await engine.dispose()


app = FastAPI(title="PaperMind", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


def error_response(status, message, code, request_id):
    return JSONResponse(
        status_code=status, content={"error": {"code": code, "message": message, "request_id": request_id}}
    )


@app.middleware("http")
async def request_guard(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    started = time.perf_counter()
    max_body = (
        cfg.max_upload_mb * 1024 * 1024 + 65536 if request.url.path.endswith("/upload") else 1024 * 1024
    )
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > max_body):
        return error_response(413, "Request body is too large", "body_limit", request.state.request_id)
    # Reject oversized chunked uploads before multipart spooling can consume unbounded disk.
    original_receive = request._receive
    received = 0

    async def bounded_receive():
        nonlocal received
        message = await original_receive()
        received += len(message.get("body", b""))
        if received > max_body:
            raise HTTPException(413, "Request body is too large")
        return message

    request._receive = bounded_receive
    if request.url.path not in ("/health/live", "/health/ready"):
        identity = request.client.host if request.client else "unknown"
        bucket = int(time.time() // 60)
        is_auth = request.url.path.startswith("/api/v1/auth/") and request.method == "POST"
        key = (
            "rate:"
            + hashlib.sha256(identity.encode()).hexdigest()[:16]
            + f":{'auth' if is_auth else 'api'}:{bucket}"
        )
        limit = 12 if is_auth else cfg.rate_limit_per_minute
        try:
            if cfg.environment == "production":
                count = await redis.incr(key)
                if count == 1:
                    await redis.expire(key, 70)
            else:
                # ponytail: process-local dev limiter only; production uses Redis across replicas.
                for stale in list(windows):
                    if windows[stale][1] < bucket:
                        del windows[stale]
                windows[key][0] += 1
                windows[key][1] = bucket
                count = windows[key][0]
            if count > limit:
                response = error_response(429, "Rate limit exceeded", "rate_limit", request.state.request_id)
                response.headers["Retry-After"] = "60"
                return response
        except Exception:
            return error_response(
                503, "Rate limiter unavailable", "dependency_unavailable", request.state.request_id
            )
    try:
        response = await call_next(request)
    except HTTPException as exc:
        response = error_response(exc.status_code, str(exc.detail), "request_error", request.state.request_id)
    except Exception as exc:
        log.error(
            json.dumps(
                {
                    "event": "unhandled_error",
                    "request_id": request.state.request_id,
                    "error_type": type(exc).__name__,
                }
            )
        )
        response = error_response(500, "Internal service error", "internal_error", request.state.request_id)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    log.info(
        json.dumps(
            {
                "request_id": request.state.request_id,
                "method": request.method,
                "status": response.status_code,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
    )
    return response


@app.exception_handler(StarletteHTTPException)
async def http_error(request, exc):
    return error_response(
        exc.status_code, str(exc.detail), "http_error", getattr(request.state, "request_id", "")
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Do not echo request input (passwords, prompts, private paper content).
    fields = [".".join(str(i) for i in e["loc"]) for e in exc.errors()]
    return error_response(
        422,
        "Invalid fields: " + ", ".join(fields),
        "validation_error",
        getattr(request.state, "request_id", ""),
    )


@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready():
    async with Session() as db:
        await db.execute(text("SELECT 1"))
    if not cfg.task_eager:
        await redis.ping()
    import asyncio

    await asyncio.to_thread(lambda: vector_client().get_collections())
    return {"status": "ready", "mode": cfg.environment}


app.include_router(router)
