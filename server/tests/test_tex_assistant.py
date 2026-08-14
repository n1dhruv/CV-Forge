import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

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
    session.scalar = AsyncMock(side_effect=[profile, jd])
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
