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
    with pytest.raises(ValueError):
        AssistantRequest(instruction="   ")


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
    compiler = AsyncMock(return_value=b"%PDF-1.4")
    blocking_compiler = MagicMock(return_value=b"%PDF-1.4")
    monkeypatch.setattr(tex_assistant, "compile_latex_async", compiler, raising=False)
    monkeypatch.setattr(tex_assistant, "compile_latex", blocking_compiler, raising=False)

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
    assert compiler.await_args.args[0] == source()
    assert compiler.await_args.kwargs["enforce_one_page"] is True
    blocking_compiler.assert_not_called()


async def test_invalid_schema_gets_one_correction_attempt(monkeypatch) -> None:
    resume = version()
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=resume))
    monkeypatch.setattr(tex_assistant, "build_context", AsyncMock(return_value="facts"))
    completion = AsyncMock(
        side_effect=["not json", json.dumps({"message": "Fixed.", "tex_source": source()})]
    )
    monkeypatch.setattr(tex_assistant.llm_client, "get_completion", completion)
    monkeypatch.setattr(
        tex_assistant, "compile_latex_async", AsyncMock(return_value=b"%PDF-1.4")
    )

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
    compiler = AsyncMock(
        side_effect=[
            CompilationError(CompileDiagnostic("syntax", "Undefined control sequence", 4)),
            b"%PDF-1.4",
        ]
    )
    monkeypatch.setattr(tex_assistant.llm_client, "get_completion", completion)
    monkeypatch.setattr(tex_assistant, "compile_latex_async", compiler)
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
        "compile_latex_async",
        AsyncMock(
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


def test_context_cap_drops_job_description_before_mandatory_facts() -> None:
    current = "CURRENT-" + "x" * 70_000
    selected = "SELECTED-" + "y" * 1_000
    context = {
        "current_resume": {"tex_source": current},
        "selected_bullet_evidence": [{"original_text": selected}],
        "job_description": {"raw_text": "JD-" + "z" * 20_000, "parsed": None},
        "remaining_skill_bank": [],
    }

    capped = tex_assistant._capped_json(context)

    assert current in capped and selected in capped
    assert "JD-" not in capped


def test_pathological_structural_context_over_cap_terminates() -> None:
    context = {
        "current_resume": {"tex_source": ""},
        "selected_bullet_evidence": [{"text": ""}] * 20_000,
        "remaining_skill_bank": [],
    }

    with pytest.raises(tex_assistant.AssistantContextTooLargeError):
        tex_assistant._capped_json(context)


def test_mandatory_context_over_cap_is_rejected_instead_of_truncated() -> None:
    context = {
        "current_resume": {"tex_source": "CURRENT-" + "x" * 80_000},
        "selected_bullet_evidence": [{"original_text": "SELECTED"}],
        "remaining_skill_bank": [],
    }

    with pytest.raises(tex_assistant.AssistantContextTooLargeError):
        tex_assistant._capped_json(context)


async def test_context_too_large_is_a_safe_client_error(monkeypatch) -> None:
    resume = version()
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=resume))
    monkeypatch.setattr(
        tex_assistant,
        "build_context",
        AsyncMock(side_effect=tex_assistant.AssistantContextTooLargeError()),
    )

    with pytest.raises(HTTPException) as error:
        await resume_versions_api.propose_tex(
            resume.id,
            request(),
            MagicMock(),
            type("User", (), {"id": resume.user_id})(),
            MagicMock(),
        )

    assert error.value.status_code == 422
    assert "too large" in error.value.detail.lower()


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


@pytest.mark.parametrize(
    ("visible", "verification", "diagnostic"),
    [
        (
            "Built Python APIs at Acme in 2024, improving uptime by 99%",
            {"unsupported_claims": [], "technology_terms": ["Python"]},
            "number",
        ),
        (
            "Built Python APIs at Acme in 2025, improving uptime by 20%",
            {"unsupported_claims": [], "technology_terms": ["Python"]},
            "number",
        ),
        (
            "Built Python APIs at Acme for 5 years, improving uptime by 20%",
            {"unsupported_claims": [], "technology_terms": ["Python"]},
            "number",
        ),
        (
            "Built Python APIs at Globex in 2024, improving uptime by 20%",
            {"unsupported_claims": ["Globex"], "technology_terms": ["Python"]},
            "unsupported",
        ),
        (
            "Built Python and Rust APIs at Acme in 2024, improving uptime by 20%",
            {"unsupported_claims": [], "technology_terms": ["Python", "Rust"]},
            "technology",
        ),
        (
            "Built Python APIs at Acme in 2024, doubling revenue and improving uptime by 20%",
            {"unsupported_claims": ["doubling revenue"], "technology_terms": ["Python"]},
            "unsupported",
        ),
    ],
)
async def test_new_protected_facts_are_rejected_after_one_correction(
    monkeypatch, visible, verification, diagnostic
) -> None:
    context = json.dumps(
        {
            "current_resume": {
                "tex_source": "Built Python APIs at Acme in 2024, improving uptime by 20%"
            },
            "job_description": {"raw_text": "Seeking Rust expertise and 5 years experience"},
            "selected_bullet_evidence": [],
            "selected_skill_snapshots": [{"name": "Python"}],
        }
    )
    proposal = json.dumps({"message": "Updated.", "tex_source": source()})

    async def completion(user_id, messages, **kwargs):
        del user_id, kwargs
        if "Audit the proposed resume" in messages[-1]["content"]:
            return json.dumps(verification)
        return proposal

    monkeypatch.setattr(tex_assistant.llm_client, "get_completion", completion)
    monkeypatch.setattr(
        tex_assistant, "compile_latex_async", AsyncMock(return_value=b"%PDF-1.4"), raising=False
    )
    monkeypatch.setattr(
        tex_assistant, "PdfReader", lambda _: rendered_pdf(visible), raising=False
    )

    with pytest.raises(tex_assistant.InvalidAssistantProposalError) as error:
        await tex_assistant.propose(
            uuid4(),
            request().instruction,
            context,
            MagicMock(tectonic_binary_path="tectonic", latex_compile_timeout_seconds=30),
        )

    assert diagnostic in error.value.diagnostic.lower()


def preservation_context() -> str:
    return json.dumps(
        {
            "profile": {"full_name": "Ada Lovelace", "contact_email": "ada@example.test"},
            "primary_education": {"title": "BSc Computer Science"},
        }
    )


def preserved_source() -> str:
    return (
        "\\documentclass{article}\\begin{document}"
        "Ada Lovelace ada@example.test BSc Computer Science"
        "\\end{document}"
    )


def rendered_pdf(text: str):
    page = type("Page", (), {"extract_text": lambda self: text})()
    return type("Pdf", (), {"pages": [page]})()


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
    monkeypatch.setattr(
        tex_assistant, "compile_latex_async", AsyncMock(return_value=b"%PDF-1.4")
    )
    monkeypatch.setattr(
        tex_assistant, "PdfReader", lambda _: rendered_pdf("missing"), raising=False
    )

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
    monkeypatch.setattr(
        tex_assistant, "compile_latex_async", AsyncMock(return_value=b"%PDF-1.4")
    )
    monkeypatch.setattr(
        tex_assistant,
        "PdfReader",
        lambda _: rendered_pdf("Ada Lovelace ada@example.test BSc Computer Science"),
        raising=False,
    )

    proposal = await tex_assistant.propose(
        uuid4(),
        request().instruction,
        preservation_context(),
        MagicMock(tectonic_binary_path="tectonic", latex_compile_timeout_seconds=30),
    )

    assert proposal.tex_source == preserved_source()
    assert completion.await_count == 1


@pytest.mark.parametrize(
    "hidden_source",
    [
        source() + "% Ada Lovelace ada@example.test BSc Computer Science\n",
        source() + " Ada Lovelace ada@example.test BSc Computer Science",
    ],
)
async def test_comment_or_post_document_preservation_is_rejected(
    monkeypatch, hidden_source
) -> None:
    completion = AsyncMock(
        return_value=json.dumps({"message": "Hidden required facts.", "tex_source": hidden_source})
    )
    monkeypatch.setattr(tex_assistant.llm_client, "get_completion", completion)
    monkeypatch.setattr(
        tex_assistant, "compile_latex_async", AsyncMock(return_value=b"%PDF-1.4")
    )
    monkeypatch.setattr(
        tex_assistant, "PdfReader", lambda _: rendered_pdf("visible only"), raising=False
    )

    with pytest.raises(tex_assistant.InvalidAssistantProposalError):
        await tex_assistant.propose(
            uuid4(),
            request().instruction,
            preservation_context(),
            MagicMock(tectonic_binary_path="tectonic", latex_compile_timeout_seconds=30),
        )

    assert completion.await_count == 2
