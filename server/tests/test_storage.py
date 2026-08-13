from unittest.mock import AsyncMock, MagicMock

from app.services.storage import StorageService


async def test_signed_download_url_makes_supabase_relative_url_absolute(monkeypatch) -> None:
    settings = MagicMock(
        supabase_url="https://project.supabase.co",
        supabase_storage_bucket_resumes="resumes",
    )
    settings.supabase_secret_key.get_secret_value.return_value = "secret"
    response = MagicMock()
    response.json.return_value = {"signedURL": "/storage/v1/object/sign/resumes/file.pdf?token=x"}
    client = AsyncMock()
    client.__aenter__.return_value.post.return_value = response
    monkeypatch.setattr("app.services.storage.httpx.AsyncClient", MagicMock(return_value=client))

    result = await StorageService(settings).signed_download_url("file.pdf")

    assert result["signed_url"] == (
        "https://project.supabase.co/storage/v1/object/sign/resumes/file.pdf?token=x"
    )


async def test_signed_download_url_prefixes_storage_api_for_object_path(monkeypatch) -> None:
    settings = MagicMock(
        supabase_url="https://project.supabase.co",
        supabase_storage_bucket_resumes="resumes",
    )
    settings.supabase_secret_key.get_secret_value.return_value = "secret"
    response = MagicMock()
    response.json.return_value = {"signedURL": "/object/sign/resumes/file.pdf?token=x"}
    client = AsyncMock()
    client.__aenter__.return_value.post.return_value = response
    monkeypatch.setattr("app.services.storage.httpx.AsyncClient", MagicMock(return_value=client))

    result = await StorageService(settings).signed_download_url("file.pdf")

    assert result["signed_url"] == (
        "https://project.supabase.co/storage/v1/object/sign/resumes/file.pdf?token=x"
    )


async def test_upload_replaces_existing_resume_pdf(monkeypatch) -> None:
    settings = MagicMock(
        supabase_url="https://project.supabase.co",
        supabase_storage_bucket_resumes="resumes",
    )
    settings.supabase_secret_key.get_secret_value.return_value = "secret"
    client = AsyncMock()
    client.__aenter__.return_value.post.return_value = MagicMock()
    monkeypatch.setattr("app.services.storage.httpx.AsyncClient", MagicMock(return_value=client))

    await StorageService(settings).upload("owner/version/resume.pdf", b"pdf", "application/pdf")

    headers = client.__aenter__.return_value.post.call_args.kwargs["headers"]
    assert headers["x-upsert"] == "true"
