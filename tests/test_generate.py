import re
from collections import Counter

from mail_router.data.generate import generate
from mail_router.schema import MAIL_TYPES, TYPE_FIELDS


def test_deterministic():
    assert generate(5, seed=1) == generate(5, seed=1)


def test_balanced_types():
    ex = generate(20, seed=0)
    assert Counter(e.type for e in ex) == {t: 20 for t in MAIL_TYPES}


def test_only_example_domains():
    for e in generate(30, seed=0):
        assert re.fullmatch(r"[^@\s]+@[\w.-]+\.example", e.sender)
        for dom in re.findall(r"@([\w.-]+)", e.body):
            assert dom.endswith(".example")


def test_spans_are_verbatim():
    for e in generate(30, seed=0):
        for k in ("patient_name", "wunschtermin", "medikament", "fachrichtung", "au_zeitraum"):
            v = getattr(e.fields, k)
            if v:
                assert v.lower() in e.body.lower()


def test_only_type_specific_field_set():
    for e in generate(30, seed=0):
        for t, f in TYPE_FIELDS.items():
            if f and t != e.type:
                assert getattr(e.fields, f) is None


def test_variety():
    bodies = [e.body for e in generate(100, seed=0)]
    assert len(set(bodies)) / len(bodies) > 0.95


def test_own_field_anliegen_and_iso_birthdate():
    for e in generate(30, seed=3):
        f = TYPE_FIELDS[e.type]
        if f:
            assert getattr(e.fields, f)
        assert e.fields.anliegen
        if e.fields.geburtsdatum:
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", e.fields.geburtsdatum)


def test_split_is_stratified_and_disjoint():
    from mail_router.data.generate import split

    train, val = split(generate(50, seed=0), 0.2, seed=42)
    assert Counter(e.type for e in val) == {t: 10 for t in MAIL_TYPES}
    assert len(train) == 240


def test_jsonl_roundtrip(tmp_path):
    import json

    from mail_router.data.generate import _write
    from mail_router.schema import Fields

    ex = generate(2, seed=0)
    _write(tmp_path / "x.jsonl", ex)
    rows = [json.loads(line) for line in (tmp_path / "x.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["type"] for r in rows] == [e.type for e in ex]
    assert set(rows[0]) == {"sender", "subject", "body", "type", "fields"}
    assert Fields(**rows[0]["fields"]) == ex[0].fields


KEYWORDS = {
    "termin": r"termin|appointment",
    "rezept": r"rezept|prescription",
    "ueberweisung": r"überweisung|ueberweisung|referral",
    "befund": r"befund|ergebnis|results",
    "au": r"\bau\b|krank|sick",
}


def test_subject_does_not_leak_label():
    ex = generate(150, seed=42)
    generic = {"", "Anfrage", "Frage", "Hallo", "Kurze Frage", "Nachricht", "Question", "Hello"}
    for t, pat in KEYWORDS.items():
        subs = [e.subject for e in ex if e.type == t]
        share = sum(bool(re.search(pat, s, re.I)) for s in subs) / len(subs)
        assert share <= 0.4, (t, share)
    for t in MAIL_TYPES:
        subs = {e.subject.removeprefix("Re: ") for e in ex if e.type == t}
        assert subs & generic, t


def test_sonstiges_subject_fits_body():
    for e in generate(150, seed=42):
        if e.type == "sonstiges" and e.subject == "Öffnungszeiten":
            assert "zeit" in e.body.lower()


def test_anliegen_is_german():
    english = [" the ", "Requests", "Asks", "Reports", " for ", "whether"]
    for e in generate(150, seed=42):
        assert not any(w in e.fields.anliegen for w in english), e.fields.anliegen
