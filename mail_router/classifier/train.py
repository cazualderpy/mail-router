import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from mail_router.schema import MAIL_TYPES, RouteRequest, to_text

BASE_MODEL = "distilbert/distilbert-base-german-cased"
LR = 5e-5
BATCH_SIZE = 16
MAX_LENGTH = 256
SEED = 42


def pick_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def load(path: Path) -> tuple[list[str], list[int]]:
    texts, labels = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        req = RouteRequest(sender=row["sender"], subject=row["subject"], body=row["body"])
        texts.append(to_text(req))
        labels.append(MAIL_TYPES.index(row["type"]))
    return texts, labels


def encode(tok, texts: list[str], device: str) -> dict:
    enc = tok(texts, truncation=True, max_length=MAX_LENGTH, padding=True, return_tensors="pt")
    return {k: v.to(device) for k, v in enc.items()}


def evaluate(model, tok, texts, labels, device) -> list[int]:
    model.eval()
    preds: list[int] = []
    with torch.no_grad():
        for i in range(0, len(texts), 32):
            logits = model(**encode(tok, texts[i : i + 32], device)).logits
            preds += logits.argmax(-1).tolist()
    return preds


def metrics(y_true: list[int], y_pred: list[int]) -> tuple[float, float, str, list[list[int]]]:
    n = len(MAIL_TYPES)
    cm = [[0] * n for _ in range(n)]
    for t, p in zip(y_true, y_pred):
        cm[t][p] += 1
    lines = [f"{'':14}{'precision':>10}{'recall':>10}{'f1-score':>10}{'support':>9}"]
    f1s = []
    for i, name in enumerate(MAIL_TYPES):
        tp = cm[i][i]
        pred_n = sum(cm[r][i] for r in range(n))
        sup = sum(cm[i])
        prec = tp / pred_n if pred_n else 0.0
        rec = tp / sup if sup else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        f1s.append(f1)
        lines.append(f"{name:14}{prec:10.3f}{rec:10.3f}{f1:10.3f}{sup:9d}")
    acc = sum(cm[i][i] for i in range(n)) / len(y_true)
    macro = sum(f1s) / n
    lines.append(f"{'accuracy':14}{'':20}{acc:10.3f}{len(y_true):9d}")
    lines.append(f"{'macro avg':14}{'':20}{macro:10.3f}{len(y_true):9d}")
    return acc, macro, "\n".join(lines), cm


def write_doc(path: Path, *, acc, f1, report, cm, epochs, device, duration, n_train, n_val) -> None:
    header = "| " + " | ".join(["Wahr \\ Vorhergesagt", *MAIL_TYPES]) + " |"
    sep = "|" + "---|" * (len(MAIL_TYPES) + 1)
    rows = [f"| {t} | " + " | ".join(str(x) for x in cm[i]) + " |" for i, t in enumerate(MAIL_TYPES)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# Training des Klassifikators",
                "",
                "Automatisch erzeugt von `mail_router.classifier.train`.",
                "",
                f"- Basismodell: `{BASE_MODEL}`",
                f"- Trainingsdaten: {n_train} Beispiele, Validierung: {n_val} Beispiele (synthetisch)",
                f"- Epochen: {epochs}, Batch-Größe: {BATCH_SIZE}, Lernrate: {LR}, max. Länge: {MAX_LENGTH}, Seed: {SEED}",
                f"- Gerät: {device}",
                f"- Dauer: {duration:.0f} s",
                "",
                "## Validierung",
                "",
                f"- Accuracy: {acc:.4f}",
                f"- Macro-F1: {f1:.4f}",
                "",
                "## Classification Report",
                "",
                "```",
                report,
                "```",
                "",
                "## Konfusionsmatrix",
                "",
                header,
                sep,
                *rows,
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--data", default="data")
    ap.add_argument("--doc", default="docs/training.md")
    args = ap.parse_args()

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    device = pick_device()
    start = time.time()

    tok = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=len(MAIL_TYPES),
        id2label=dict(enumerate(MAIL_TYPES)),
        label2id={t: i for i, t in enumerate(MAIL_TYPES)},
    ).to(device)

    tr_x, tr_y = load(Path(args.data) / "train.jsonl")
    va_x, va_y = load(Path(args.data) / "val.jsonl")
    opt = torch.optim.AdamW(model.parameters(), lr=LR)

    for epoch in range(args.epochs):
        model.train()
        order = list(range(len(tr_x)))
        random.shuffle(order)
        total = 0.0
        for i in range(0, len(order), BATCH_SIZE):
            idx = order[i : i + BATCH_SIZE]
            batch = encode(tok, [tr_x[j] for j in idx], device)
            labels = torch.tensor([tr_y[j] for j in idx], device=device)
            loss = model(**batch, labels=labels).loss
            loss.backward()
            opt.step()
            opt.zero_grad()
            total += loss.item() * len(idx)
        print(f"epoch {epoch + 1}/{args.epochs} loss={total / len(order):.4f}", flush=True)

    preds = evaluate(model, tok, va_x, va_y, device)
    acc, f1, report, cm = metrics(va_y, preds)
    print(f"val accuracy={acc:.4f} macro-F1={f1:.4f}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    model.to("cpu").save_pretrained(out)
    tok.save_pretrained(out)
    write_doc(
        Path(args.doc), acc=acc, f1=f1, report=report, cm=cm, epochs=args.epochs,
        device=device, duration=time.time() - start, n_train=len(tr_x), n_val=len(va_x),
    )


if __name__ == "__main__":
    main()
