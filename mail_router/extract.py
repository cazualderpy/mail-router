"""Feldextraktion per LangChain-Kette (Ollama) mit deterministischer Nachbearbeitung."""
import datetime
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_ollama import ChatOllama

from mail_router.schema import TYPE_FIELDS, Fields, RouteRequest, to_text

_MONTHS = {
    "januar": 1, "january": 1, "februar": 2, "february": 2, "märz": 3, "maerz": 3, "march": 3,
    "april": 4, "mai": 5, "may": 5, "juni": 6, "june": 6, "juli": 7, "july": 7,
    "august": 8, "september": 9, "oktober": 10, "october": 10, "november": 11,
    "dezember": 12, "december": 12,
}
_VERBATIM = ("patient_name", "wunschtermin", "medikament", "fachrichtung", "au_zeitraum")


def _iso(y: int, m: int, d: int) -> str | None:
    try:
        return datetime.date(y, m, d).isoformat()
    except ValueError:
        return None


def parse_birthdate(s: str | None) -> str | None:
    if not s:
        return None
    if m := re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", s):
        return _iso(int(m[1]), int(m[2]), int(m[3]))
    if m := re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", s):
        return _iso(int(m[3]), int(m[2]), int(m[1]))
    if m := re.search(r"(\d{1,2})\.?\s+([A-Za-zäöüÄÖÜ]+)\s+(\d{4})", s):
        mon = _MONTHS.get(m[2].lower())
        if mon:
            return _iso(int(m[3]), mon, int(m[1]))
    return None


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().casefold()


def normalize_fields(raw: Fields, mail_type: str, text: str) -> Fields:
    own = TYPE_FIELDS.get(mail_type)
    haystack = _norm(text)
    data: dict[str, str | None] = {}
    for name in Fields.model_fields:
        val = getattr(raw, name)
        val = val.strip() if isinstance(val, str) else val
        if not val:
            val = None
        if name in _VERBATIM and name not in ("patient_name", own):
            val = None
        elif name in _VERBATIM and val is not None and _norm(val) not in haystack:
            val = None
        elif name == "geburtsdatum":
            val = parse_birthdate(val)
        data[name] = val
    return Fields(**data)


_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "Du extrahierst Felder aus Patientenmails einer Arztpraxis. Mailtyp: {mail_type}.\n"
     "Regeln:\n"
     "- patient_name, wunschtermin, medikament, fachrichtung, au_zeitraum: wörtlich aus der Mail "
     "übernehmen (exakter Textausschnitt), nichts erfinden.\n"
     "- Feld nicht in der Mail: null.\n"
     "- geburtsdatum: wie in der Mail, sonst null.\n"
     "- anliegen: ein kurzer deutscher Satz.\n"
     "- Nur Felder füllen, die zum Typ passen (termin: wunschtermin, rezept: medikament, "
     "ueberweisung: fachrichtung, au: au_zeitraum).\n\n"
     "Beispiel 1 (Typ termin):\n"
     "Betreff: Frage\n\nMoin,\n\nich melde mich, da wir möchten einen Termin für eine Untersuchung "
     "buchen, idealerweise Montag nachmittags.\n\n(*15.11.2003)\n\nBeste Grüße\nKarl Heinz Henschel\n"
     'Ergebnis: {{"patient_name": "Karl Heinz Henschel", "geburtsdatum": "15.11.2003", '
     '"anliegen": "Terminanfrage, gewünscht ist Montag nachmittags.", '
     '"wunschtermin": "Montag nachmittags", "medikament": null, "fachrichtung": null, '
     '"au_zeitraum": null}}\n\n'
     "Beispiel 2 (Typ au):\n"
     "Betreff: Krankschreibung\n\nLiebes Praxisteam,\n\nIch war krank und benötige die AU für meinen "
     "Arbeitgeber, Zeitraum: diese ganze Woche.\n\nGruß\nKornelia Steinberg\n"
     'Ergebnis: {{"patient_name": "Kornelia Steinberg", "geburtsdatum": null, '
     '"anliegen": "Meldet sich krank, AU gewünscht: diese ganze Woche.", "wunschtermin": null, '
     '"medikament": null, "fachrichtung": null, "au_zeitraum": "diese ganze Woche"}}\n\n'
     "Beispiel 3 (Typ befund):\n"
     "Betreff: Kurze Anfrage\n\nGuten Morgen,\n\nBitte um Kopie des Röntgenbefundes für meinen "
     "Facharzt. Geburtsdatum: *25.11.1994\n\nMit besten Grüßen\nHeinz-Josef Mohaupt\n"
     'Ergebnis: {{"patient_name": "Heinz-Josef Mohaupt", "geburtsdatum": "25.11.1994", '
     '"anliegen": "Bittet um eine Kopie des Röntgenbefunds.", "wunschtermin": null, '
     '"medikament": null, "fachrichtung": null, "au_zeitraum": null}}'),
    ("human", "{mail_text}"),
])


def build_llm(base_url: str, model: str = "qwen2.5:3b") -> Runnable:
    chat = ChatOllama(model=model, base_url=base_url, temperature=0, num_predict=256)
    return chat.with_structured_output(Fields)


def extract(req: RouteRequest, mail_type: str, llm: Runnable) -> Fields:
    text = to_text(req)
    raw = (_PROMPT | llm).invoke({"mail_type": mail_type, "mail_text": text})
    if not isinstance(raw, Fields):
        raw = Fields.model_validate(raw) if raw else Fields()
    return normalize_fields(raw, mail_type, text)
