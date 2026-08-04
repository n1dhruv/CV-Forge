import asyncio
from io import BytesIO
from typing import Any
from uuid import UUID

import pdfplumber
from pydantic import ValidationError
from pypdf import PdfReader
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.jobs import BackgroundJob
from app.models.resume import JDRequirement, JobDescription
from app.schemas.jd import JDParsed
from app.services import llm_client
from app.services.storage import StorageService

MAX_LLM_CHARACTERS = 15_000
MIN_EXTRACTED_CHARACTERS = 50
NO_LLM_ERROR = "No LLM provider configured — add one in Settings"
PDF_TEXT_ERROR = "Couldn't extract text from this PDF — try pasting the text directly"
INVALID_OUTPUT_ERROR = "The LLM returned invalid structured data twice — try again"


def extract_pdf_text(content: bytes) -> str:
    text = ""
    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages).strip()
    except Exception:
        text = ""
    if len(text) >= MIN_EXTRACTED_CHARACTERS:
        return text
    try:
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception:
        return ""


def capped_jd_text(raw_text: str) -> str:
    note = "\n\n[JD truncated to 15,000 characters.]"
    if len(raw_text) <= MAX_LLM_CHARACTERS:
        return raw_text
    return raw_text[: MAX_LLM_CHARACTERS - len(note)] + note


def prompt_for(raw_text: str) -> str:
    return f"""Extract the job description into exactly this JSON shape:
{{
  "required_skills": ["string"],
  "nice_to_have_skills": ["string"],
  "responsibilities": ["string"],
  "seniority": "junior | mid | senior | staff | unspecified",
  "ats_keywords": ["string"]
}}
Return only the valid JSON object: no preamble, markdown fences, or commentary.
Use an empty array, never null or an omitted field, when a list category has no values.

Job description:
{capped_jd_text(raw_text)}"""


async def _load_rows(
    jd_id: UUID, job_id: UUID, user_id: UUID
) -> tuple[JobDescription | None, BackgroundJob | None]:
    async with async_session_factory() as session:
        jd = await session.scalar(
            select(JobDescription).where(
                JobDescription.id == jd_id, JobDescription.user_id == user_id
            )
        )
        job = await session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.id == job_id, BackgroundJob.user_id == user_id
            )
        )
        return jd, job


async def _set_status(
    jd_id: UUID,
    job_id: UUID,
    user_id: UUID,
    status: str,
    *,
    error: str | None = None,
) -> None:
    async with async_session_factory() as session:
        jd = await session.scalar(
            select(JobDescription).where(
                JobDescription.id == jd_id, JobDescription.user_id == user_id
            )
        )
        job = await session.scalar(
            select(BackgroundJob).where(
                BackgroundJob.id == job_id, BackgroundJob.user_id == user_id
            )
        )
        if jd is None or job is None:
            return
        jd.status = status
        job.status = status
        job.error = error
        await session.commit()


async def _validated_completion(user_id: UUID, raw_text: str) -> JDParsed | None:
    messages = [{"role": "user", "content": prompt_for(raw_text)}]
    for attempt in range(2):
        output = await llm_client.get_completion(user_id, messages, max_tokens=1200)
        try:
            return JDParsed.model_validate_json(output)
        except ValidationError:
            if attempt == 0:
                messages.extend(
                    [
                        {"role": "assistant", "content": output},
                        {
                            "role": "user",
                            "content": (
                                "Your previous response was not valid JSON matching the required "
                                "schema. Return only the JSON object."
                            ),
                        },
                    ]
                )
    return None


async def parse_jd_task(
    context: dict[str, Any], jd_id: str, background_job_id: str, user_id: str
) -> None:
    del context
    parsed_jd_id = UUID(jd_id)
    parsed_job_id = UUID(background_job_id)
    parsed_user_id = UUID(user_id)

    try:
        await llm_client.ensure_configured(parsed_user_id)
    except llm_client.LLMNotConfiguredError:
        await _set_status(parsed_jd_id, parsed_job_id, parsed_user_id, "failed", error=NO_LLM_ERROR)
        return

    description, job = await _load_rows(parsed_jd_id, parsed_job_id, parsed_user_id)
    if description is None or job is None:
        return
    await _set_status(parsed_jd_id, parsed_job_id, parsed_user_id, "running")

    raw_text = description.raw_text
    if description.source_file_url:
        try:
            settings = get_settings()
            pdf = await StorageService(settings).download(
                description.source_file_url, settings.supabase_storage_bucket_jd_uploads
            )
            raw_text = await asyncio.to_thread(extract_pdf_text, pdf)
        except Exception:
            await _set_status(
                parsed_jd_id,
                parsed_job_id,
                parsed_user_id,
                "failed",
                error="Unable to download or read the uploaded PDF — try again",
            )
            return
        if len(raw_text) < MIN_EXTRACTED_CHARACTERS:
            await _set_status(
                parsed_jd_id, parsed_job_id, parsed_user_id, "failed", error=PDF_TEXT_ERROR
            )
            return
        async with async_session_factory() as session:
            current = await session.get(JobDescription, parsed_jd_id)
            if current is None or current.user_id != parsed_user_id:
                return
            current.raw_text = raw_text
            await session.commit()

    if not raw_text:
        await _set_status(
            parsed_jd_id, parsed_job_id, parsed_user_id, "failed", error="Job description is empty"
        )
        return

    try:
        parsed = await _validated_completion(parsed_user_id, raw_text)
    except llm_client.LLMNotConfiguredError:
        error = NO_LLM_ERROR
    except llm_client.LLMAuthError:
        error = "Your API key was rejected by the provider — check it in Settings"
    except llm_client.LLMRateLimitError:
        error = "Your provider rate limit was reached — wait and try again"
    except llm_client.LLMProviderError:
        error = "The LLM provider could not complete the request — try again"
    else:
        if parsed is None:
            await _set_status(
                parsed_jd_id,
                parsed_job_id,
                parsed_user_id,
                "failed",
                error=INVALID_OUTPUT_ERROR,
            )
            return
        async with async_session_factory() as session:
            current_jd = await session.scalar(
                select(JobDescription).where(
                    JobDescription.id == parsed_jd_id,
                    JobDescription.user_id == parsed_user_id,
                )
            )
            current_job = await session.scalar(
                select(BackgroundJob).where(
                    BackgroundJob.id == parsed_job_id,
                    BackgroundJob.user_id == parsed_user_id,
                )
            )
            if current_jd is None or current_job is None:
                return
            parsed_data = parsed.model_dump()
            current_jd.parsed_json = parsed_data
            current_jd.status = "done"
            session.add_all(
                [
                    JDRequirement(jd_id=parsed_jd_id, skill=skill, importance=importance)
                    for importance, skills in (
                        ("required", parsed.required_skills),
                        ("nice_to_have", parsed.nice_to_have_skills),
                    )
                    for skill in skills
                ]
            )
            current_job.status = "done"
            current_job.error = None
            current_job.result = {
                "required_skills": len(parsed.required_skills),
                "nice_to_have_skills": len(parsed.nice_to_have_skills),
            }
            await session.commit()
        return

    await _set_status(parsed_jd_id, parsed_job_id, parsed_user_id, "failed", error=error)
