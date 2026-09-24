# Route layer: thin. Parse request -> call service -> return. No business logic here.

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.deps import close_resources, get_service
from app.errors import install_error_handlers
from app.ingest_routes import ingest_router
from app.models import Item, ItemCreate, ItemPage, ItemUpdate
from app.observability import configure_logging, install_observability
from app.service import ItemService

settings = get_settings()
configure_logging(settings.log_level, settings.git_sha)
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("startup", extra={"env": settings.app_env, "git_sha": settings.git_sha})
    yield
    close_resources()  # graceful shutdown: drain pool/Redis connections
    log.info("shutdown")


app = FastAPI(title="Interview App", version="0.1.0", lifespan=lifespan)
install_observability(app, settings.git_sha)
install_error_handlers(app)
app.include_router(ingest_router)

# CORS_ORIGINS defaults to "*" for the demo; set it to the real frontend
# origin in production (config.py) -- say so out loud.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """Liveness: the process is up. No dependency checks -- a DB blip must not
    get every instance restarted at once."""
    return {"status": "ok"}


@app.get("/version")
def version() -> dict:
    """Which commit is live? CI asserts this equals the SHA it just deployed."""
    return {"git_sha": settings.git_sha, "build_time": settings.build_time, "env": settings.app_env}


@app.get("/ready")
def ready(svc: ItemService = Depends(get_service)):
    """Readiness: can this instance serve traffic? DB down -> 503 (pull from
    the load balancer). Cache down -> still ready, just degraded."""
    checks = svc.check_dependencies()
    if not checks["database"]:
        return JSONResponse(status_code=503, content={"status": "unavailable", "checks": checks})
    return {"status": "ok" if all(checks.values()) else "degraded", "checks": checks}


@app.get("/items", response_model=ItemPage)
def list_items(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    svc: ItemService = Depends(get_service),
):
    return ItemPage(items=svc.list_items(limit, offset), limit=limit, offset=offset)


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: str, svc: ItemService = Depends(get_service)):
    return svc.get_item(item_id)


@app.post("/items", response_model=Item, status_code=201)
def create_item(data: ItemCreate, svc: ItemService = Depends(get_service)):
    return svc.create_item(data)


@app.patch("/items/{item_id}", response_model=Item)
def update_item(item_id: str, data: ItemUpdate, svc: ItemService = Depends(get_service)):
    return svc.update_item(item_id, data)


@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: str, svc: ItemService = Depends(get_service)):
    svc.delete_item(item_id)
