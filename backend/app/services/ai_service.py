from decimal import Decimal

import httpx

from app.config import GROQ_API_KEY, GROQ_API_URL, GROQ_MODEL
from app.database.models import Patient

SYSTEM_PROMPT = """You provide a brief, cautious explanation of user-entered laboratory
measurements for general education, not diagnosis or treatment. The values have no
units or laboratory reference ranges unless explicitly supplied; do not infer or
invent units, normal ranges, results, or diagnoses. Explain that interpretation is
limited without units, reference ranges, clinical history, and clinician review.
Mention a value as potentially noteworthy only when the provided context is
sufficient. Keep the response under 400 words, use plain language, and predict based on the information provided
what disease the patient may have. Emphasize that the user should seek professional medical advice and
discussing results with a qualified healthcare professional. Never claim a disease
has been diagnosed. Do not request or repeat identifying information."""


class AIServiceError(Exception):
    """A safe, user-facing description of an AI-provider failure."""


class AIConfigurationError(AIServiceError):
    """The AI provider is not configured for this application."""


def generate_health_remarks(patient: Patient) -> str:
    if not GROQ_API_KEY:
        raise AIConfigurationError("AI remarks are not configured. Add GROQ_API_KEY to .env.")

    measurements = {
        "date_of_birth": patient.date_of_birth.isoformat(),
        "glucose": _serialize_measurement(patient.glucose),
        "haemoglobin": _serialize_measurement(patient.haemoglobin),
        "cholesterol": _serialize_measurement(patient.cholesterol),
    }

    try:
        response = httpx.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": GROQ_MODEL,
                "temperature": 0.2,
                "max_tokens": 500,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "Provide cautious educational context for these "
                            f"measurements. Values have no provided units: {measurements}"
                        ),
                    },
                ],
            },
            timeout=12.0,
        )
    except httpx.TimeoutException as error:
        raise AIServiceError("The AI service timed out. You can retry remarks generation.") from error
    except httpx.RequestError as error:
        raise AIServiceError("The AI service could not be reached. You can retry later.") from error

    if response.status_code in (401, 403):
        raise AIServiceError("The AI service rejected its credentials. Check GROQ_API_KEY.")
    if response.status_code == 429:
        raise AIServiceError("The AI service rate limit was reached. Retry in a moment.")
    if response.is_error:
        raise AIServiceError("The AI service is temporarily unavailable. You can retry later.")

    try:
        payload = response.json()
    except ValueError as error:
        raise AIServiceError("The AI service returned an invalid response. You can retry.") from error

    try:
        remarks = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise AIServiceError("The AI service returned an unexpected response. You can retry.") from error

    if not isinstance(remarks, str) or not remarks.strip():
        raise AIServiceError("The AI service returned empty remarks. You can retry.")
    return remarks.strip()[:2000]


def _serialize_measurement(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None
