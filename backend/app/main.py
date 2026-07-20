from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routers import admin, auth, purchases, sessions, social, tours

app = FastAPI(
    title="NoB — Neighbourhoods of Bengaluru",
    description="Backend API for the NoB audio walking tour app",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allows the mobile app and admin panel to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
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
app.include_router(purchases.router)
app.include_router(sessions.router)
app.include_router(social.router)
app.include_router(admin.router)

# Serves locally-uploaded audio/images during development. Swap for S3 +
# signed URLs (see tours.py's _signed_audio_url) before production.
app.mount("/media", StaticFiles(directory="media", check_dir=False), name="media")


@app.get("/")
async def root():
    return {"message": "NoB API is running", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
