import json
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.models.resume import JobDescription, ResumeBulletSelection, ResumeVersion
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.models.user import User
from app.schemas.resume_version import AssistantProposal
from app.services import llm_client
from app.services.latex_compiler import CompilationError, CompileDiagnostic, compile_latex

MAX_CONTEXT_CHARACTERS = 80_000


class InvalidAssistantProposalError(Exception):
    def __init__(self, diagnostic: str) -> None:
        super().__init__(diagnostic)
        self.diagnostic = diagnostic


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
    return {field: getattr(user, field, None) for field in fields}


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


def _string_locations(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, str):
                yield value, key, child
            else:
                yield from _string_locations(child)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, str):
                yield value, index, child
            else:
                yield from _string_locations(child)


def _shrink(value: Any, overflow: int) -> bool:
    locations = list(_string_locations(value))
    if not locations:
        return False
    container, key, text = max(locations, key=lambda item: len(item[2]))
    marker = " [truncated]"
    target = len(text) - overflow - 64
    container[key] = text[: target - len(marker)] + marker if target > len(marker) else ""
    return True


def _capped_json(context: dict[str, Any]) -> str:
    while True:
        serialized = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
        if len(serialized) <= MAX_CONTEXT_CHARACTERS:
            return serialized
        if not _shrink(context, len(serialized) - MAX_CONTEXT_CHARACTERS):
            remaining = context["remaining_skill_bank"]
            if remaining:
                remaining.pop()
                continue
            return json.dumps({}, separators=(",", ":"))


async def build_context(session: AsyncSession, user_id: UUID, version: ResumeVersion) -> str:
    user = await session.scalar(select(User).where(User.id == user_id))
    jd = None
    if version.jd_id is not None:
        jd = await session.scalar(
            select(JobDescription).where(
                JobDescription.id == version.jd_id, JobDescription.user_id == user_id
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
            snapshot for snapshot in version.selected_skills or [] if isinstance(snapshot, dict)
        ],
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
    return "The response was not valid JSON with a short message and complete TeX source"


async def propose(
    user_id: UUID, instruction: str, context: str, settings: Settings
) -> AssistantProposal:
    messages = [{"role": "user", "content": _prompt(instruction, context)}]
    diagnostic = ""
    for attempt in range(2):
        try:
            raw = await llm_client.get_completion(user_id, messages)
            proposal = AssistantProposal.model_validate_json(raw)
            compile_latex(
                proposal.tex_source,
                settings.tectonic_binary_path,
                settings.latex_compile_timeout_seconds,
                enforce_one_page=True,
            )
            return proposal
        except (ValidationError, CompilationError) as error:
            diagnostic = _diagnostic(error)
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": f"{diagnostic}. Correct it and return only valid JSON.",
                    }
                )
    raise InvalidAssistantProposalError(diagnostic)
