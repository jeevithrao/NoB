from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import admin, auth, media, neighbourhoods, purchases, sessions, social, tours

app = FastAPI(
    title="NoB \u2014 Neighbourhoods of Bengaluru",
    description="Backend API for the NoB audio walking tour app",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS \u2014 explicitly list allowed origins; never combine allow_origins=["*"]
# with allow_credentials=True as browsers reject that combination.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Normalizes every error to the {"error": {"code", "message"}} envelope
    from the API Specification doc, whether a route raised it that way
    already or FastAPI/Pydantic raised a plain string detail."""
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        body = detail
    else:
        body = {"error": {"code": "HTTP_ERROR", "message": str(detail)}}
    return JSONResponse(status_code=exc.status_code, content=body)


app.include_router(auth.router)
app.include_router(tours.router)
app.include_router(neighbourhoods.router)
app.include_router(purchases.router)
app.include_router(sessions.router)
app.include_router(social.router)
app.include_router(admin.router)
# Signed media serving \u2014 replaces the open StaticFiles mount.
# Every /media/** request is validated against an HMAC-SHA256 signature
# before the file is returned (see app/routers/media.py).
app.include_router(media.router)


@app.get("/")
async def root():
    return {"message": "NoB API is running", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
