"""Questions asked in every gap assessment, regardless of the client's applicable controls.

Not LLM-generated — this is deterministic config. Edit the list directly to
change what's always asked; each item is prepended to the generated
questionnaire with is_universal=True and control_ids=[].

Starter set — review and adjust the wording before using with real clients.
"""

UNIVERSAL_QUESTIONS: list[dict] = [
    {
        "text": "Is there a designated person or role responsible for information security at your "
        "organisation (e.g. a security officer, IT manager, or outsourced provider)?",
    },
    {
        "text": "Have you experienced any security incidents, data breaches, or significant IT outages "
        "in the past 12 months? If so, briefly describe what happened and how it was handled.",
    },
    {
        "text": "Do employees receive any security awareness training, formal or informal, and how often?",
    },
    {
        "text": "Do you have a written, even informal, incident response plan for handling a security "
        "incident if one occurred?",
    },
    {
        "text": "How do you vet and manage third-party vendors or contractors who can access your "
        "systems or data?",
    },
    {
        "text": "Is there a written information security policy, even brief, that employees are aware of?",
    },
]
