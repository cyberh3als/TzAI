"""Convert onboarding answers into validated client memory and applicable controls."""

from pathlib import Path
from uuid import UUID, uuid4

from .agents.technology_normalizer import TECHNOLOGY_FIELDS, normalize_technology_profile
from .control_catalog import select_controls, validate_frameworks
from .memory import save_controls, save_memory
from .models import (
    ApplicabilityProfile,
    ClientMemory,
    ComplianceProfile,
    MemoryFact,
    OnboardingSubmission,
    OrganizationProfile,
    TechnologyProfile,
)
from .text_normalize import normalize_text


def onboard_client(
    submission: OnboardingSubmission,
    catalog: dict,
    memory_directory: Path,
    client_id: UUID | None = None,
) -> tuple[ClientMemory, list[dict]]:
    validate_frameworks(catalog, submission.frameworks)
    now = ClientMemory.now()

    raw_technology = {field: getattr(submission, field) for field in TECHNOLOGY_FIELDS}
    normalized_technology = normalize_technology_profile(raw_technology)
    facts = [
        MemoryFact(
            key=f"{field}_raw_answer",
            value=raw_technology[field].strip(),
            source="onboarding",
            confidence="user_asserted",
            observed_at=now,
        )
        for field in TECHNOLOGY_FIELDS
        if raw_technology[field] and raw_technology[field].strip()
    ]

    memory = ClientMemory(
        client_id=client_id or uuid4(),
        organization=OrganizationProfile(
            name=submission.organization_name,
            employee_range=submission.employee_range,
            industry=normalize_text(submission.industry),
            countries=clean_list(submission.countries),
            departments=clean_list(submission.departments),
        ),
        compliance=ComplianceProfile(
            target_frameworks=clean_list(submission.frameworks),
        ),
        applicability=ApplicabilityProfile(
            sensitive_data=clean_list(submission.sensitive_data),
            does_development=submission.does_development,
            work_model=submission.work_model,
        ),
        technology=TechnologyProfile(**normalized_technology),
        facts=facts,
        created_at=now,
        updated_at=now,
    )
    saved = save_memory(memory_directory, memory)
    controls = select_controls(
        catalog,
        frameworks=saved.compliance.target_frameworks,
        does_development=saved.applicability.does_development,
        work_model=saved.applicability.work_model,
    )
    save_controls(memory_directory, saved.client_id, controls)
    return saved, controls


def clean_list(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))
