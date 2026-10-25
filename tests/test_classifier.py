import pytest

from mail_router.classifier.predict import Classifier
from mail_router.classifier.train import pick_device
from mail_router.schema import MAIL_TYPES, RouteRequest


def test_pick_device_valid():
    assert pick_device() in {"mps", "cuda", "cpu"}


@pytest.mark.slow
def test_predict_shape_and_long_input():
    clf = Classifier("models/classifier")
    label, conf = clf.predict(
        RouteRequest(sender="a@b.example", subject="Rezept", body="Bitte Rezept für Ramipril. " * 400)
    )
    assert label in MAIL_TYPES and 0.0 <= conf <= 1.0


@pytest.mark.slow
def test_obvious_cases():
    clf = Classifier("models/classifier")
    req = RouteRequest(sender="a@b.example", subject="AU", body="Ich brauche eine Krankschreibung bis Freitag.")
    assert clf.predict(req)[0] == "au"
