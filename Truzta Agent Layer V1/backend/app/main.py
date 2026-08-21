from threading import Lock
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field

from .agents.gap_assessment import GapFinding, GapQuestion, evaluate_gaps, generate_questions
from .agents.gap_assessment import interview as interview_flow
from .agents.gap_assessment.interview import InterviewStep
from .agents.gap_assessment.scope import in_scope
from .config import CLIENT_MEMORY_DIR, SCF_PATH
from .control_catalog import list_frameworks, load_catalog, select_controls
from .memory import (
    list_memories, load_controls, load_gap_findings, load_gap_questions,
    load_gap_state, load_memory, save_controls, save_gap_answers,
    save_gap_findings, save_gap_questions, save_gap_state,
)
from .models import ClientMemory, ClientSummary, OnboardingResult, OnboardingSubmission
from .onboarding import onboard_client


class AnswerSubmission(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


def create_app() -> FastAPI:
    app = FastAPI(title="Truzta Agent Layer", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    catalog = load_catalog(SCF_PATH)
    # One questionnaire per client, generated exactly once. Without this, opening
    # two tabs at once had both find an empty cache and each run a full generation
    # — doubling the wait and the API cost, and producing two different question
    # sets where the later one silently overwrote the earlier.
    generation_locks: dict[UUID, Lock] = {}
    locks_guard = Lock()

    def _generation_lock(client_id: UUID) -> Lock:
        with locks_guard:
            return generation_locks.setdefault(client_id, Lock())

    @app.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/frameworks", tags=["onboarding"])
    def frameworks() -> list[dict]:
        return list_frameworks(catalog)

    @app.post("/api/clients", response_model=OnboardingResult, status_code=201, tags=["onboarding"])
    def create_client(submission: OnboardingSubmission) -> OnboardingResult:
        try:
            memory, controls = onboard_client(submission, catalog, CLIENT_MEMORY_DIR)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return OnboardingResult(client=memory, applicable_controls=controls)

    @app.get("/api/clients", response_model=list[ClientSummary], tags=["clients"])
    def clients() -> list[ClientSummary]:
        return list_memories(CLIENT_MEMORY_DIR)

    @app.get("/api/clients/{client_id}", response_model=ClientMemory, tags=["clients"])
    def get_client(client_id: UUID) -> ClientMemory:
        memory = load_memory(CLIENT_MEMORY_DIR, client_id)
        if memory is None:
            raise HTTPException(status_code=404, detail="Client not found")
        return memory

    @app.get("/api/clients/{client_id}/controls", tags=["clients"])
    def get_client_controls(client_id: UUID) -> list[dict]:
        memory = load_memory(CLIENT_MEMORY_DIR, client_id)
        if memory is None:
            raise HTTPException(status_code=404, detail="Client not found")
        cached = load_controls(CLIENT_MEMORY_DIR, client_id)
        if cached is not None:
            return cached
        controls = select_controls(
            catalog,
            frameworks=memory.compliance.target_frameworks,
            does_development=memory.applicability.does_development,
            work_model=memory.applicability.work_model,
        )
        return save_controls(CLIENT_MEMORY_DIR, client_id, controls)

    @app.get("/api/clients/{client_id}/gap-questions", response_model=list[GapQuestion], tags=["gap-assessment"])
    def get_gap_questions(client_id: UUID) -> list[GapQuestion]:
        memory = load_memory(CLIENT_MEMORY_DIR, client_id)
        if memory is None:
            raise HTTPException(status_code=404, detail="Client not found")
        cached = load_gap_questions(CLIENT_MEMORY_DIR, client_id)
        if cached is not None:
            return cached
        controls = load_controls(CLIENT_MEMORY_DIR, client_id) or select_controls(
            catalog,
            frameworks=memory.compliance.target_frameworks,
            does_development=memory.applicability.does_development,
            work_model=memory.applicability.work_model,
        )
        if not in_scope(controls):
            raise HTTPException(
                status_code=422,
                detail="Gap assessment is not available for PCI DSS-only clients.",
            )
        with _generation_lock(client_id):
            # Re-check inside the lock: a concurrent request may have finished
            # generating while this one was waiting.
            cached = load_gap_questions(CLIENT_MEMORY_DIR, client_id)
            if cached is not None:
                return cached
            questions = generate_questions(memory, controls)
            return save_gap_questions(CLIENT_MEMORY_DIR, client_id, questions)

    @app.get("/api/clients/{client_id}/gap-findings", response_model=list[GapFinding], tags=["gap-assessment"])
    def get_gap_findings(client_id: UUID) -> list[GapFinding]:
        if load_memory(CLIENT_MEMORY_DIR, client_id) is None:
            raise HTTPException(status_code=404, detail="Client not found")
        findings = load_gap_findings(CLIENT_MEMORY_DIR, client_id)
        if findings is None:
            # Findings only exist once an interview has been evaluated. Distinct
            # from "client not found" so the UI can offer the right next step.
            raise HTTPException(status_code=404, detail="No gap assessment has been run for this client yet.")
        return findings

    def _require(client_id: UUID):
        memory = load_memory(CLIENT_MEMORY_DIR, client_id)
        if memory is None:
            raise HTTPException(status_code=404, detail="Client not found")
        controls = load_controls(CLIENT_MEMORY_DIR, client_id) or select_controls(
            catalog,
            frameworks=memory.compliance.target_frameworks,
            does_development=memory.applicability.does_development,
            work_model=memory.applicability.work_model,
        )
        return memory, controls

    @app.get("/api/clients/{client_id}/gap-interview", response_model=InterviewStep, tags=["gap-assessment"])
    def get_interview(client_id: UUID) -> InterviewStep:
        _require(client_id)
        state = load_gap_state(CLIENT_MEMORY_DIR, client_id)
        if state is None:
            questions = load_gap_questions(CLIENT_MEMORY_DIR, client_id)
            if questions is None:
                # This endpoint never generates. The questionnaire has exactly one
                # producer (GET /gap-questions) so a client is interviewed against
                # one stable question set for its whole life.
                raise HTTPException(
                    status_code=409,
                    detail="The questionnaire has not been generated yet.",
                )
            state = save_gap_state(CLIENT_MEMORY_DIR, client_id, interview_flow.start(questions))
        return interview_flow.current_step(state)

    @app.post("/api/clients/{client_id}/gap-interview/answer", response_model=InterviewStep, tags=["gap-assessment"])
    def answer_interview(client_id: UUID, submission: AnswerSubmission) -> InterviewStep:
        memory, controls = _require(client_id)
        state = load_gap_state(CLIENT_MEMORY_DIR, client_id)
        if state is None:
            raise HTTPException(status_code=409, detail="Interview has not been started.")
        state = interview_flow.submit_answer(state, submission.text, memory, controls)
        save_gap_state(CLIENT_MEMORY_DIR, client_id, state)
        save_gap_answers(CLIENT_MEMORY_DIR, client_id, state.answers)
        return interview_flow.current_step(state)

    @app.post("/api/clients/{client_id}/gap-interview/skip", response_model=InterviewStep, tags=["gap-assessment"])
    def skip_question(client_id: UUID) -> InterviewStep:
        _require(client_id)
        state = load_gap_state(CLIENT_MEMORY_DIR, client_id)
        if state is None:
            raise HTTPException(status_code=409, detail="Interview has not been started.")
        state = interview_flow.skip(state)
        save_gap_state(CLIENT_MEMORY_DIR, client_id, state)
        save_gap_answers(CLIENT_MEMORY_DIR, client_id, state.answers)
        return interview_flow.current_step(state)

    @app.post("/api/clients/{client_id}/gap-interview/evaluate", response_model=list[GapFinding], tags=["gap-assessment"])
    def evaluate_interview(client_id: UUID) -> list[GapFinding]:
        memory, controls = _require(client_id)
        state = load_gap_state(CLIENT_MEMORY_DIR, client_id)
        if state is None or not state.answers:
            raise HTTPException(status_code=409, detail="No interview answers to evaluate.")
        # Every control-backed question is judged, whether or not the interview
        # reached it: unreached ones are assessed as "not in place" so ending early
        # still yields a complete report rather than a silently truncated one.
        answers = interview_flow.fill_unreached(state)
        judged = {answer.question_id for answer in answers}
        scored = [question for question in state.questions if question.question_id in judged]
        save_gap_answers(CLIENT_MEMORY_DIR, client_id, answers)
        findings = evaluate_gaps(memory, controls, scored, answers)
        save_gap_findings(CLIENT_MEMORY_DIR, client_id, findings)
        state.status = "complete"
        save_gap_state(CLIENT_MEMORY_DIR, client_id, state)
        return findings

    return app


app = create_app()
