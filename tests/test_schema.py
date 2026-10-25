import pytest
from pydantic import ValidationError

from mail_router.schema import MAIL_TYPES, TYPE_FIELDS, Fields, RouteRequest, to_text


def test_route_request_rejects_empty_mail():
    with pytest.raises(ValidationError):
        RouteRequest(sender="a@b.example", subject="  ", body="")


def test_fields_default_null():
    assert Fields().model_dump() == {
        k: None
        for k in ["patient_name", "geburtsdatum", "anliegen", "wunschtermin", "medikament", "fachrichtung", "au_zeitraum"]
    }


def test_to_text():
    assert to_text(RouteRequest(sender="x@y.example", subject="Hi", body="Text")) == "Betreff: Hi\n\nText"


def test_type_fields_cover_all_types():
    assert set(TYPE_FIELDS) == set(MAIL_TYPES)
