import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from arq import create_pool
from app.routers import upload, chat, thesis, journal, companies, notes
from app.config import settings
from app.utils.logger import logger
from app.worker import _redis_settings_from_url


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One shared arq connection pool for the whole app's lifetime, instead
    # of upload.py opening a fresh Redis connection on every request —
    # same reasoning as the get_supabase() singleton fix.
    app.state.arq_pool = await create_pool(_redis_settings_from_url(settings.redis_url))
    logger.info("arq pool connected (background job queue ready)")
    yield
    await app.state.arq_pool.close()
    logger.info("arq pool closed")


app = FastAPI(title="StockSense API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    method = request.method
    path = request.url.path
    client_ip = request.client.host if request.client else "unknown"

    logger.info(f"-> {method} {path} | Client IP: {client_ip}")

    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        status_code = response.status_code

        log_msg = f"<- {method} {path} | Status: {status_code} | Duration: {process_time:.2f}ms"
        if status_code >= 400:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return response
    except Exception as exc:
        process_time = (time.time() - start_time) * 1000
        logger.exception(f"❌ {method} {path} failed | Error: {str(exc)} | Duration: {process_time:.2f}ms")
        raise exc

app.include_router(upload.router,    prefix="/api/upload",    tags=["upload"])
app.include_router(chat.router,      prefix="/api/chat",      tags=["chat"])
app.include_router(thesis.router,    prefix="/api/thesis",    tags=["thesis"])
app.include_router(journal.router,   prefix="/api/journal",   tags=["journal"])
app.include_router(companies.router, prefix="/api/companies", tags=["companies"])
app.include_router(notes.router,     prefix="/api/notes",     tags=["notes"])

@app.get("/health")
def health_check():
    return {"status": "ok"}