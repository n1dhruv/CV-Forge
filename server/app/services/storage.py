from urllib.parse import quote

import httpx

from app.core.config import Settings


class StorageService:
    def __init__(self, settings: Settings) -> None:
        self.base_url = f"{settings.supabase_url.rstrip('/')}/storage/v1"
        key = settings.supabase_service_role_key.get_secret_value()
        self.headers = {"Authorization": f"Bearer {key}", "apikey": key}
        self.bucket = settings.supabase_storage_bucket_resumes

    async def signed_upload_url(self, path: str) -> dict[str, str | None]:
        encoded = quote(path, safe="/")
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.base_url}/object/upload/sign/{self.bucket}/{encoded}", headers=self.headers
            )
            response.raise_for_status()
        data = response.json()
        return {"path": path, "signed_url": data["url"], "token": data.get("token")}

    async def signed_download_url(self, path: str, expires_in: int = 3600) -> dict[str, str | None]:
        encoded = quote(path, safe="/")
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.base_url}/object/sign/{self.bucket}/{encoded}",
                headers=self.headers,
                json={"expiresIn": expires_in},
            )
            response.raise_for_status()
        data = response.json()
        return {"path": path, "signed_url": data["signedURL"], "token": None}
