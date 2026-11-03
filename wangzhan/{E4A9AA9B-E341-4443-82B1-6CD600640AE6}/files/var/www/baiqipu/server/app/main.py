from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from app.services.auth import get_current_user
from app.v2.api import router as v2_router
from app.v2.knowledge_api import router as knowledge_router
from app.v2.compat import router as v2_compat_router
from app.v2.legacy_assets import router as v2_legacy_assets_router
from app.v2 import models as v2_models

from app.config import get_settings
from app.database import Base, engine
from app.routers import horses, products, auth, gacha, orders, chat, video, crossborder, admin, analytics_api, payments, ai, tts, users, workflow
from app.routers import collections

settings = get_settings()

# Database tables are managed by Alembic migrations
# Run: alembic upgrade head

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(horses.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(gacha.router, prefix="/api/v1")
app.include_router(orders.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(video.router, prefix="/api/v1")
app.include_router(workflow.router, prefix="/api/v1")
app.include_router(crossborder.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(analytics_api.router, prefix="/api/v1")
app.include_router(collections.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(tts.router, prefix="/api/v1")

server_dir = Path(__file__).resolve().parents[1]
generated_dir = server_dir / "generated"
assets_dir = server_dir / "assets"
generated_dir.mkdir(exist_ok=True)
assets_dir.mkdir(exist_ok=True)
# Legacy private media is no longer publicly mounted.
@app.get("/generated/{relative:path}")
def private_legacy_media(relative: str, user=Depends(get_current_user)):
    target = (generated_dir / relative).resolve()
    if not target.is_relative_to(generated_dir.resolve()) or not target.is_file():
        raise HTTPException(404, "Media not found")
    # Old uploads do not contain reliable ownership metadata. Fail closed until migrated.
    if user.role not in {"admin", "operator"}:
        raise HTTPException(403, "Legacy media requires staff migration/review")
    return FileResponse(target)

if settings.V2_STUDIO_ENABLED:
    app.include_router(v2_router)
    app.include_router(knowledge_router)
    # Compatibility adapter: keeps the original video-factory frontend contract
    # while all work happens on the V2 CPU DAG backend.
    app.include_router(v2_compat_router)
    # Audited import path for legacy /generated/* media.
    app.include_router(v2_legacy_assets_router)

@app.middleware("http")
async def guarded_legacy_actions(request, call_next):
    path = request.url.path
    if not settings.LEGACY_EXTERNAL_ENABLED and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if path.startswith(("/api/v1/video/", "/api/v1/crossborder/", "/api/v1/tts/")):
            return JSONResponse({"error_code": "LEGACY_EXTERNAL_DISABLED", "message": "旧生成/发布动作暂冻结；请使用 V2 本地 CPU 工作台。"}, status_code=409)
    return await call_next(request)
backgrounds_dir = assets_dir / "video_backgrounds"
backgrounds_dir.mkdir(exist_ok=True)
app.mount("/assets/video_backgrounds", StaticFiles(directory=backgrounds_dir), name="video-backgrounds")


@app.get("/")
def root():
    return {"name": settings.APP_NAME, "version": settings.VERSION, "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}

# Compatibility: preserve the old built site and business routes without editing minified assets.
legacy_dir = server_dir.parents[5] / "baiqipu.com-source-20260424-194149"
# Resolve by sibling layout rather than relying on a deployment-specific absolute path.
legacy_dir = next((parent / "baiqipu.com-source-20260424-194149" for parent in server_dir.parents if (parent / "baiqipu.com-source-20260424-194149").is_dir()), legacy_dir)
if legacy_dir.is_dir():
    app.mount("/images", StaticFiles(directory=legacy_dir / "images"), name="legacy-images")
    app.mount("/assets/js", StaticFiles(directory=legacy_dir / "assets/js"), name="legacy-js")
    @app.get("/assets/{filename}")
    def legacy_css(filename: str):
        if filename != "index-CAKZiFLw.css":
            raise HTTPException(404)
        return FileResponse(legacy_dir / "assets" / filename)
    @app.get("/gacha")
    @app.get("/collection")
    @app.get("/collections")
    @app.get("/quiz")
    @app.get("/quiz/result")
    @app.get("/product")
    @app.get("/product/{product_id}")
    @app.get("/products")
    @app.get("/products/{product_id}")
    @app.get("/login")
    @app.get("/register")
    @app.get("/atlas")
    @app.get("/atlas/{horse_id}")
    @app.get("/chat")
    @app.get("/video-factory")
    @app.get("/crossborder")
    @app.get("/admin/users")
    @app.get("/admin/crossborder")
    @app.get("/analytics")
    def legacy_page():
        return FileResponse(legacy_dir / "index.html")
    app.mount("/legacy", StaticFiles(directory=legacy_dir, html=True), name="legacy-site")

@app.exception_handler(HTTPException)
async def safe_http_error(request, exc):
    import uuid
    detail = exc.detail if isinstance(exc.detail, str) else "Request rejected"
    return JSONResponse({"detail": detail, "error_code": detail.split(":")[0] if ":" in detail else "HTTP_"+str(exc.status_code),
                         "message": detail, "request_id": uuid.uuid4().hex}, status_code=exc.status_code)
