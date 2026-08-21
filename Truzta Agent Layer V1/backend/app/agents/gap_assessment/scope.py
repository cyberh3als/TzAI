"""Which of a client's applicable controls the gap assessment will actually cover.

PCI DSS is excluded by product decision. Its catalog gate is `weight >= 9`, which
admits 220 controls — more than twice any other framework — and at the current
question-to-control ratio that projects to roughly 250 interview questions. That is
unworkable as a conversation, so PCI DSS is out of scope for gap assessment until
the question-mix compression in docs/gap-question-design.md lands.

Exclusion is per-control, not per-client: a control is dropped only if PCI DSS is
its *sole* reason for applying. A client running ISO 27001 alongside PCI DSS still
gets a full gap assessment of their ISO obligations; only the PCI-exclusive controls
fall away. A PCI-DSS-only client is left with no in-scope controls, which callers
should treat as "gap assessment unavailable" rather than as an empty questionnaire.
"""

EXCLUDED_FRAMEWORKS = frozenset({"PCI DSS 4.0.1"})


def in_scope(controls: list[dict]) -> list[dict]:
    """Drop controls that apply only because of an excluded framework."""
    kept = []
    for control in controls:
        matched = set(control.get("matched_frameworks") or [])
        # No framework attribution at all (SCF CORE profile only) — keep it.
        if not matched or matched - EXCLUDED_FRAMEWORKS:
            kept.append(control)
    return kept
