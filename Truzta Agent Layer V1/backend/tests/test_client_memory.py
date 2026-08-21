from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.memory import VersionConflictError, load_controls, load_memory, save_controls, save_memory
from app.models import ApplicabilityProfile, ClientMemory, ComplianceProfile, OrganizationProfile


def memory(version: int = 1) -> ClientMemory:
    now = datetime.now(timezone.utc)
    return ClientMemory(
        client_id=UUID("00000000-0000-4000-8000-000000000001"),
        version=version,
        organization=OrganizationProfile(name="Acme", employee_range="10-49", countries=["Malaysia"]),
        compliance=ComplianceProfile(target_frameworks=["ISO 27001"]),
        applicability=ApplicabilityProfile(does_development=True, work_model="Fully on-site"),
        created_at=now,
        updated_at=now,
    )


def test_yaml_round_trip(tmp_path):
    saved = save_memory(tmp_path, memory())
    assert load_memory(tmp_path, saved.client_id) == saved
    assert "organization:" in (tmp_path / f"{saved.client_id}.yaml").read_text(encoding="utf-8")


def test_rejects_stale_version(tmp_path):
    save_memory(tmp_path, memory())
    with pytest.raises(VersionConflictError):
        save_memory(tmp_path, memory(version=2), expected_version=999)


def test_controls_json_round_trip(tmp_path):
    client_id = UUID("00000000-0000-4000-8000-000000000001")
    controls = [{"scf_id": "GOV-01", "matched_frameworks": ["ISO 27001"]}]
    assert load_controls(tmp_path, client_id) is None
    save_controls(tmp_path, client_id, controls)
    assert load_controls(tmp_path, client_id) == controls
    assert (tmp_path / f"{client_id}.controls.json").exists()
