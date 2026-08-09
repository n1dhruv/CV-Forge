import re

WORD = re.compile(r"[a-z0-9+#]+")


def normalized_text(value: str) -> str:
    return " ".join(WORD.findall(value.casefold()))


def contains_literal_term(source_text: str, term: str) -> bool:
    source = normalized_text(source_text)
    normalized_term = normalized_text(term)
    return bool(normalized_term) and f" {normalized_term} " in f" {source} "
