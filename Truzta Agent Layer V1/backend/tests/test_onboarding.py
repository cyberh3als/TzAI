import json
from pathlib import Path
from uuid import UUID

from app.control_catalog import load_catalog
from app.models import OnboardingSubmission
from app.onboarding import onboard_client


def test_onboarding_creates_valid_memory(tmp_path):
    root = Path(__file__).resolve().parents[2]
    catalog = load_catalog(root / "data" / "catalog" / "scf_controls.json")
    submission = OnboardingSubmission(
        organization_name="Acme",
        employee_range="10-49",
        countries=["Malaysia"],
        frameworks=["ISO 27001"],
        does_development=True,
        work_model="Fully on-site",
    )
    memory, controls = onboard_client(submission, catalog, tmp_path, client_id=UUID("00000000-0000-4000-8000-000000000001"))
    assert memory.organization.name == "Acme"
    assert memory.version == 1
    assert len(controls) > 0
    assert all("ISO 27001" in control["matched_frameworks"] for control in controls)

    controls_file = tmp_path / f"{memory.client_id}.controls.json"
    assert controls_file.exists()
    assert json.loads(controls_file.read_text(encoding="utf-8")) == controls


def test_onboarding_removes_development_controls_when_no_development(tmp_path):
    root = Path(__file__).resolve().parents[2]
    catalog = load_catalog(root / "data" / "catalog" / "scf_controls.json")
    base = dict(organization_name="Acme", employee_range="10-49", countries=["Malaysia"], frameworks=["PCI DSS 4.0.1"], work_model="Fully on-site")

    _, with_dev = onboard_client(
        OnboardingSubmission(**base, does_development=True),
        catalog, tmp_path, client_id=UUID("00000000-0000-4000-8000-000000000002"),
    )
    _, without_dev = onboard_client(
        OnboardingSubmission(**base, does_development=False),
        catalog, tmp_path, client_id=UUID("00000000-0000-4000-8000-000000000003"),
    )
    assert len(without_dev) < len(with_dev)
    assert not any("development" in control.get("tags", []) for control in without_dev)


def test_onboarding_normalizes_no_answer_phrases_to_null(tmp_path):
    root = Path(__file__).resolve().parents[2]
    catalog = load_catalog(root / "data" / "catalog" / "scf_controls.json")
    submission = OnboardingSubmission(
        organization_name="Acme",
        employee_range="10-49",
        industry="Not sure",
        countries=["Malaysia"],
        frameworks=["ISO 27001"],
        does_development=False,
        work_model="Fully remote",
        endpoint_protection="Not sure",
        password_manager="None",
        network_security="  ",
        identity_provider="Microsoft Entra ID",
    )
    memory, _ = onboard_client(submission, catalog, tmp_path, client_id=UUID("00000000-0000-4000-8000-000000000004"))
    assert memory.organization.industry is None
    assert memory.technology.endpoint_protection is None
    assert memory.technology.password_manager is None
    assert memory.technology.network_security is None
    assert memory.technology.identity_provider == "Microsoft Entra ID"


def test_onboarding_preserves_raw_technology_answers_as_facts(tmp_path):
    root = Path(__file__).resolve().parents[2]
    catalog = load_catalog(root / "data" / "catalog" / "scf_controls.json")
    submission = OnboardingSubmission(
        organization_name="Acme",
        employee_range="10-49",
        countries=["Malaysia"],
        frameworks=["ISO 27001"],
        does_development=False,
        work_model="Fully remote",
        identity_provider="in tune",
        password_manager="Not sure",
        network_security="  ",
    )
    memory, _ = onboard_client(submission, catalog, tmp_path, client_id=UUID("00000000-0000-4000-8000-000000000005"))
    facts_by_key = {fact.key: fact.value for fact in memory.facts}
    assert facts_by_key["identity_provider_raw_answer"] == "in tune"
    assert facts_by_key["password_manager_raw_answer"] == "Not sure"
    assert "network_security_raw_answer" not in facts_by_key
    assert all(fact.source == "onboarding" for fact in memory.facts)
