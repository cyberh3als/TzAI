"""Maps a client's employee_range to the matching SCF business-size consideration field.

Verified directly against data/catalog/scf_controls.json: every control's
business_size_considerations dict has exactly these five keys, one per
OnboardingSubmission.employee_range bucket.
"""

from ...models import EmployeeRange

EMPLOYEE_RANGE_TO_CONSIDERATION_KEY: dict[str, str] = {
    "1-9": "micro_small_business_considerations",
    "10-49": "small_business_considerations",
    "50-249": "medium_business_considerations",
    "250-999": "large_business_considerations",
    "1000+": "enterprise_business_considerations",
}


def get_consideration(control: dict, employee_range: EmployeeRange) -> str:
    """Return the business-size-appropriate consideration text for a control."""
    key = EMPLOYEE_RANGE_TO_CONSIDERATION_KEY[employee_range]
    return control.get("business_size_considerations", {}).get(key, "")
