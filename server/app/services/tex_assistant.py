import json
from io import BytesIO
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.models.resume import JobDescription, ResumeBulletSelection, ResumeVersion
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.models.user import User
from app.schemas.resume_version import AssistantProposal
from app.services import llm_client
from app.services.latex_compiler import (
    CompilationError,
    CompileDiagnostic,
    compile_latex_async,
)
from app.services.rewriter import VerificationOutput, contains_term, number_tokens

MAX_CONTEXT_CHARACTERS = 80_000
_MANDATORY_CONTEXT_KEYS = (
    "profile",
    "current_resume",
    "selected_bullet_evidence",
    "selected_skill_snapshots",
    "primary_education",
)
_GROUNDING_EVIDENCE_KEYS = (*_MANDATORY_CONTEXT_KEYS, "remaining_skill_bank")


class InvalidAssistantProposalError(Exception):
    def __init__(self, diagnostic: str) -> None:
        super().__init__(diagnostic)
        self.diagnostic = diagnostic


class InvalidAssistantPreservationError(Exception):
    pass


class InvalidAssistantGroundingError(Exception):
    pass


class AssistantContextTooLargeError(Exception):
    pass


def _profile(user: User | None) -> dict[str, str | None]:
    fields = (
        "full_name",
        "contact_email",
        "phone",
        "location",
        "linkedin_url",
        "github_url",
        "leetcode_url",
        "portfolio_url",
    )
    profile = {field: getattr(user, field, None) for field in fields}
    if user is not None:
        profile["contact_email"] = user.contact_email or user.email
    return profile


def _remaining_item(item: SkillBankItem) -> dict[str, Any]:
    return {
        "type": item.type,
        "title": item.title,
        "org": item.org,
        "start_date": str(item.start_date) if item.start_date else None,
        "end_date": str(item.end_date) if item.end_date else None,
        "raw_text": item.raw_text,
        "skill_category": item.skill_category,
        "tags": item.tags or [],
        "bullets": [
            {"text": bullet.text, "metrics": bullet.metrics, "tags": bullet.tags or []}
            for bullet in item.bullet_points
        ],
    }


def _capped_json(context: dict[str, Any]) -> str:
    mandatory = {key: context[key] for key in _MANDATORY_CONTEXT_KEYS if key in context}
    if len(json.dumps(mandatory, ensure_ascii=False, separators=(",", ":"))) > (
        MAX_CONTEXT_CHARACTERS
    ):
        raise AssistantContextTooLargeError
    while True:
        serialized = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
        if len(serialized) <= MAX_CONTEXT_CHARACTERS:
            return serialized
        remaining = context.get("remaining_skill_bank")
        if isinstance(remaining, list) and remaining:
            remaining.pop()
            continue
        if "remaining_skill_bank" in context:
            del context["remaining_skill_bank"]
            continue
        job_description = context.get("job_description")
        if isinstance(job_description, dict) and job_description.get("parsed") is not None:
            job_description["parsed"] = None
            continue
        if isinstance(job_description, dict) and job_description.get("raw_text") is not None:
            job_description["raw_text"] = None
            continue
        if "job_description" in context:
            del context["job_description"]
            continue
        raise AssistantContextTooLargeError


async def build_context(session: AsyncSession, user_id: UUID, version: ResumeVersion) -> str:
    user = await session.scalar(select(User).where(User.id == user_id))
    jd = None
    if version.jd_id is not None:
        jd = await session.scalar(
            select(JobDescription).where(
                JobDescription.id == version.jd_id, JobDescription.user_id == user_id
            )
        )
    primary_education = await session.scalar(
        select(SkillBankItem)
        .where(SkillBankItem.user_id == user_id, SkillBankItem.type == "education")
        .order_by(
            SkillBankItem.end_date.desc().nullslast(),
            SkillBankItem.start_date.desc().nullslast(),
            SkillBankItem.created_at.desc(),
        )
    )
    selected_rows = list(
        (
            await session.execute(
                select(ResumeBulletSelection, BulletPoint, SkillBankItem)
                .join(BulletPoint, BulletPoint.id == ResumeBulletSelection.bullet_point_id)
                .join(SkillBankItem, SkillBankItem.id == BulletPoint.item_id)
                .where(
                    ResumeBulletSelection.resume_version_id == version.id,
                    SkillBankItem.user_id == user_id,
                )
                .order_by(ResumeBulletSelection.section_order, ResumeBulletSelection.id)
            )
        ).all()
    )
    selected_item_ids = {item.id for _, _, item in selected_rows}
    if primary_education is not None:
        selected_item_ids.add(primary_education.id)
    selected_skill_ids = {
        snapshot.get("item_id")
        for snapshot in version.selected_skills or []
        if isinstance(snapshot, dict) and isinstance(snapshot.get("item_id"), str)
    }
    remaining_query = (
        select(SkillBankItem)
        .options(selectinload(SkillBankItem.bullet_points))
        .where(SkillBankItem.user_id == user_id)
    )
    remaining = list((await session.scalars(remaining_query)).all())
    context = {
        "profile": _profile(user),
        "job_description": {
            "raw_text": jd.raw_text if jd else None,
            "parsed": jd.parsed_json if jd else None,
        },
        "current_resume": {"tex_source": version.tex_source},
        "selected_bullet_evidence": [
            {
                "item": {"type": item.type, "title": item.title, "org": item.org},
                "original_text": selection.original_text,
                "rewritten_text": selection.rewritten_text,
                "approved": selection.approved,
                "resolved": selection.resolved,
            }
            for selection, _, item in selected_rows
        ],
        "selected_skill_snapshots": [
            {"name": snapshot.get("name"), "category": snapshot.get("category")}
            for snapshot in version.selected_skills or []
            if isinstance(snapshot, dict)
        ],
        "primary_education": _remaining_item(primary_education) if primary_education else None,
        "remaining_skill_bank": [
            _remaining_item(item)
            for item in remaining
            if item.id not in selected_item_ids and str(item.id) not in selected_skill_ids
        ],
    }
    return _capped_json(context)


def _prompt(instruction: str, context: str) -> str:
    return f"""Return only a JSON object with exactly these fields:
{{"message":"short summary","tex_source":"complete replacement TeX"}}

Act as a resume TeX assistant. Use only facts in the supplied context. Preserve the existing
one-page layout and the existing header fields unless the user explicitly asks to remove an
optional header field. The TeX must compile in Tectonic untrusted mode and fit exactly one page.
Do not claim skills, metrics, employers, dates, or outcomes absent from the context.

User instruction:
{instruction}

Grounding context:
{context}"""


def _diagnostic(error: Exception) -> str:
    if isinstance(error, CompilationError):
        diagnostic: CompileDiagnostic = error.diagnostic
        line = f" at line {diagnostic.line}" if diagnostic.line is not None else ""
        return f"The proposed TeX failed {diagnostic.kind} validation{line}: {diagnostic.message}"
    if isinstance(error, InvalidAssistantPreservationError):
        return str(error)
    if isinstance(error, InvalidAssistantGroundingError):
        return str(error)
    return "The response was not valid JSON with a short message and complete TeX source"


def _visible_text(pdf: bytes) -> str:
    try:
        return " ".join(
            text for page in PdfReader(BytesIO(pdf)).pages if (text := page.extract_text())
        )
    except Exception as exc:
        raise InvalidAssistantPreservationError(
            "The compiled PDF could not be checked for required content"
        ) from exc


def _validate_preservation(pdf: bytes, context: str) -> None:
    try:
        facts = json.loads(context)
    except json.JSONDecodeError:
        return
    visible = " ".join(_visible_text(pdf).split())
    profile = facts.get("profile") if isinstance(facts, dict) else None
    if isinstance(profile, dict):
        name = profile.get("full_name") or profile.get("contact_email")
        contact_email = profile.get("contact_email")
        required_header = [
            value for value in (name, contact_email) if isinstance(value, str) and value
        ]
        if any(" ".join(value.split()) not in visible for value in required_header):
            raise InvalidAssistantPreservationError(
                "The proposed TeX must preserve the required header"
            )
    education = facts.get("primary_education") if isinstance(facts, dict) else None
    if isinstance(education, dict) and isinstance(education.get("title"), str):
        if " ".join(education["title"].split()) not in visible:
            raise InvalidAssistantPreservationError(
                "The proposed TeX must preserve the primary education"
            )


def _grounding_prompt(context: str, visible: str) -> str:
    prompt = f"""Audit the proposed resume against the supplied evidence.

Supplied evidence:
{context}

Proposed visible resume text:
{visible}

List every factual claim absent from the supplied evidence, including new employers, dates,
skills, scope, responsibilities, outcomes, and accomplishments. Be conservative. Also list every
named technology or tool in the proposed text independently of the first response. Do not treat
wording-only changes as new claims.

Return only JSON: {{"unsupported_claims":["exact phrase"],"technology_terms":["tool"]}}"""
    if len(prompt) > MAX_CONTEXT_CHARACTERS:
        raise AssistantContextTooLargeError
    return prompt


async def _validate_grounding(user_id: UUID, pdf: bytes, context: str) -> None:
    try:
        facts = json.loads(context)
    except json.JSONDecodeError:
        return
    if not isinstance(facts, dict) or not isinstance(facts.get("current_resume"), dict):
        return
    evidence = json.dumps(
        {key: facts[key] for key in _GROUNDING_EVIDENCE_KEYS if key in facts},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    visible = " ".join(_visible_text(pdf).split())
    if number_tokens(visible) - number_tokens(evidence):
        raise InvalidAssistantGroundingError(
            "The proposed resume introduced a number absent from supplied evidence"
        )
    raw = await llm_client.get_completion(
        user_id,
        [{"role": "user", "content": _grounding_prompt(evidence, visible)}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    try:
        verification = VerificationOutput.model_validate_json(raw)
    except ValidationError as exc:
        raise llm_client.LLMProviderError(
            "The LLM returned an invalid assistant guardrail check"
        ) from exc
    if verification.unsupported_claims:
        raise InvalidAssistantGroundingError(
            "The proposed resume introduced an unsupported factual claim"
        )
    if any(
        contains_term(visible, term) and not contains_term(evidence, term)
        for term in verification.technology_terms
    ):
        raise InvalidAssistantGroundingError(
            "The proposed resume introduced a technology absent from supplied evidence"
        )


async def propose(
    user_id: UUID, instruction: str, context: str, settings: Settings
) -> AssistantProposal:
    messages = [{"role": "user", "content": _prompt(instruction, context)}]
    diagnostic = ""
    for attempt in range(2):
        try:
            raw = await llm_client.get_completion(user_id, messages)
            proposal = AssistantProposal.model_validate_json(raw)
            pdf = await compile_latex_async(
                proposal.tex_source,
                settings.tectonic_binary_path,
                settings.latex_compile_timeout_seconds,
                enforce_one_page=True,
            )
            _validate_preservation(pdf, context)
            await _validate_grounding(user_id, pdf, context)
            return proposal
        except (
            ValidationError,
            CompilationError,
            InvalidAssistantPreservationError,
            InvalidAssistantGroundingError,
        ) as error:
            diagnostic = _diagnostic(error)
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": f"{diagnostic}. Correct it and return only valid JSON.",
                    }
                )
    raise InvalidAssistantProposalError(diagnostic)
