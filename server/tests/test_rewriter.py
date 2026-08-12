import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services import llm_client, rewriter

ORIGINAL_CICD = (
    "Developed a comprehensive CI/CD pipeline in GitHub Actions that automated build and "
    "deployment processes, decreasing release cycles by 40% for new features."
)
TRIVIAL_CICD = (
    "Implemented a comprehensive CI/CD pipeline in GitHub Actions that automated build and "
    "deployment processes, decreasing release cycles by 40% for new features."
)
RESTRUCTURED_CICD = (
    "Engineered and automated an end-to-end CI/CD pipeline using GitHub Actions, streamlining "
    "build and deployment workflows and cutting release cycle time by 40%."
)


def rewrite_batch(text: str, technology_terms: list[str] | None = None) -> str:
    return json.dumps(
        {
            "rewrites": [
                {
                    "index": 0,
                    "rewritten_text": text,
                    "technology_terms": technology_terms or [],
                }
            ]
        }
    )


def verification_batch(technology_terms: list[str] | None = None) -> str:
    return json.dumps(
        {
            "verifications": [
                {
                    "index": 0,
                    "unsupported_claims": [],
                    "technology_terms": technology_terms or [],
                }
            ]
        }
    )


@pytest.mark.parametrize(
    ("original", "proposed"),
    [
        ("Reduced API latency", "Reduced API latency by 20%"),
        ("Reduced API latency by 20%", "Reduced API latency"),
        ("Reduced API latency by 20%", "Reduced API latency by 35%"),
    ],
)
def test_new_removed_or_changed_number_is_blocked(original: str, proposed: str) -> None:
    rewritten, flags = rewriter.guard_rewrite(original, proposed, [], [])

    assert rewritten == original
    assert [flag["reason"] for flag in flags] == ["number_changed"]


def test_new_technology_is_flagged_but_kept_for_review() -> None:
    rewritten, flags = rewriter.guard_rewrite(
        "Built batch data pipelines",
        "Built Spark batch data pipelines",
        ["Spark"],
        [],
    )

    assert rewritten == "Built Spark batch data pipelines"
    assert flags[0]["term"] == "Spark"
    assert flags[0]["reason"] == "new_technology"


def test_user_tagged_technology_is_not_flagged() -> None:
    rewritten, flags = rewriter.guard_rewrite(
        "Built batch data pipelines",
        "Built Spark batch data pipelines",
        ["Spark"],
        ["spark"],
    )

    assert rewritten == "Built Spark batch data pipelines"
    assert flags == []


def test_unsupported_claim_is_blocked() -> None:
    original = "Built an internal API"

    rewritten, flags = rewriter.guard_rewrite(
        original,
        "Led a team building a global internal API",
        [],
        [],
        ["Led a team", "global"],
    )

    assert rewritten == original
    assert {flag["reason"] for flag in flags} == {"unsupported_claim"}


def test_opening_verb_swap_is_a_trivial_rewrite() -> None:
    assert rewriter.is_trivial_rewrite(ORIGINAL_CICD, TRIVIAL_CICD) is True


def test_restructured_sentence_is_not_a_trivial_rewrite() -> None:
    assert rewriter.is_trivial_rewrite(ORIGINAL_CICD, RESTRUCTURED_CICD) is False


async def test_clean_rewrite_uses_action_verb_without_flags(monkeypatch) -> None:
    completion = AsyncMock(
        side_effect=[
            '{"rewritten_text":"Collaborated with product and design teams","technology_terms":[]}',
            '{"unsupported_claims":[]}',
        ]
    )
    monkeypatch.setattr(llm_client, "get_completion", completion)

    rewritten, flags = await rewriter.rewrite_bullet(
        uuid4(),
        "Worked with product and design teams",
        ["Cross-functional collaboration"],
        ["Collaborated"],
        [],
    )

    assert rewritten == "Collaborated with product and design teams"
    assert flags == []
    assert completion.await_count == 2


async def test_independent_verifier_can_flag_omitted_technology(monkeypatch) -> None:
    completion = AsyncMock(
        side_effect=[
            '{"rewritten_text":"Built Spark data pipelines","technology_terms":[]}',
            '{"unsupported_claims":[],"technology_terms":["Spark"]}',
        ]
    )
    monkeypatch.setattr(llm_client, "get_completion", completion)

    rewritten, flags = await rewriter.rewrite_bullet(
        uuid4(), "Built data pipelines", ["Apache Spark"], [], []
    )

    assert rewritten == "Built Spark data pipelines"
    assert [(flag["term"], flag["reason"]) for flag in flags] == [("Spark", "new_technology")]


async def test_numeric_violation_skips_claim_verifier(monkeypatch) -> None:
    completion = AsyncMock(
        return_value='{"rewritten_text":"Improved uptime by 99%","technology_terms":[]}'
    )
    monkeypatch.setattr(llm_client, "get_completion", completion)

    rewritten, flags = await rewriter.rewrite_bullet(uuid4(), "Improved uptime", [], [], [])

    assert rewritten == "Improved uptime"
    assert flags[0]["reason"] == "number_changed"
    completion.assert_awaited_once()


async def test_batch_rewrite_uses_two_provider_calls_for_multiple_bullets(monkeypatch) -> None:
    completion = AsyncMock(
        side_effect=[
            '{"rewrites":['
            '{"index":0,"rewritten_text":"Designed and delivered the internal API","technology_terms":[]},'
            '{"index":1,"rewritten_text":"Partnered across product teams","technology_terms":[]}'
            "]}",
            '{"verifications":['
            '{"index":0,"unsupported_claims":[],"technology_terms":[]},'
            '{"index":1,"unsupported_claims":[],"technology_terms":[]}'
            "]}",
        ]
    )
    monkeypatch.setattr(llm_client, "get_completion", completion)

    results = await rewriter.rewrite_bullets(
        uuid4(),
        ["Built an internal API", "Worked with product teams"],
        ["API design", "Cross-functional collaboration"],
        ["Designed", "Collaborated"],
        [],
        [],
    )

    assert [text for text, _, _ in results] == [
        "Designed and delivered the internal API",
        "Partnered across product teams",
    ]
    assert completion.await_count == 2


async def test_trivial_batch_rewrite_retries_once_and_marks_still_trivial(monkeypatch) -> None:
    completion = AsyncMock(
        side_effect=[
            rewrite_batch(TRIVIAL_CICD),
            verification_batch(),
            rewrite_batch(TRIVIAL_CICD),
            verification_batch(),
        ]
    )
    monkeypatch.setattr(llm_client, "get_completion", completion)

    [(rewritten, flags, low_effort)] = await rewriter.rewrite_bullets(
        uuid4(), [ORIGINAL_CICD], ["CI/CD"], ["Engineered"], ["automation"], []
    )

    assert rewritten == TRIVIAL_CICD
    assert flags == []
    assert low_effort is True
    assert completion.await_count == 4
    retry_messages = completion.await_args_list[2].args[1]
    assert "Substantively restructure" in retry_messages[-1]["content"]


async def test_retried_rewrite_with_changed_numbers_keeps_safe_first_attempt(monkeypatch) -> None:
    unsafe = RESTRUCTURED_CICD.replace("40%", "50%")
    completion = AsyncMock(
        side_effect=[
            rewrite_batch(TRIVIAL_CICD),
            verification_batch(),
            rewrite_batch(unsafe),
        ]
    )
    monkeypatch.setattr(llm_client, "get_completion", completion)

    [(rewritten, flags, low_effort)] = await rewriter.rewrite_bullets(
        uuid4(), [ORIGINAL_CICD], ["CI/CD"], ["Engineered"], ["automation"], []
    )

    assert rewritten == TRIVIAL_CICD
    assert flags == []
    assert low_effort is True
    assert completion.await_count == 3


async def test_retried_rewrite_is_checked_for_new_technologies(monkeypatch) -> None:
    unsafe = RESTRUCTURED_CICD.replace("GitHub Actions", "GitHub Actions and Jenkins")
    completion = AsyncMock(
        side_effect=[
            rewrite_batch(TRIVIAL_CICD),
            verification_batch(),
            rewrite_batch(unsafe, ["GitHub Actions", "Jenkins"]),
            verification_batch(["GitHub Actions", "Jenkins"]),
        ]
    )
    monkeypatch.setattr(llm_client, "get_completion", completion)

    [(rewritten, flags, low_effort)] = await rewriter.rewrite_bullets(
        uuid4(), [ORIGINAL_CICD], ["CI/CD"], ["Engineered"], ["automation"], []
    )

    assert rewritten == unsafe
    assert [(flag["term"], flag["reason"]) for flag in flags] == [("Jenkins", "new_technology")]
    assert low_effort is False
    assert completion.await_count == 4


def test_batch_prompt_lists_extracted_jd_language_and_restructuring_example() -> None:
    prompt = rewriter.batch_rewrite_prompt(
        [ORIGINAL_CICD], ["CI/CD"], ["Engineered"], ["automation"], ["GitHub Actions"]
    )

    assert "Required skills: ['CI/CD']" in prompt
    assert "JD ATS keywords: ['automation']" in prompt
    assert "Available JD action verbs: ['Engineered']" in prompt
    assert "do not simply substitute the opening verb" in prompt
    assert "Bad rewrite" in prompt and "Good rewrite" in prompt


def test_rewrite_prompt_contains_safety_rules() -> None:
    prompt = rewriter.rewrite_prompt("Built API", ["API design"], ["Designed"], [])

    assert "Preserve every fact" in prompt
    assert "Preserve every number and metric exactly" in prompt
    assert "Never add or change a technology" in prompt
