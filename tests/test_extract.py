import pytest
from langchain_core.runnables import RunnableLambda

from mail_router.extract import extract, normalize_fields, parse_birthdate
from mail_router.schema import Fields, RouteRequest


@pytest.mark.parametrize("raw,iso", [("02.11.1990","1990-11-02"),("*07.06.1968","1968-06-07"),("12 March 1979","1979-03-12"),("12. März 1979","1979-03-12"),("1985-09-30","1985-09-30"),("geb. am 3.3.1938","1938-03-03"),("unbekannt",None),(None,None)])
def test_parse_birthdate(raw, iso):
    assert parse_birthdate(raw) == iso


def test_normalize_drops_hallucinations_and_foreign_fields():
    text = "Bitte Rezept für Ramipril 5 mg. Gerda Pohl"
    raw = Fields(patient_name="Gerda Pohl", medikament="Ramipril 5 mg", wunschtermin="morgen", fachrichtung="Kardiologie", anliegen="Folgerezept")
    out = normalize_fields(raw, "rezept", text)
    assert out.medikament == "Ramipril 5 mg" and out.patient_name == "Gerda Pohl"
    assert out.wunschtermin is None and out.fachrichtung is None and out.anliegen == "Folgerezept"


def test_normalize_drops_value_not_in_text():
    out = normalize_fields(Fields(medikament="Aspirin"), "rezept", "Rezept für Ramipril bitte")
    assert out.medikament is None


def test_normalize_empty_strings_and_whitespace_case():
    out = normalize_fields(Fields(patient_name="  ", anliegen="", medikament="ramipril  5 MG"), "rezept", "Ramipril\n5 mg")
    assert out.patient_name is None and out.anliegen is None and out.medikament == "ramipril  5 MG"


def test_extract_uses_llm_and_normalizes():
    fake = RunnableLambda(lambda _: Fields(patient_name="Tim Sauer", medikament="L-Thyroxin", geburtsdatum="01.02.1990"))
    req = RouteRequest(sender="t@s.example", subject="rezept", body="mein L-Thyroxin ist alle. Tim Sauer, 01.02.1990")
    out = extract(req, "rezept", fake)
    assert out.geburtsdatum == "1990-02-01" and out.medikament == "L-Thyroxin"


def test_build_llm_constructs_offline():
    from mail_router.extract import build_llm
    assert build_llm("http://localhost:11434") is not None
