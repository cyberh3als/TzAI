"""Read and write human-editable client-memory YAML files."""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

import yaml

from .agents.gap_assessment.models import GapAnswer, GapAssessmentState, GapFinding, GapQuestion
from .models import ClientMemory, ClientSummary


class VersionConflictError(Exception):
    pass


def load_memory(directory: Path, client_id: UUID) -> ClientMemory | None:
    path = directory / f"{client_id}.yaml"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as stream:
        return ClientMemory.model_validate(yaml.safe_load(stream))


def list_memories(directory: Path) -> list[ClientSummary]:
    """Return small records for the client chooser, newest first."""
    if not directory.exists():
        return []
    clients = []
    for path in directory.glob("*.yaml"):
        if path.name == "example.yaml":
            continue
        with path.open(encoding="utf-8") as stream:
            memory = ClientMemory.model_validate(yaml.safe_load(stream))
        clients.append(ClientSummary(
            client_id=memory.client_id,
            organization_name=memory.organization.name,
            frameworks=memory.compliance.target_frameworks,
            updated_at=memory.updated_at,
        ))
    return sorted(clients, key=lambda client: client.updated_at, reverse=True)


def save_memory(
    directory: Path,
    memory: ClientMemory,
    expected_version: int | None = None,
) -> ClientMemory:
    directory.mkdir(parents=True, exist_ok=True)
    current = load_memory(directory, memory.client_id)
    if expected_version is not None and (current is None or current.version != expected_version):
        actual = current.version if current else None
        raise VersionConflictError(f"Expected version {expected_version}, found {actual}")

    target = directory / f"{memory.client_id}.yaml"
    with NamedTemporaryFile("w", encoding="utf-8", dir=directory, delete=False, suffix=".tmp") as stream:
        yaml.safe_dump(memory.model_dump(mode="json"), stream, sort_keys=False, allow_unicode=True)
        temporary = Path(stream.name)
    temporary.replace(target)
    return memory


def load_controls(directory: Path, client_id: UUID) -> list[dict] | None:
    path = directory / f"{client_id}.controls.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def save_controls(directory: Path, client_id: UUID, controls: list[dict]) -> list[dict]:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{client_id}.controls.json"
    with NamedTemporaryFile("w", encoding="utf-8", dir=directory, delete=False, suffix=".tmp") as stream:
        json.dump(controls, stream, indent=2, ensure_ascii=False)
        temporary = Path(stream.name)
    temporary.replace(target)
    return controls


def load_gap_questions(directory: Path, client_id: UUID) -> list[GapQuestion] | None:
    path = directory / f"{client_id}.gap-questions.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as stream:
        return [GapQuestion.model_validate(item) for item in json.load(stream)]


def save_gap_questions(directory: Path, client_id: UUID, questions: list[GapQuestion]) -> list[GapQuestion]:
    _write_json(directory, f"{client_id}.gap-questions.json", [question.model_dump(mode="json") for question in questions])
    return questions


def load_gap_answers(directory: Path, client_id: UUID) -> list[GapAnswer] | None:
    path = directory / f"{client_id}.gap-answers.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as stream:
        return [GapAnswer.model_validate(item) for item in json.load(stream)]


def save_gap_answers(directory: Path, client_id: UUID, answers: list[GapAnswer]) -> list[GapAnswer]:
    _write_json(directory, f"{client_id}.gap-answers.json", [answer.model_dump(mode="json") for answer in answers])
    return answers


def load_gap_findings(directory: Path, client_id: UUID) -> list[GapFinding] | None:
    path = directory / f"{client_id}.gap-findings.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as stream:
        return [GapFinding.model_validate(item) for item in json.load(stream)]


def save_gap_findings(directory: Path, client_id: UUID, findings: list[GapFinding]) -> list[GapFinding]:
    _write_json(directory, f"{client_id}.gap-findings.json", [finding.model_dump(mode="json") for finding in findings])
    return findings


def load_gap_state(directory: Path, client_id: UUID) -> GapAssessmentState | None:
    path = directory / f"{client_id}.gap-state.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as stream:
        return GapAssessmentState.model_validate(json.load(stream))


def save_gap_state(directory: Path, client_id: UUID, state: GapAssessmentState) -> GapAssessmentState:
    _write_json(directory, f"{client_id}.gap-state.json", state.model_dump(mode="json"))
    return state


def _write_json(directory: Path, filename: str, payload: object) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / filename
    with NamedTemporaryFile("w", encoding="utf-8", dir=directory, delete=False, suffix=".tmp") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False)
        temporary = Path(stream.name)
    temporary.replace(target)
