import re
from collections.abc import Iterable

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "with",
}

ASCII_PART_PATTERN = re.compile(r"[a-zA-Z0-9]+")
CJK_CHAR_PATTERN = re.compile("[\u4e00-\u9fff]")


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def approximate_token_count(text: str) -> int:
    return len(text.split())


def split_sentences(text: str) -> list[str]:
    parts = re.split("(?<=[.!?\u3002\uff01\uff1f])\\s*", text)
    return [part.strip() for part in parts if part.strip()]


def extract_keywords(text: str) -> set[str]:
    return {
        token
        for token in tokenize_text(text)
        if not token.isascii() or token not in STOPWORDS
    }


def tokenize_text(text: str) -> list[str]:
    normalized_ascii = re.sub(r"[-_/]+", " ", text.lower())
    ascii_parts = ASCII_PART_PATTERN.findall(normalized_ascii)
    ascii_tokens = [
        token
        for token in ascii_parts
        if len(token) >= 2 or any(character.isdigit() for character in token)
    ]
    ascii_bigrams = [
        f"{left} {right}"
        for left, right in zip(ascii_parts, ascii_parts[1:], strict=False)
        if left and right and not (left in STOPWORDS and right in STOPWORDS)
    ]
    cjk_chars = CJK_CHAR_PATTERN.findall(text)
    cjk_bigrams = [
        "".join(cjk_chars[index : index + 2])
        for index in range(len(cjk_chars) - 1)
    ]

    ordered: list[str] = []
    seen: set[str] = set()
    for token in [*ascii_tokens, *ascii_bigrams, *cjk_bigrams, *cjk_chars]:
        if len(token.strip()) < 2 and token.isascii():
            continue
        if token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered


def build_preview(text: str, limit: int = 200) -> str:
    clean = normalize_whitespace(text)
    return clean if len(clean) <= limit else f"{clean[: limit - 3].rstrip()}..."


def unique_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
