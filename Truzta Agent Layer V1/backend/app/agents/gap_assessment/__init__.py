"""Gap assessment agent: turns a client's applicable controls into an interview,
runs that interview with a bounded number of follow-ups, and evaluates the
transcript into gap findings.

Public entry points, re-exported for callers (e.g. main.py):
    generate_questions  — build the questionnaire from client memory + controls
    evaluate_gaps       — turn an interview transcript into GapFindings
    generate_followup   — decide whether one more follow-up is needed (not yet built)

Everything else in this package (prompts, model config, business-size lookup,
priority scoring, coverage validation) is an implementation detail of those calls.
"""

from .evaluation import evaluate_gaps
from .models import GapAnswer, GapAssessmentState, GapFinding, GapQuestion
from .questions import generate_questions

__all__ = [
    "generate_questions",
    "evaluate_gaps",
    "GapQuestion",
    "GapAnswer",
    "GapFinding",
    "GapAssessmentState",
]
