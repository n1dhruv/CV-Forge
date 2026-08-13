from urllib.parse import quote

import httpx

from app.core.config import Settings


class StorageService:
    def __init__(self, settings: Settings) -> None:
        self.supabase_url = settings.supabase_url.rstrip("/")
        self.base_url = f"{self.supabase_url}/storage/v1"
        key = settings.supabase_secret_key.get_secret_value()
        self.headers = {"apikey": key}
        self.bucket = settings.supabase_storage_bucket_resumes

    async def upload(
        self, path: str, content: bytes, content_type: str, bucket: str | None = None
    ) -> str:
        encoded = quote(path, safe="/")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/object/{bucket or self.bucket}/{encoded}",
                headers={**self.headers, "Content-Type": content_type, "x-upsert": "true"},
                content=content,
            )
            response.raise_for_status()
        return path

    async def download(self, path: str, bucket: str | None = None) -> bytes:
        encoded = quote(path, safe="/")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/object/authenticated/{bucket or self.bucket}/{encoded}",
                headers=self.headers,
            )
            response.raise_for_status()
        return response.content

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
        signed_url = str(data["signedURL"])
        if signed_url.startswith("/object/"):
            signed_url = f"{self.base_url}{signed_url}"
        elif signed_url.startswith("/"):
            signed_url = f"{self.supabase_url}{signed_url}"
        return {"path": path, "signed_url": signed_url, "token": None}
