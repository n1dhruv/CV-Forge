import json
import re
from collections import Counter
from difflib import SequenceMatcher
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError

from app.services import llm_client

NUMBER_PATTERN = re.compile(
    r"(?<![\w.])(?:[$€£]\s*)?\d+(?:[,.]\d+)*(?:\s?(?:%|[kKmMbB]|x|\+))?(?!\w)"
)
WORD_PATTERN = re.compile(r"[a-z0-9]+(?:[+/#.-][a-z0-9]+)*")
# Calibrated examples: opening-verb swap = 0.045 change; substantive rephrase = 0.545.
TRIVIAL_REWRITE_MIN_CHANGE_RATIO = 0.35
BLOCKING_FLAG_REASONS = {"number_changed", "unsupported_claim"}


class RewriteOutput(BaseModel):
    rewritten_text: str = Field(min_length=1)
    technology_terms: list[str] = Field(default_factory=list)


class VerificationOutput(BaseModel):
    unsupported_claims: list[str] = Field(default_factory=list)
    technology_terms: list[str] = Field(default_factory=list)


class BatchRewriteItem(RewriteOutput):
    index: int = Field(ge=0)


class BatchRewriteOutput(BaseModel):
    rewrites: list[BatchRewriteItem]


class BatchVerificationItem(VerificationOutput):
    index: int = Field(ge=0)


class BatchVerificationOutput(BaseModel):
    verifications: list[BatchVerificationItem]


def number_tokens(text: str) -> Counter[str]:
    return Counter(re.sub(r"\s+", "", match).casefold() for match in NUMBER_PATTERN.findall(text))


def contains_term(text: str, term: str) -> bool:
    return bool(
        term.strip() and re.search(rf"(?<!\w){re.escape(term.strip())}(?!\w)", text, re.IGNORECASE)
    )


def is_trivial_rewrite(
    original: str,
    rewritten: str,
    min_change_ratio: float = TRIVIAL_REWRITE_MIN_CHANGE_RATIO,
) -> bool:
    return rewrite_change_ratio(original, rewritten) < min_change_ratio


def rewrite_change_ratio(original: str, rewritten: str) -> float:
    original_words = WORD_PATTERN.findall(original.casefold())
    rewritten_words = WORD_PATTERN.findall(rewritten.casefold())
    if original_words[1:] == rewritten_words[1:]:
        return 0.0
    similarity = SequenceMatcher(None, original_words, rewritten_words).ratio()
    return 1 - similarity


def _is_blocked(flags: list[dict[str, str]]) -> bool:
    return any(flag["reason"] in BLOCKING_FLAG_REASONS for flag in flags)


def guard_rewrite(
    original: str,
    rewritten: str,
    technology_terms: list[str],
    allowed_skills: list[str],
    unsupported_claims: list[str] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    flags: list[dict[str, str]] = []
    if number_tokens(original) != number_tokens(rewritten):
        flags.append(
            {
                "term": ", ".join(sorted(set(NUMBER_PATTERN.findall(rewritten + " " + original)))),
                "reason": "number_changed",
                "message": "The rewrite changed, added, or removed a number and was blocked.",
            }
        )
        return original, flags

    allowed = {skill.casefold().strip() for skill in allowed_skills}
    for term in dict.fromkeys(term.strip() for term in technology_terms if term.strip()):
        if (
            contains_term(rewritten, term)
            and not contains_term(original, term)
            and term.casefold() not in allowed
        ):
            flags.append(
                {
                    "term": term,
                    "reason": "new_technology",
                    "message": "This technology was not in the original bullet or your tagged skills.",
                }
            )

    claims = [claim.strip() for claim in unsupported_claims or [] if claim.strip()]
    if claims:
        flags.extend(
            {
                "term": claim,
                "reason": "unsupported_claim",
                "message": "The rewrite added an unsupported claim and was blocked.",
            }
            for claim in claims
        )
        return original, flags
    return rewritten.strip(), flags


def rewrite_prompt(
    original: str, requirements: list[str], action_verbs: list[str], allowed_skills: list[str]
) -> str:
    return f"""Rewrite one resume bullet to better mirror the job description.

Original bullet:
{original}

Job requirements: {requirements}
Preferred action verbs: {action_verbs}
User-tagged skills: {allowed_skills}

Rules:
- Preserve every fact. Never add or change a technology, tool, employer, scope, responsibility, or claim.
- Preserve every number and metric exactly; never add or remove one.
- You may use a preferred action verb only when it is a genuine synonym for work already stated.
- If a safe improvement is not possible, return the original or make only trivial wording changes.
- technology_terms must list every named technology or tool present in rewritten_text.

Return only JSON:
{{"rewritten_text":"...","technology_terms":["..."]}}"""


def verification_prompt(original: str, rewritten: str) -> str:
    return f"""Compare this resume rewrite with its source.

Original: {original}
Rewrite: {rewritten}

List every new factual claim in the rewrite that is not supported by the original, including new
employers, ownership, scale, scope, outcomes, responsibilities, methods, or accomplishments.
Do not list wording-only changes, genuine synonyms, numbers, or named technologies; those are checked
separately. Be conservative: when uncertain, list the questionable phrase.

Also list every named technology or tool in the rewrite, independently of the first response.

Return only JSON: {{"unsupported_claims":["exact phrase"],"technology_terms":["tool"]}}"""


def batch_rewrite_prompt(
    originals: list[str],
    required_skills: list[str],
    action_verbs: list[str],
    ats_keywords: list[str],
    allowed_skills: list[str],
) -> str:
    bullets = [{"index": index, "original_text": text} for index, text in enumerate(originals)]
    return f"""Rewrite each resume bullet to better mirror the job description.

Bullets: {json.dumps(bullets)}
Required skills: {required_skills}
JD ATS keywords: {ats_keywords}
Available JD action verbs: {action_verbs}
User-tagged skills: {allowed_skills}

Rules:
- Return exactly one rewrite for every input index, in the same order.
- Rewrite the full sentence structure — do not simply substitute the opening verb and leave the rest of the sentence unchanged.
- Vary sentence structure, reorder clauses where it improves clarity, and integrate the JD's language throughout, not only at the start.
- From the action verbs and keywords, use any that authentically describe what the bullet already states.
- Do not use a keyword or verb that implies a skill, tool, or scope beyond the original. For example, do not add DevOps or continuous integration unless the original genuinely supports that framing.
- Preserve every fact. Never add or change a technology, tool, employer, scope, responsibility, or claim.
- Preserve every number and metric exactly; never add or remove one.
- You may use a preferred action verb only when it is a genuine synonym for work already stated.
- If a safe improvement is not possible, return the original or make only trivial wording changes.
- technology_terms must list every named technology or tool present in rewritten_text.

Bad rewrite (do not do this — only the first word changed):
Original: "Developed a comprehensive CI/CD pipeline in GitHub Actions..."
Bad:      "Implemented a comprehensive CI/CD pipeline in GitHub Actions..."

Good rewrite (restructured, uses JD language naturally, same facts):
Original: "Developed a comprehensive CI/CD pipeline in GitHub Actions that automated build and deployment processes, decreasing release cycles by 40% for new features."
Good:     "Engineered and automated an end-to-end CI/CD pipeline using GitHub Actions, streamlining build and deployment workflows and cutting release cycle time by 40%."

Return only JSON:
{{"rewrites":[{{"index":0,"rewritten_text":"...","technology_terms":["..."]}}]}}"""


def batch_verification_prompt(originals: list[str], rewrites: list[BatchRewriteItem]) -> str:
    pairs = [
        {
            "index": rewrite.index,
            "original": originals[rewrite.index],
            "rewrite": rewrite.rewritten_text,
        }
        for rewrite in rewrites
    ]
    return f"""Compare each resume rewrite with its source.

Pairs: {json.dumps(pairs)}

For every index, list each new factual claim in the rewrite that is not supported by the original,
including new employers, ownership, scale, scope, outcomes, responsibilities, methods, or
accomplishments. Do not list wording-only changes, genuine synonyms, numbers, or named
technologies; those are checked separately. Be conservative: when uncertain, list the
questionable phrase.

Also list every named technology or tool in each rewrite, independently of the first response.
Return exactly one verification for every input index.

Return only JSON:
{{"verifications":[{{"index":0,"unsupported_claims":["exact phrase"],"technology_terms":["tool"]}}]}}"""


def retry_trivial_prompt(indices: set[int]) -> str:
    return f"""Your previous rewrites for indexes {sorted(indices)} only made minor wording changes.
Substantively restructure each sentence and incorporate more of the provided action verbs and
keywords where truthful. Do not just swap one word. Preserve all facts, technologies, scope,
numbers, and metrics exactly. Return the complete rewrites array for every original index again."""


def _parse_rewrite_batch(raw: str, expected: set[int]) -> dict[int, BatchRewriteItem]:
    try:
        proposed = BatchRewriteOutput.model_validate_json(raw)
    except ValidationError as exc:
        raise llm_client.LLMProviderError("The LLM returned an invalid rewrite batch") from exc
    rewrites = {item.index: item for item in proposed.rewrites}
    if len(rewrites) != len(proposed.rewrites) or set(rewrites) != expected:
        raise llm_client.LLMProviderError("The LLM returned an incomplete rewrite batch")
    return rewrites


async def _guard_batch(
    user_id: UUID,
    originals: list[str],
    rewrites: dict[int, BatchRewriteItem],
    allowed_skills: list[str],
    known_technologies: list[str],
) -> dict[int, tuple[str, list[dict[str, str]]]]:
    results: dict[int, tuple[str, list[dict[str, str]]]] = {}
    safe_rewrites = []
    for index, rewrite in rewrites.items():
        if number_tokens(originals[index]) != number_tokens(rewrite.rewritten_text):
            results[index] = guard_rewrite(
                originals[index],
                rewrite.rewritten_text,
                rewrite.technology_terms,
                allowed_skills,
            )
        else:
            safe_rewrites.append(rewrite)

    if not safe_rewrites:
        return results
    verification_raw = await llm_client.get_completion(
        user_id,
        [{"role": "user", "content": batch_verification_prompt(originals, safe_rewrites)}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    expected = {rewrite.index for rewrite in safe_rewrites}
    try:
        verified = BatchVerificationOutput.model_validate_json(verification_raw)
    except ValidationError as exc:
        raise llm_client.LLMProviderError("The LLM returned an invalid guardrail batch") from exc
    verifications = {item.index: item for item in verified.verifications}
    if len(verifications) != len(verified.verifications) or set(verifications) != expected:
        raise llm_client.LLMProviderError("The LLM returned an incomplete guardrail batch")

    for rewrite in safe_rewrites:
        verification = verifications[rewrite.index]
        results[rewrite.index] = guard_rewrite(
            originals[rewrite.index],
            rewrite.rewritten_text,
            list(
                dict.fromkeys(
                    [
                        *rewrite.technology_terms,
                        *verification.technology_terms,
                        *known_technologies,
                    ]
                )
            ),
            allowed_skills,
            verification.unsupported_claims,
        )
    return results


async def rewrite_bullets(
    user_id: UUID,
    originals: list[str],
    required_skills: list[str],
    action_verbs: list[str],
    ats_keywords: list[str],
    allowed_skills: list[str],
    known_technologies: list[str] | None = None,
) -> list[tuple[str, list[dict[str, str]], bool]]:
    if not originals:
        return []
    prompt = batch_rewrite_prompt(
        originals, required_skills, action_verbs, ats_keywords, allowed_skills
    )
    messages = [{"role": "user", "content": prompt}]
    raw = await llm_client.get_completion(
        user_id,
        messages,
        response_format={"type": "json_object"},
        temperature=0,
    )
    expected = set(range(len(originals)))
    rewrites = _parse_rewrite_batch(raw, expected)
    results = await _guard_batch(
        user_id, originals, rewrites, allowed_skills, known_technologies or []
    )
    trivial_indices = {
        index
        for index, (rewritten, flags) in results.items()
        if not _is_blocked(flags) and is_trivial_rewrite(originals[index], rewritten)
    }
    if trivial_indices:
        retry_raw = await llm_client.get_completion(
            user_id,
            [
                *messages,
                {"role": "assistant", "content": raw},
                {"role": "user", "content": retry_trivial_prompt(trivial_indices)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        retried = _parse_rewrite_batch(retry_raw, expected)
        guarded_retries = await _guard_batch(
            user_id,
            originals,
            {index: retried[index] for index in trivial_indices},
            allowed_skills,
            known_technologies or [],
        )
        for index, retried_result in guarded_retries.items():
            if _is_blocked(retried_result[1]):
                continue
            current_result = results[index]
            if rewrite_change_ratio(originals[index], retried_result[0]) >= rewrite_change_ratio(
                originals[index], current_result[0]
            ):
                results[index] = retried_result

    return [
        (
            results[index][0],
            results[index][1],
            not _is_blocked(results[index][1])
            and is_trivial_rewrite(originals[index], results[index][0]),
        )
        for index in range(len(originals))
    ]


async def rewrite_bullet(
    user_id: UUID,
    original: str,
    requirements: list[str],
    action_verbs: list[str],
    allowed_skills: list[str],
    known_technologies: list[str] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    raw = await llm_client.get_completion(
        user_id,
        [
            {
                "role": "user",
                "content": rewrite_prompt(original, requirements, action_verbs, allowed_skills),
            }
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    try:
        proposed = RewriteOutput.model_validate_json(raw)
    except ValidationError as exc:
        raise llm_client.LLMProviderError("The LLM returned an invalid rewrite") from exc

    # Numbers are checked before another provider call: unsafe numeric output is never reconsidered.
    if number_tokens(original) != number_tokens(proposed.rewritten_text):
        return guard_rewrite(
            original, proposed.rewritten_text, proposed.technology_terms, allowed_skills
        )

    verification_raw = await llm_client.get_completion(
        user_id,
        [{"role": "user", "content": verification_prompt(original, proposed.rewritten_text)}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    try:
        verification = VerificationOutput.model_validate_json(verification_raw)
    except ValidationError as exc:
        raise llm_client.LLMProviderError("The LLM returned an invalid guardrail check") from exc
    return guard_rewrite(
        original,
        proposed.rewritten_text,
        list(
            dict.fromkeys(
                [
                    *proposed.technology_terms,
                    *verification.technology_terms,
                    *(known_technologies or []),
                ]
            )
        ),
        allowed_skills,
        verification.unsupported_claims,
    )
