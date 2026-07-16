from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(
    title="NoB — Neighbourhoods of Bengaluru",
    description="Backend API for the NoB audio walking tour app",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS — allows the mobile app and admin panel to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "NoB API is running", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}