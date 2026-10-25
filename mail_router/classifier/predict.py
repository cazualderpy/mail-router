import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from mail_router.schema import RouteRequest, to_text

MAX_LENGTH = 256


class Classifier:
    """CPU-Inferenz; Gewichte werden explizit auf CPU gemappt (auch bei MPS-Training)."""

    def __init__(self, path: str):
        self.tokenizer = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForSequenceClassification.from_pretrained(path)
        self.model.to("cpu").eval()

    def predict(self, req: RouteRequest) -> tuple[str, float]:
        enc = self.tokenizer(to_text(req), truncation=True, max_length=MAX_LENGTH, return_tensors="pt")
        with torch.no_grad():
            logits = self.model(**enc).logits[0]
        probs = torch.softmax(logits, dim=-1)
        idx = int(probs.argmax())
        return self.model.config.id2label[idx], float(probs[idx])
