import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.api import resume_versions as resume_versions_api
from app.models.resume import JobDescription, ResumeBulletSelection, ResumeVersion
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.models.user import User
from app.schemas.resume_version import AssistantRequest
from app.services import llm_client, resume_versions, tex_assistant
from app.services.latex_compiler import CompilationError, CompileDiagnostic


class Rows:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


def source() -> str:
    return "\\documentclass{article}\\begin{document}One page\\end{document}"


def version(owner=None, **changes: object) -> ResumeVersion:
    values = {
        "id": uuid4(),
        "user_id": owner or uuid4(),
        "jd_id": uuid4(),
        "status": "compiled",
        "tex_source": source(),
        "selected_skills": [
            {
                "item_id": str(uuid4()),
                "name": "Python",
                "category": "Languages",
                "selection_order": 0,
            }
        ],
    }
    values.update(changes)
    return ResumeVersion(**values)


def request() -> AssistantRequest:
    return AssistantRequest(instruction="Make the project impact clearer.")


def test_assistant_request_requires_a_nonempty_bounded_instruction() -> None:
    with pytest.raises(ValueError):
        AssistantRequest(instruction="")
    with pytest.raises(ValueError):
        AssistantRequest(instruction="x" * 4001)


async def test_context_keeps_current_and_selected_facts_before_capping() -> None:
    owner = uuid4()
    resume = version(owner)
    profile = User(id=owner, email="owner@example.test", full_name="Ada Lovelace")
    jd = JobDescription(
        id=resume.jd_id, user_id=owner, raw_text="Build safe Python APIs", status="done"
    )
    item = SkillBankItem(id=uuid4(), user_id=owner, type="experience", title="Platform Team")
    bullet = BulletPoint(id=uuid4(), item_id=item.id, text="Reduced latency by 20%")
    selected = ResumeBulletSelection(
        id=uuid4(),
        resume_version_id=resume.id,
        bullet_point_id=bullet.id,
        original_text="Reduced latency by 20%",
        rewritten_text="Cut latency by 20%",
        approved=True,
        resolved=True,
        flagged_terms=[],
        low_effort_rewrite=False,
    )
    remaining = SkillBankItem(
        id=uuid4(),
        user_id=owner,
        type="project",
        title="remaining " + "x" * 100_000,
    )
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[profile, jd, None])
    session.execute = AsyncMock(return_value=Rows([(selected, bullet, item)]))
    session.scalars = AsyncMock(return_value=Rows([remaining]))

    context = await tex_assistant.build_context(session, owner, resume)

    assert len(context) <= tex_assistant.MAX_CONTEXT_CHARACTERS
    assert context.index("Ada Lovelace") < context.index("remaining")
    assert "Build safe Python APIs" in context
    assert "Reduced latency by 20%" in context and "Cut latency by 20%" in context
    assert "Python" in context
    assert "super-secret-provider-key" not in context


async def test_assistant_rejects_unowned_version_before_calling_provider(monkeypatch) -> None:
    owner = uuid4()
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=None))
    completion = AsyncMock()
    monkeypatch.setattr(tex_assistant.llm_client, "get_completion", completion)

    with pytest.raises(HTTPException, match="not found") as error:
        await resume_versions_api.propose_tex(
            uuid4(), request(), MagicMock(), type("User", (), {"id": owner})(), MagicMock()
        )

    assert error.value.status_code == 404
    completion.assert_not_awaited()


@pytest.mark.parametrize("status_value", ["draft", "compiling", "assembled"])
async def test_assistant_requires_a_stable_nonempty_source(monkeypatch, status_value) -> None:
    resume = version(status=status_value)
    if status_value == "assembled":
        resume.tex_source = ""
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=resume))
    completion = AsyncMock()
    monkeypatch.setattr(tex_assistant.llm_client, "get_completion", completion)

    with pytest.raises(HTTPException) as error:
        await resume_versions_api.propose_tex(
            resume.id,
            request(),
            MagicMock(),
            type("User", (), {"id": resume.user_id})(),
            MagicMock(),
        )

    assert error.value.status_code == 409
    completion.assert_not_awaited()


async def test_valid_proposal_is_returned_without_persisting_source(monkeypatch) -> None:
    resume = version()
    session = MagicMock()
    session.commit = AsyncMock()
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=resume))
    monkeypatch.setattr(tex_assistant, "build_context", AsyncMock(return_value="facts"))
    monkeypatch.setattr(
        tex_assistant.llm_client,
        "get_completion",
        AsyncMock(
            return_value=json.dumps({"message": "Tightened projects.", "tex_source": source()})
        ),
    )
    compiler = MagicMock(return_value=b"%PDF-1.4")
    monkeypatch.setattr(tex_assistant, "compile_latex", compiler)

    proposal = await resume_versions_api.propose_tex(
        resume.id,
        request(),
        session,
        type("User", (), {"id": resume.user_id})(),
        MagicMock(tectonic_binary_path="tectonic", latex_compile_timeout_seconds=30),
    )

    assert proposal.message == "Tightened projects." and proposal.tex_source == source()
    assert resume.tex_source == source() and resume.status == "compiled"
    session.commit.assert_not_awaited()
    assert compiler.call_args.args[0] == source()
    assert compiler.call_args.kwargs["enforce_one_page"] is True


async def test_invalid_schema_gets_one_correction_attempt(monkeypatch) -> None:
    resume = version()
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=resume))
    monkeypatch.setattr(tex_assistant, "build_context", AsyncMock(return_value="facts"))
    completion = AsyncMock(
        side_effect=["not json", json.dumps({"message": "Fixed.", "tex_source": source()})]
    )
    monkeypatch.setattr(tex_assistant.llm_client, "get_completion", completion)
    monkeypatch.setattr(tex_assistant, "compile_latex", MagicMock(return_value=b"%PDF-1.4"))

    result = await resume_versions_api.propose_tex(
        resume.id,
        request(),
        MagicMock(),
        type("User", (), {"id": resume.user_id})(),
        MagicMock(tectonic_binary_path="tectonic", latex_compile_timeout_seconds=30),
    )

    assert result.message == "Fixed."
    assert completion.await_count == 2
    assert "valid JSON" in completion.await_args.args[1][-1]["content"]


async def test_compile_failure_gets_one_diagnostic_correction_attempt(monkeypatch) -> None:
    resume = version()
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=resume))
    monkeypatch.setattr(tex_assistant, "build_context", AsyncMock(return_value="facts"))
    completion = AsyncMock(
        side_effect=[
            json.dumps({"message": "First.", "tex_source": "bad"}),
            json.dumps({"message": "Fixed.", "tex_source": source()}),
        ]
    )
    compiler = MagicMock(
        side_effect=[
            CompilationError(CompileDiagnostic("syntax", "Undefined control sequence", 4)),
            b"%PDF-1.4",
        ]
    )
    monkeypatch.setattr(tex_assistant.llm_client, "get_completion", completion)
    monkeypatch.setattr(tex_assistant, "compile_latex", compiler)
    result = await resume_versions_api.propose_tex(
        resume.id,
        request(),
        MagicMock(),
        type("User", (), {"id": resume.user_id})(),
        MagicMock(tectonic_binary_path="tectonic", latex_compile_timeout_seconds=30),
    )

    assert result.message == "Fixed."
    assert "Undefined control sequence" in completion.await_args.args[1][-1]["content"]


async def test_two_multi_page_proposals_are_rejected_without_writes(monkeypatch) -> None:
    resume = version()
    session = MagicMock()
    session.commit = AsyncMock()
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=resume))
    monkeypatch.setattr(tex_assistant, "build_context", AsyncMock(return_value="facts"))
    monkeypatch.setattr(
        tex_assistant.llm_client,
        "get_completion",
        AsyncMock(return_value=json.dumps({"message": "Too long.", "tex_source": source()})),
    )
    monkeypatch.setattr(
        tex_assistant,
        "compile_latex",
        MagicMock(
            side_effect=CompilationError(
                CompileDiagnostic("layout", "Resume must fit exactly one page")
            )
        ),
    )

    with pytest.raises(HTTPException, match="one page") as error:
        await resume_versions_api.propose_tex(
            resume.id,
            request(),
            session,
            type("User", (), {"id": resume.user_id})(),
            MagicMock(tectonic_binary_path="tectonic", latex_compile_timeout_seconds=30),
        )

    assert error.value.status_code == 422
    assert resume.tex_source == source() and resume.status == "compiled"
    session.commit.assert_not_awaited()


async def test_provider_failures_are_a_safe_gateway_error(monkeypatch) -> None:
    resume = version()
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=resume))
    monkeypatch.setattr(tex_assistant, "build_context", AsyncMock(return_value="facts"))
    monkeypatch.setattr(
        tex_assistant.llm_client,
        "get_completion",
        AsyncMock(side_effect=llm_client.LLMProviderError("provider detail")),
    )

    with pytest.raises(HTTPException, match="Unable to generate") as error:
        await resume_versions_api.propose_tex(
            resume.id,
            request(),
            MagicMock(),
            type("User", (), {"id": resume.user_id})(),
            MagicMock(),
        )

    assert error.value.status_code == 502


def test_context_cap_drops_remaining_evidence_before_current_or_selected_facts() -> None:
    current = "CURRENT-" + "x" * 70_000
    selected = "SELECTED-" + "y" * 1_000
    context = {
        "current_resume": {"tex_source": current},
        "selected_bullet_evidence": [{"original_text": selected}],
        "remaining_skill_bank": [{"title": "REMAINING-" + "z" * 20_000}],
    }

    capped = tex_assistant._capped_json(context)

    assert current in capped and selected in capped
    assert "REMAINING-" not in capped


def test_context_cap_makes_no_progress_for_empty_strings() -> None:
    assert tex_assistant._shrink({"text": ""}, 1) is False


def test_pathological_structural_context_over_cap_terminates() -> None:
    context = {
        "current_resume": {"tex_source": ""},
        "selected_bullet_evidence": [{"text": ""}] * 20_000,
        "remaining_skill_bank": [],
    }

    assert tex_assistant._capped_json(context) == "{}"


async def test_context_uses_account_email_when_contact_email_is_unset() -> None:
    owner = uuid4()
    resume = version(owner)
    profile = User(id=owner, email="account@example.test", full_name="Ada")
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[profile, None, None])
    session.execute = AsyncMock(return_value=Rows([]))
    session.scalars = AsyncMock(return_value=Rows([]))

    context = json.loads(await tex_assistant.build_context(session, owner, resume))

    assert context["profile"]["contact_email"] == "account@example.test"


async def test_context_uses_the_same_primary_education_ordering_as_assembly() -> None:
    owner = uuid4()
    resume = version(owner)
    profile = User(id=owner, email="owner@example.test")
    education = SkillBankItem(
        id=uuid4(), user_id=owner, type="education", title="BSc Computer Science"
    )
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[profile, None, education])
    session.execute = AsyncMock(return_value=Rows([]))
    session.scalars = AsyncMock(return_value=Rows([]))

    context = json.loads(await tex_assistant.build_context(session, owner, resume))

    sql = str(session.scalar.await_args_list[2].args[0].compile(dialect=postgresql.dialect()))
    assert "skill_bank_items.end_date DESC NULLS LAST" in sql
    assert "skill_bank_items.start_date DESC NULLS LAST" in sql
    assert "skill_bank_items.created_at DESC" in sql
    assert context["primary_education"]["title"] == "BSc Computer Science"


def preservation_context() -> str:
    return json.dumps(
        {
            "profile": {"full_name": "Ada Lovelace", "contact_email": "ada@example.test"},
            "primary_education": {"title": "BSc Computer Science"},
        }
    )


def preserved_source() -> str:
    return source() + " Ada Lovelace ada@example.test BSc Computer Science"


@pytest.mark.parametrize(
    "missing",
    [
        source() + " BSc Computer Science",
        source() + " Ada Lovelace ada@example.test",
    ],
)
async def test_missing_required_header_or_education_retries_then_returns_422(
    monkeypatch, missing
) -> None:
    resume = version()
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=resume))
    monkeypatch.setattr(
        tex_assistant, "build_context", AsyncMock(return_value=preservation_context())
    )
    completion = AsyncMock(
        return_value=json.dumps({"message": "Missing required content.", "tex_source": missing})
    )
    monkeypatch.setattr(tex_assistant.llm_client, "get_completion", completion)
    monkeypatch.setattr(tex_assistant, "compile_latex", MagicMock(return_value=b"%PDF-1.4"))

    with pytest.raises(HTTPException) as error:
        await resume_versions_api.propose_tex(
            resume.id,
            request(),
            MagicMock(),
            type("User", (), {"id": resume.user_id})(),
            MagicMock(tectonic_binary_path="tectonic", latex_compile_timeout_seconds=30),
        )

    assert error.value.status_code == 422
    assert completion.await_count == 2


async def test_proposal_preserving_required_header_and_education_passes(monkeypatch) -> None:
    completion = AsyncMock(
        return_value=json.dumps(
            {"message": "Preserved required facts.", "tex_source": preserved_source()}
        )
    )
    monkeypatch.setattr(tex_assistant.llm_client, "get_completion", completion)
    monkeypatch.setattr(tex_assistant, "compile_latex", MagicMock(return_value=b"%PDF-1.4"))

    proposal = await tex_assistant.propose(
        uuid4(),
        request().instruction,
        preservation_context(),
        MagicMock(tectonic_binary_path="tectonic", latex_compile_timeout_seconds=30),
    )

    assert proposal.tex_source == preserved_source()
    assert completion.await_count == 1
