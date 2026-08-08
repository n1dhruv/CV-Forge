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
from app.models.resume import JDActionVerb, JDRequirement, JobDescription
from app.schemas.jd import JDParsed, JDTechnologyRequirement
from app.services import llm_client
from app.services.storage import StorageService
from app.services.technology_matching import contains_literal_term, normalized_text

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
  "ats_keywords": ["string"],
  "action_verbs": ["string"],
  "technology_requirements": [
    {{
      "requirement": "exact string from required_skills or nice_to_have_skills",
      "named_technologies": ["technology exactly as written in the job description"],
      "match_mode": "any | all"
    }}
  ]
}}
Return only the valid JSON object: no preamble, markdown fences, or commentary.
Use an empty array, never null or an omitted field, when a list category has no values.
Extract strong action verbs actually used in responsibilities or requirements. Deduplicate them
and normalize inflections to a base form where reasonable (for example, "manage" instead of
"managing", "managed", and "manages"). Do not invent verbs absent from the job description.
For technology_requirements, include only requirements that name concrete technologies,
products, programming languages, platforms, protocols, or tools. Copy each technology exactly
as written in the job description. Use "all" only when the requirement explicitly requires every
listed technology; use "any" for alternatives such as "or". Do not invent aliases or technologies.

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
        output = await llm_client.get_completion(user_id, messages)
        try:
            parsed = JDParsed.model_validate_json(output)
            validated_technology_specs(parsed, raw_text)
            return parsed
        except (ValidationError, ValueError):
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


def deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip().casefold() for value in values if value.strip()))


def validated_technology_specs(
    parsed: JDParsed, raw_text: str
) -> dict[str, JDTechnologyRequirement]:
    requirements = {
        normalized_text(requirement)
        for requirement in parsed.required_skills + parsed.nice_to_have_skills
    }
    validated: dict[str, JDTechnologyRequirement] = {}
    for spec in parsed.technology_requirements:
        requirement_key = normalized_text(spec.requirement)
        if requirement_key not in requirements or requirement_key in validated:
            raise ValueError("Technology extraction references an unknown requirement")
        technologies = list(
            dict.fromkeys(
                technology.strip() for technology in spec.named_technologies if technology.strip()
            )
        )
        if not technologies or any(
            not contains_literal_term(raw_text, technology)
            and not contains_literal_term(spec.requirement, technology)
            for technology in technologies
        ):
            raise ValueError("Technology extraction contains an invented term")
        validated[requirement_key] = spec.model_copy(update={"named_technologies": technologies})
    return validated


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
            parsed_data["action_verbs"] = deduplicate(parsed.action_verbs)
            technology_specs = validated_technology_specs(parsed, raw_text)
            parsed_data["technology_requirements"] = [
                spec.model_dump() for spec in technology_specs.values()
            ]
            current_jd.parsed_json = parsed_data
            current_jd.status = "done"
            requirement_rows = []
            for importance, skills in (
                ("required", parsed.required_skills),
                ("nice_to_have", parsed.nice_to_have_skills),
            ):
                for skill in skills:
                    spec = technology_specs.get(normalized_text(skill))
                    requirement_rows.append(
                        JDRequirement(
                            jd_id=parsed_jd_id,
                            skill=skill,
                            importance=importance,
                            named_technologies=(spec.named_technologies if spec else []),
                            technology_match_mode=(spec.match_mode if spec else None),
                        )
                    )
            session.add_all(
                requirement_rows
                + [
                    JDActionVerb(jd_id=parsed_jd_id, verb=verb)
                    for verb in parsed_data["action_verbs"]
                ]
            )
            current_job.status = "done"
            current_job.error = None
            current_job.result = {
                "required_skills": len(parsed.required_skills),
                "nice_to_have_skills": len(parsed.nice_to_have_skills),
                "action_verbs": len(parsed_data["action_verbs"]),
            }
            await session.commit()
        return

    await _set_status(parsed_jd_id, parsed_job_id, parsed_user_id, "failed", error=error)
