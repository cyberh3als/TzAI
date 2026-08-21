from app.agents.gap_assessment import interview as flow
from app.agents.gap_assessment.models import GapQuestion
from app.agents.gap_assessment.priority import build_priority_map, priority_for
from app.agents.gap_assessment.scope import in_scope


def _questions():
    return [
        GapQuestion(question_id="q1", text="First?", order=0, control_ids=["GOV-01"]),
        GapQuestion(question_id="q2", text="Second?", order=1, control_ids=["GOV-02"]),
    ]


def _memory():
    from datetime import datetime, timezone
    from app.models import (
        ApplicabilityProfile, ClientMemory, ComplianceProfile,
        OrganizationProfile, TechnologyProfile,
    )
    now = datetime.now(timezone.utc)
    return ClientMemory(
        client_id="00000000-0000-4000-8000-000000000009",
        organization=OrganizationProfile(name="Acme", employee_range="10-49", countries=["Malaysia"]),
        compliance=ComplianceProfile(target_frameworks=["ISO 27001"]),
        applicability=ApplicabilityProfile(does_development=False, work_model="Fully on-site"),
        technology=TechnologyProfile(),
        created_at=now,
        updated_at=now,
    )


def test_followup_cap_holds_when_model_always_wants_more(monkeypatch):
    """The 2-follow-up bound is deterministic — a model that never stops asking
    must not be able to stretch one question past three answers."""
    monkeypatch.setattr(flow, "generate_followup", lambda *a, **k: "Tell me more?")

    state = flow.start(_questions())
    memory = _memory()

    for _ in range(3):
        state = flow.submit_answer(state, "vague answer", memory, [])

    # Initial answer + exactly MAX_FOLLOWUPS follow-up answers, then it moved on.
    transcript = next(a for a in state.answers if a.question_id == "q1")
    assert len(transcript.segments) == flow.MAX_FOLLOWUPS + 1
    assert state.current_question_id == "q2"
    assert state.current_followup_count == 0


def test_no_followup_advances_immediately(monkeypatch):
    monkeypatch.setattr(flow, "generate_followup", lambda *a, **k: None)
    state = flow.submit_answer(flow.start(_questions()), "detailed answer", _memory(), [])
    assert state.current_question_id == "q2"
    assert flow.current_step(state).kind == "question"


def test_followup_prompt_survives_reload(monkeypatch):
    """A pending follow-up must persist, or a reload re-asks the original question."""
    monkeypatch.setattr(flow, "generate_followup", lambda *a, **k: "Which systems?")
    state = flow.submit_answer(flow.start(_questions()), "yes", _memory(), [])

    restored = type(state).model_validate(state.model_dump(mode="json"))
    step = flow.current_step(restored)
    assert step.kind == "followup"
    assert step.prompt == "Which systems?"


def test_interview_completes_after_last_question(monkeypatch):
    monkeypatch.setattr(flow, "generate_followup", lambda *a, **k: None)
    state = flow.start(_questions())
    memory = _memory()
    state = flow.submit_answer(state, "a", memory, [])
    state = flow.submit_answer(state, "b", memory, [])

    step = flow.current_step(state)
    assert step.kind == "complete"
    assert state.status == "awaiting_evaluation"
    assert step.answered == step.total == 2


def test_pci_only_controls_are_out_of_scope():
    controls = [
        {"scf_id": "A", "matched_frameworks": ["PCI DSS 4.0.1"]},
        {"scf_id": "B", "matched_frameworks": ["PCI DSS 4.0.1", "ISO 27001"]},
        {"scf_id": "C", "matched_frameworks": []},
    ]
    assert [c["scf_id"] for c in in_scope(controls)] == ["B", "C"]


def test_priority_spreads_when_every_weight_is_identical():
    """SOC 2's catalog gate admits only weight==10, so weight alone cannot rank."""
    controls = [
        {"scf_id": f"C{i}", "weight": "10",
         "scf_core_profile_count": i % 6, "selected_framework_count": (i * 3) % 7}
        for i in range(40)
    ]
    tiers = set(build_priority_map(controls).values())
    assert tiers == {"high", "medium", "low"}


def test_finding_takes_highest_priority_of_its_controls():
    priority_map = {"A": "low", "B": "high"}
    assert priority_for(["A", "B"], priority_map) == "high"
    assert priority_for([], priority_map) == "medium"


def test_unreached_questions_become_negative_answers():
    """Ending an interview early must still produce a complete report: every
    control-backed question is judged, unreached ones as 'not in place'."""
    questions = _questions() + [
        GapQuestion(question_id="u1", text="Universal?", order=2, is_universal=True),
    ]
    state = flow.start(questions)
    flow._append_segment(state, "q1", "Yes, documented and reviewed annually.")

    filled = flow.fill_unreached(state)
    by_id = {answer.question_id: answer.segments for answer in filled}

    assert by_id["q1"] == ["Yes, documented and reviewed annually."]
    assert by_id["q2"] == [flow.UNREACHED_ANSWER]
    # Universal questions map to no control, so an unreached one yields no finding.
    assert "u1" not in by_id


def test_fill_unreached_preserves_answered_universal_questions():
    questions = _questions() + [
        GapQuestion(question_id="u1", text="Universal?", order=2, is_universal=True),
    ]
    state = flow.start(questions)
    flow._append_segment(state, "u1", "Yes, we do that.")

    by_id = {a.question_id: a.segments for a in flow.fill_unreached(state)}
    assert by_id["u1"] == ["Yes, we do that."]


def test_skip_during_followup_abandons_only_the_followup(monkeypatch):
    """Skipping a pending follow-up moves to the next question but keeps whatever
    the client already said — a partial answer is still worth assessing."""
    monkeypatch.setattr(flow, "generate_followup", lambda *a, **k: "Which systems?")
    state = flow.submit_answer(flow.start(_questions()), "Yes we do that.", _memory(), [])
    assert flow.current_step(state).kind == "followup"

    state = flow.skip(state)

    kept = next(a for a in state.answers if a.question_id == "q1")
    assert kept.segments == ["Yes we do that."]
    assert state.current_question_id == "q2"
    assert state.pending_prompt is None


def test_skip_untouched_question_records_it_as_skipped():
    state = flow.skip(flow.start(_questions()))
    assert next(a for a in state.answers if a.question_id == "q1").segments == ["[skipped]"]


def test_followup_skipped_entirely_when_no_controls_mapped(monkeypatch):
    """Universal questions map to no control, so the judge can only say 'sufficient'.
    Calling it anyway cost ~6s per answer for a foregone conclusion."""
    from app.agents.gap_assessment import followup

    called = []
    monkeypatch.setattr(followup, "get_client", lambda: called.append(1))

    result = followup.generate_followup(
        GapQuestion(question_id="u1", text="Universal?", order=0, is_universal=True),
        [], _memory(), ["Yes."],
    )
    assert result is None
    assert called == [], "no LLM call should be made when no controls are mapped"
