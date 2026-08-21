"""Run a synthetic gap assessment end-to-end for one client and print a summary.

    python -m scripts.run_gap_test <client_id> [baseline|random]

Generates the questionnaire if it isn't cached, answers it synthetically, evaluates
it into findings, persists them, and prints a status/priority breakdown plus a
sample. Test tooling — not part of the API.
"""

import sys
from collections import Counter
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.agents.gap_assessment import evaluate_gaps, generate_questions  # noqa: E402
from app.agents.gap_assessment.synthetic_answers import build_answers  # noqa: E402
from app.config import CLIENT_MEMORY_DIR, SCF_PATH  # noqa: E402
from app.control_catalog import load_catalog, select_controls  # noqa: E402
from app.memory import (  # noqa: E402
    load_controls, load_gap_questions, load_memory,
    save_gap_answers, save_gap_findings, save_gap_questions,
)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    client_id = UUID(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "baseline"

    memory = load_memory(CLIENT_MEMORY_DIR, client_id)
    if memory is None:
        print(f"No client {client_id}")
        return 1

    controls = load_controls(CLIENT_MEMORY_DIR, client_id)
    if controls is None:
        catalog = load_catalog(SCF_PATH)
        controls = select_controls(
            catalog,
            frameworks=memory.compliance.target_frameworks,
            does_development=memory.applicability.does_development,
            work_model=memory.applicability.work_model,
        )

    questions = load_gap_questions(CLIENT_MEMORY_DIR, client_id)
    if questions is None:
        print(f"Generating questionnaire for {memory.organization.name}...")
        questions = save_gap_questions(
            CLIENT_MEMORY_DIR, client_id, generate_questions(memory, controls)
        )

    answers = build_answers(questions, mode=mode)
    save_gap_answers(CLIENT_MEMORY_DIR, client_id, answers)

    # Universal questions get no synthetic answer, so evaluating them would only
    # produce "[skipped]" findings that map to no control. Judge the control-backed
    # questions only.
    answered_ids = {answer.question_id for answer in answers}
    scored = [question for question in questions if question.question_id in answered_ids]

    print(f"{memory.organization.name}: {len(controls)} controls, {len(questions)} questions "
          f"({len(scored)} control-backed), {len(answers)} synthetic answers (mode={mode})")
    print("Evaluating...")

    findings = evaluate_gaps(memory, controls, scored, answers)
    save_gap_findings(CLIENT_MEMORY_DIR, client_id, findings)

    status = Counter(finding.status for finding in findings)
    priority = Counter(finding.priority for finding in findings)
    print(f"\nfindings: {len(findings)}")
    print(f"  status  : open={status['open']} closed={status['closed']}")
    print(f"  priority: high={priority['high']} medium={priority['medium']} low={priority['low']}")

    if mode == "baseline" and status["closed"]:
        print(f"\n  !! {status['closed']} finding(s) came back CLOSED on an all-negative "
              f"transcript — likely evaluator false negatives:")
        for finding in findings:
            if finding.status == "closed":
                print(f"     [{finding.finding_id}] {finding.question_text[:90]}")
                print(f"        -> {finding.summary}")

    print("\n--- sample findings ---")
    for finding in findings[:5]:
        print(f"\n[{finding.priority.upper()}/{finding.status}] {finding.control_ids}")
        print(f"  Q: {finding.question_text[:110]}")
        print(f"  summary   : {finding.summary}")
        print(f"  suggestion: {finding.suggestion}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
