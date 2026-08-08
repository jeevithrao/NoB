"""Signed media file serving.

Replaces the static StaticFiles mount from main.py with a route that
validates the HMAC-SHA256 signature and expiry before serving any file.
This prevents permanent shareable links to audio content \u2014 each URL
becomes invalid after SIGNED_URL_EXPIRE_SECONDS seconds.
"""
import os

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.security import verify_media_signature

router = APIRouter(tags=["media"])


@router.get("/media/{file_path:path}")
async def serve_media(
    file_path: str,
    exp: str = Query(...),
    sig: str = Query(...),
):
    """Serve a media file after verifying its HMAC signature and expiry.

    Returns 403 for an expired or tampered URL, 404 if the file doesn't exist.
    The Accept-Ranges header enables HTTP byte-range requests so mobile audio
    players can seek without re-downloading the whole file.
    """
    path = f"/media/{file_path}"
    if not verify_media_signature(path, exp, sig):
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "INVALID_SIGNATURE", "message": "URL expired or invalid."}},
        )

    disk_path = os.path.join("media", file_path)
    if not os.path.isfile(disk_path):
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "File not found."}},
        )

    return FileResponse(
        disk_path,
        media_type="audio/mpeg",
        headers={"Accept-Ranges": "bytes"},
    )
