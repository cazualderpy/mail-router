"""Unabhängige Abnahme des Mail-Routers gegen den Holdout.

Spricht nur den API-Vertrag (POST /route) an. Nur Standardbibliothek.
Aufruf: python eval.py [--url http://localhost:8000] [--out ergebnis.json]
"""
import argparse
import json
import pathlib
import re
import time
import urllib.request
from collections import Counter

TYPES = ["termin", "rezept", "ueberweisung", "befund", "au", "sonstiges"]
SCORED = ["patient_name", "geburtsdatum", "wunschtermin", "medikament", "fachrichtung", "au_zeitraum"]
TIMEOUT_S = 120
THRESH_TYPE, THRESH_FIELDS = 0.85, 0.70


def norm(s):
    s = str(s).lower().replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s).strip()
    return s.strip(" .,;:!?\"'()")


def field_hit(name, expected, got):
    if expected is None or got is None or (isinstance(got, str) and not got.strip()):
        return expected is None and (got is None or not str(got).strip())
    if name == "geburtsdatum":
        return str(got).strip() == expected
    e, g = norm(expected), norm(got)
    return bool(e) and bool(g) and (e in g or g in e)


def call(url, s):
    payload = json.dumps({k: s[k] for k in ("sender", "subject", "body")}).encode()
    req = urllib.request.Request(url + "/route", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--out", default=str(pathlib.Path(__file__).with_name("ergebnis.json")))
    a = ap.parse_args()
    scen = [json.loads(l) for l in pathlib.Path(__file__).with_name("scenarios.jsonl").read_text().splitlines() if l.strip()]

    rows, confusion = [], Counter()
    for s in scen:
        exp, t0 = s["expected"], time.time()
        try:
            res, err = call(a.url, s), None
        except Exception as ex:  # Timeout/Fehler zählt als Fehlschlag
            res, err = {}, repr(ex)
        pred = res.get("type")
        fields = res.get("fields") or {}
        hits = {f: field_hit(f, exp[f], fields.get(f)) if err is None else False for f in SCORED}
        anliegen_ok = err is None and bool(str(fields.get("anliegen") or "").strip())
        confusion[(exp["type"], pred)] += 1
        rows.append({"id": s["id"], "expected_type": exp["type"], "pred_type": pred,
                     "field_hits": hits, "anliegen_ok": anliegen_ok,
                     "latency_s": round(time.time() - t0, 2), "error": err})
        print(f"{s['id']} {exp['type']:>12} -> {str(pred):>12}  Felder {sum(hits.values())}/{len(SCORED)}")

    n = len(rows)
    acc = sum(r["expected_type"] == r["pred_type"] for r in rows) / n
    f1s = {}
    for t in TYPES:
        tp = confusion[(t, t)]
        fp = sum(v for (e, p), v in confusion.items() if p == t and e != t)
        fn = sum(v for (e, p), v in confusion.items() if e == t and p != t)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s[t] = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    field_rate = sum(sum(r["field_hits"].values()) for r in rows) / (n * len(SCORED))
    per_field = {f: sum(r["field_hits"][f] for r in rows) / n for f in SCORED}
    summary = {
        "n": n, "type_accuracy": round(acc, 3), "macro_f1": round(sum(f1s.values()) / len(TYPES), 3),
        "f1_per_type": {k: round(v, 3) for k, v in f1s.items()},
        "field_hit_rate": round(field_rate, 3), "field_hit_rate_per_field": {k: round(v, 3) for k, v in per_field.items()},
        "anliegen_nonempty_rate": round(sum(r["anliegen_ok"] for r in rows) / n, 3),
        "errors": sum(r["error"] is not None for r in rows),
        "median_latency_s": sorted(r["latency_s"] for r in rows)[n // 2],
        "passed": acc >= THRESH_TYPE and field_rate >= THRESH_FIELDS,
        "thresholds": {"type_accuracy": THRESH_TYPE, "field_hit_rate": THRESH_FIELDS},
    }
    pathlib.Path(a.out).write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
