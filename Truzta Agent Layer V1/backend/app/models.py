"""Pydantic contracts shared by the API, workflows, and future agents."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


EmployeeRange = Literal["1-9", "10-49", "50-249", "250-999", "1000+"]
WorkModel = Literal["Fully on-site", "Fully remote", "Hybrid"]


class OnboardingSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Compliance target
    frameworks: list[str] = Field(min_length=1)

    # Organization
    organization_name: str = Field(min_length=1, max_length=200)
    employee_range: EmployeeRange
    industry: str | None = Field(default=None, max_length=200)
    countries: list[str] = Field(min_length=1)
    departments: list[str] = Field(default_factory=list)

    # Applicability gates
    sensitive_data: list[str] = Field(default_factory=list)
    does_development: bool
    work_model: WorkModel

    # Technology & infrastructure profile (memory only, not used for filtering)
    identity_provider: str | None = Field(default=None, max_length=500)
    device_management: str | None = Field(default=None, max_length=500)
    endpoint_protection: str | None = Field(default=None, max_length=500)
    password_manager: str | None = Field(default=None, max_length=500)
    cloud_infrastructure: str | None = Field(default=None, max_length=1000)
    network_security: str | None = Field(default=None, max_length=500)
    vulnerability_management: str | None = Field(default=None, max_length=500)
    patch_management: str | None = Field(default=None, max_length=500)
    backup_recovery: str | None = Field(default=None, max_length=1000)
    email_collaboration: str | None = Field(default=None, max_length=500)
    logging_siem: str | None = Field(default=None, max_length=500)


class OrganizationProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    employee_range: EmployeeRange
    industry: str | None = None
    countries: list[str] = Field(min_length=1)
    departments: list[str] = Field(default_factory=list)


class ComplianceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_frameworks: list[str] = Field(min_length=1)


class ApplicabilityProfile(BaseModel):
    """Answers that gate which SCF controls apply to this client."""

    model_config = ConfigDict(extra="forbid")
    sensitive_data: list[str] = Field(default_factory=list)
    does_development: bool
    work_model: WorkModel


class TechnologyProfile(BaseModel):
    """Free-text infrastructure context. Informational only—does not filter controls."""

    model_config = ConfigDict(extra="forbid")
    identity_provider: str | None = None
    device_management: str | None = None
    endpoint_protection: str | None = None
    password_manager: str | None = None
    cloud_infrastructure: str | None = None
    network_security: str | None = None
    vulnerability_management: str | None = None
    patch_management: str | None = None
    backup_recovery: str | None = None
    email_collaboration: str | None = None
    logging_siem: str | None = None


class MemoryFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=2000)
    source: Literal["onboarding", "user", "gap_assessment", "risk_assessment", "policy_review", "manual_edit"]
    confidence: Literal["unverified", "user_asserted", "evidence_supported", "verified"] = "unverified"
    observed_at: datetime


class ClientMemory(BaseModel):
    """Durable client facts—not chat history or model reasoning."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.1"] = "1.1"
    client_id: UUID
    version: int = Field(default=1, ge=1)
    organization: OrganizationProfile
    compliance: ComplianceProfile
    applicability: ApplicabilityProfile
    technology: TechnologyProfile = Field(default_factory=TechnologyProfile)
    facts: list[MemoryFact] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)


class ClientSummary(BaseModel):
    client_id: UUID
    organization_name: str
    frameworks: list[str]
    updated_at: datetime


class OnboardingResult(BaseModel):
    """Onboarding agent output: updated client memory plus the controls it implies."""

    client: ClientMemory
    applicable_controls: list[dict]
