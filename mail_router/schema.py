from typing import Literal

from pydantic import BaseModel, model_validator

MAIL_TYPES: tuple[str, ...] = ("termin", "rezept", "ueberweisung", "befund", "au", "sonstiges")

TYPE_FIELDS: dict[str, str | None] = {
    "termin": "wunschtermin",
    "rezept": "medikament",
    "ueberweisung": "fachrichtung",
    "au": "au_zeitraum",
    "befund": None,
    "sonstiges": None,
}


class RouteRequest(BaseModel):
    sender: str
    subject: str
    body: str

    @model_validator(mode="after")
    def _not_empty(self) -> "RouteRequest":
        if not self.subject.strip() and not self.body.strip():
            raise ValueError("subject und body dürfen nicht beide leer sein")
        return self


class Fields(BaseModel):
    patient_name: str | None = None
    geburtsdatum: str | None = None
    anliegen: str | None = None
    wunschtermin: str | None = None
    medikament: str | None = None
    fachrichtung: str | None = None
    au_zeitraum: str | None = None


class RouteResponse(BaseModel):
    type: Literal["termin", "rezept", "ueberweisung", "befund", "au", "sonstiges"]
    confidence: float
    fields: Fields


def to_text(req: RouteRequest) -> str:
    return f"Betreff: {req.subject}\n\n{req.body}"
