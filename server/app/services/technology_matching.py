import re
from difflib import SequenceMatcher
from typing import Literal

WORD = re.compile(r"[a-z0-9+#]+")
RAW_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#.-]*")
GENERIC_REQUIREMENT_WORDS = {
    "and",
    "backend",
    "collaboration",
    "communication",
    "development",
    "engineering",
    "experience",
    "leadership",
    "knowledge",
    "management",
    "problem",
    "projects",
    "required",
    "systems",
    "tools",
    "using",
    "with",
}


def normalized_text(value: str) -> str:
    return " ".join(WORD.findall(value.casefold()))


def contains_literal_term(source_text: str, term: str) -> bool:
    source = normalized_text(source_text)
    normalized_term = normalized_text(term)
    return bool(normalized_term) and f" {normalized_term} " in f" {source} "


def infer_legacy_named_technologies(requirement_text: str) -> list[str]:
    """Best-effort fallback for rows created before terms were persisted."""
    words = RAW_WORD.findall(requirement_text)
    if len(words) == 1:
        return [] if normalized_text(words[0]) in GENERIC_REQUIREMENT_WORDS else words
    return list(
        dict.fromkeys(
            word
            for index, word in enumerate(words)
            if normalized_text(word) not in GENERIC_REQUIREMENT_WORDS
            and (
                word.isupper()
                or any(character.isupper() for character in word[1:])
                or any(character.isdigit() or character in "+#." for character in word)
                or (index > 0 and word[0].isupper())
            )
        )
    )


def _term_variants(term: str) -> set[str]:
    words = normalized_text(term).split()
    if not words:
        return set()
    compact = "".join(words)
    variants = {compact}
    if len(words) > 1:
        variants.add("".join(word[0] for word in words))
    for word in words:
        if len(word) >= 4:
            variants.add(f"{word[0]}{len(word) - 2}{word[-1]}")
    return variants


def _candidate_phrases(candidate_text: str) -> set[str]:
    words = normalized_text(candidate_text).split()
    return {
        "".join(words[start : start + size])
        for size in range(1, min(4, len(words)) + 1)
        for start in range(len(words) - size + 1)
    }


def _term_score(term: str, candidate_text: str) -> float:
    variants = _term_variants(term)
    candidates = _candidate_phrases(candidate_text)
    if variants & candidates:
        return 1.0
    return max(
        (
            SequenceMatcher(None, variant, candidate).ratio()
            for variant in variants
            for candidate in candidates
            if len(variant) >= 4 and len(candidate) >= 4
        ),
        default=0.0,
    )


def technology_keyword_score(
    named_technologies: list[str] | tuple[str, ...],
    candidate_text: str,
    match_mode: Literal["any", "all"],
    threshold: float = 0.85,
) -> tuple[float, list[str]]:
    scores = [(term, _term_score(term, candidate_text)) for term in named_technologies]
    if not scores:
        return 0.0, []
    evidence = [term for term, score in scores if score >= threshold]
    aggregate = min if match_mode == "all" else max
    return aggregate(score for _, score in scores), evidence
