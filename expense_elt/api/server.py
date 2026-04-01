import os

from log_config import setup_logging
setup_logging()

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse

from api.auth import require_auth, require_owner
from api.dependencies import limiter
from api.routes import status, transactions, review, categories, summary, pipeline, config
from api.routes import auth as auth_routes
from api.routes import accountant_management, export as export_routes

# --- App setup ---
_is_production = os.environ.get("ENV", "").lower() == "production"

app = FastAPI(
    title="Tax2025 Expense ELT",
    version="0.1.0",
    docs_url=None if _is_production else "/docs",
    openapi_url=None if _is_production else "/openapi.json",
)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )


# --- CORS ---
_cors_origins = os.environ.get("CORS_ORIGINS", "")
_allowed_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()] if _cors_origins else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Security headers middleware ---
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://accounts.google.com https://apis.google.com; "
        "style-src 'self' 'unsafe-inline' https://accounts.google.com; "
        "frame-src https://accounts.google.com; "
        "connect-src 'self'; "
        "img-src 'self' https://lh3.googleusercontent.com data:;"
    )
    return response


# --- Mount API routes ---
# Auth routes — no auth dependency (must be accessible before login)
app.include_router(auth_routes.router, prefix="/api", tags=["auth"])

# Routes accessible to any authenticated user (owner + accountant)
_auth_dep = [Depends(require_auth)]
app.include_router(status.router, prefix="/api", tags=["status"], dependencies=_auth_dep)
app.include_router(transactions.router, prefix="/api", tags=["transactions"], dependencies=_auth_dep)
app.include_router(categories.router, prefix="/api", tags=["categories"], dependencies=_auth_dep)
app.include_router(summary.router, prefix="/api", tags=["summary"], dependencies=_auth_dep)
app.include_router(export_routes.router, prefix="/api", tags=["export"], dependencies=_auth_dep)

# Routes restricted to owner only
_owner_dep = [Depends(require_owner)]
app.include_router(review.router, prefix="/api", tags=["review"], dependencies=_owner_dep)
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"], dependencies=_owner_dep)
app.include_router(config.router, prefix="/api", tags=["config"], dependencies=_owner_dep)
app.include_router(accountant_management.router, prefix="/api", tags=["accountants"], dependencies=_owner_dep)

# --- Serve React static files (production) ---
_FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="static")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        # Path traversal protection: resolve and validate within dist dir
        resolved = (_FRONTEND_DIST / path).resolve()
        if (
            resolved.is_relative_to(_FRONTEND_DIST)
            and resolved.exists()
            and resolved.is_file()
        ):
            return FileResponse(str(resolved))
        return FileResponse(str(_FRONTEND_DIST / "index.html"))
