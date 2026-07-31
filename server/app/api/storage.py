from fastapi import APIRouter, Depends, HTTPException
import httpx

from app.core.config import Settings, get_settings
from app.core.security import CurrentUser
from app.schemas.storage import SignedUrlResponse, StoragePathRequest
from app.services.storage import StorageService

router = APIRouter(prefix="/api/storage", tags=["storage"])


@router.post("/signed-upload-url", response_model=SignedUrlResponse)
async def create_signed_upload_url(
    payload: StoragePathRequest,
    current_user: CurrentUser,
    settings: Settings = Depends(get_settings),
) -> SignedUrlResponse:
    scoped_path = f"{current_user.id}/{payload.path}"
    try:
        result = await StorageService(settings).signed_upload_url(scoped_path)
    except (httpx.HTTPError, KeyError) as exc:
        raise HTTPException(status_code=502, detail="Unable to create storage upload URL") from exc
    return SignedUrlResponse(**result)


@router.post("/signed-download-url", response_model=SignedUrlResponse)
async def create_signed_download_url(
    payload: StoragePathRequest,
    current_user: CurrentUser,
    settings: Settings = Depends(get_settings),
) -> SignedUrlResponse:
    scoped_path = f"{current_user.id}/{payload.path}"
    try:
        result = await StorageService(settings).signed_download_url(scoped_path)
    except (httpx.HTTPError, KeyError) as exc:
        raise HTTPException(
            status_code=502, detail="Unable to create storage download URL"
        ) from exc
    return SignedUrlResponse(**result)
