"""Loads the editable, versioned gap-assessment prompts from backend/app/prompts/gap_assessment/.

Prompt text here only shapes model behaviour; it never encodes deterministic
rules (coverage, the follow-up cap, schema shape) — those stay in Python, per
backend/app/prompts/README.md.
"""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts" / "gap_assessment"

QUESTION_GENERATION_PROMPT = (_PROMPTS_DIR / "question_generation.md").read_text(encoding="utf-8")
FOLLOWUP_JUDGMENT_PROMPT = (_PROMPTS_DIR / "followup_judgment.md").read_text(encoding="utf-8")
GAP_EVALUATION_PROMPT = (_PROMPTS_DIR / "gap_evaluation.md").read_text(encoding="utf-8")
