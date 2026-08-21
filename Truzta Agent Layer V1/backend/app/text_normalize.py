"""Deterministic 'no answer' detection for free-text onboarding answers.

Fixed phrase match, not a model call — see docs/onboarding-questions.md for
what this covers. Used directly for fields with no canonicalization need
(industry), and as the fallback path when the technology-profile LLM call
fails (see agents/technology_normalizer.py).
"""

NO_ANSWER_PHRASES = {
    "none", "n/a", "na", "not sure", "unsure", "not applicable",
    "i don't know", "i dont know", "idk", "dont know", "don't know",
    "no idea", "nothing", "not decided", "tbd", "no", "not yet",
}


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped.lower() in NO_ANSWER_PHRASES:
        return None
    return stripped
