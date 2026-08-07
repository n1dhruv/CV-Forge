import asyncio
import re
from io import BytesIO
from typing import Any
from uuid import UUID

from docx import Document
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.jobs import BackgroundJob
from app.models.resume import ResumeImport
from app.schemas.resume_import import ParsedResumeImport
from app.services import llm_client
from app.services.storage import StorageService
from app.workers.jd import extract_pdf_text

MIN_EXTRACTED_CHARACTERS = 20
INVALID_OUTPUT_ERROR = "The LLM returned invalid or unsupported resume data twice — try again"


class FabricatedResumeContentError(ValueError):
    pass


def extract_docx_text(content: bytes) -> str:
    document = Document(BytesIO(content))
    return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()


def prompt_for(raw_text: str) -> str:
    return f"""Extract this resume into exactly this JSON shape:
{{
  "items": [{{
    "type": "experience | project | education | certification",
    "title": "string",
    "org": "string or null",
    "start_date": "YYYY-MM-DD or null",
    "end_date": "YYYY-MM-DD or null",
    "bullets": ["string"]
  }}],
  "skills": ["string"]
}}
Return only the valid JSON object: no preamble, markdown fences, or commentary.
CRITICAL: Extract only claims, bullets, and skills literally present in the source text.
Never infer a skill, invent a metric, embellish a bullet, or add plausible missing content.
If the source does not explicitly state something, omit it. Use empty arrays when needed.

Resume source text:
{raw_text}"""


def _literal_text(value: str) -> str:
    value = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", value.casefold())
    value = re.sub(r"(?<=\w)-(?=\w)", "", value)
    return " ".join(re.findall(r"\S+", value))


def enforce_literal_content(parsed: ParsedResumeImport, raw_text: str) -> None:
    source = _literal_text(raw_text)
    claims = parsed.skills + [
        claim
        for item in parsed.items
        for claim in ([item.title] + ([item.org] if item.org else []) + item.bullets)
    ]
    fabricated = [claim for claim in claims if _literal_text(claim) not in source]
    if fabricated:
        raise FabricatedResumeContentError


async def _validated_completion(user_id: UUID, raw_text: str) -> ParsedResumeImport | None:
    messages = [{"role": "user", "content": prompt_for(raw_text)}]
    for attempt in range(2):
        output = await llm_client.get_completion(
            user_id, messages, response_format={"type": "json_object"}
        )
        try:
            parsed = ParsedResumeImport.model_validate_json(output)
            enforce_literal_content(parsed, raw_text)
            return parsed
        except (ValidationError, FabricatedResumeContentError):
            if attempt == 0:
                messages.extend(
                    [
                        {"role": "assistant", "content": output},
                        {
                            "role": "user",
                            "content": (
                                "The response violated the schema or included content not literally "
                                "present in the source. Return corrected JSON only."
                            ),
                        },
                    ]
                )
    return None


async def _set_status(
    resume_import_id: UUID,
    job_id: UUID,
    user_id: UUID,
    status: str,
    error: str | None = None,
) -> None:
    async with async_session_factory() as session:
        resume_import = await session.scalar(
            select(ResumeImport).where(
                ResumeImport.id == resume_import_id, ResumeImport.user_id == user_id
            )
        )
        job = await session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.id == job_id, BackgroundJob.user_id == user_id
            )
        )
        if resume_import is None or job is None:
            return
        resume_import.status = status
        job.status = status
        job.error = error
        await session.commit()


async def parse_resume_import_task(
    context: dict[str, Any], resume_import_id: str, background_job_id: str, user_id: str
) -> None:
    del context
    parsed_import_id = UUID(resume_import_id)
    parsed_job_id = UUID(background_job_id)
    parsed_user_id = UUID(user_id)
    try:
        await llm_client.ensure_configured(parsed_user_id)
    except llm_client.LLMNotConfiguredError:
        await _set_status(
            parsed_import_id, parsed_job_id, parsed_user_id, "failed", "No LLM provider configured"
        )
        return

    async with async_session_factory() as session:
        resume_import = await session.scalar(
            select(ResumeImport).where(
                ResumeImport.id == parsed_import_id, ResumeImport.user_id == parsed_user_id
            )
        )
        job = await session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.id == parsed_job_id, BackgroundJob.user_id == parsed_user_id
            )
        )
        if resume_import is None or job is None or resume_import.source_file_url is None:
            return
        source_path = resume_import.source_file_url
    await _set_status(parsed_import_id, parsed_job_id, parsed_user_id, "running")

    try:
        settings = get_settings()
        content = await StorageService(settings).download(
            source_path, settings.supabase_storage_bucket_resume_imports
        )
        extractor = extract_pdf_text if source_path.lower().endswith(".pdf") else extract_docx_text
        raw_text = await asyncio.to_thread(extractor, content)
    except Exception:
        await _set_status(
            parsed_import_id,
            parsed_job_id,
            parsed_user_id,
            "failed",
            "Unable to download or read the uploaded resume",
        )
        return
    if len(raw_text) < MIN_EXTRACTED_CHARACTERS:
        await _set_status(
            parsed_import_id,
            parsed_job_id,
            parsed_user_id,
            "failed",
            "Couldn't extract text from this resume",
        )
        return

    async with async_session_factory() as session:
        current = await session.get(ResumeImport, parsed_import_id)
        if current is None or current.user_id != parsed_user_id:
            return
        current.raw_text = raw_text
        await session.commit()

    try:
        parsed = await _validated_completion(parsed_user_id, raw_text)
    except llm_client.LLMNotConfiguredError:
        error = "No LLM provider configured"
    except llm_client.LLMAuthError:
        error = "Your API key was rejected by the provider"
    except llm_client.LLMRateLimitError:
        error = "Your provider rate limit was reached"
    except llm_client.LLMProviderError:
        error = "The LLM provider could not parse this resume"
    else:
        if parsed is None:
            await _set_status(
                parsed_import_id,
                parsed_job_id,
                parsed_user_id,
                "failed",
                INVALID_OUTPUT_ERROR,
            )
            return
        async with async_session_factory() as session:
            current = await session.scalar(
                select(ResumeImport).where(
                    ResumeImport.id == parsed_import_id,
                    ResumeImport.user_id == parsed_user_id,
                )
            )
            job = await session.scalar(
                select(BackgroundJob).where(
                    BackgroundJob.id == parsed_job_id,
                    BackgroundJob.user_id == parsed_user_id,
                )
            )
            if current is None or job is None:
                return
            current.parsed_json = parsed.model_dump(mode="json")
            current.status = "done"
            job.status = "done"
            job.error = None
            job.result = {"items": len(parsed.items), "skills": len(parsed.skills)}
            await session.commit()
        return
    await _set_status(parsed_import_id, parsed_job_id, parsed_user_id, "failed", error)
