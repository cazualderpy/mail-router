# Training des Klassifikators

Automatisch erzeugt von `mail_router.classifier.train`.

- Basismodell: `distilbert/distilbert-base-german-cased`
- Trainingsdaten: 720 Beispiele, Validierung: 180 Beispiele (synthetisch)
- Epochen: 4, Batch-Größe: 16, Lernrate: 5e-05, max. Länge: 256, Seed: 42
- Gerät: mps
- Dauer: 67 s

## Validierung

- Accuracy: 1.0000
- Macro-F1: 1.0000

## Classification Report

```
               precision    recall  f1-score  support
termin             1.000     1.000     1.000       30
rezept             1.000     1.000     1.000       30
ueberweisung       1.000     1.000     1.000       30
befund             1.000     1.000     1.000       30
au                 1.000     1.000     1.000       30
sonstiges          1.000     1.000     1.000       30
accuracy                               1.000      180
macro avg                              1.000      180
```

## Konfusionsmatrix

| Wahr \ Vorhergesagt | termin | rezept | ueberweisung | befund | au | sonstiges |
|---|---|---|---|---|---|---|
| termin | 30 | 0 | 0 | 0 | 0 | 0 |
| rezept | 0 | 30 | 0 | 0 | 0 | 0 |
| ueberweisung | 0 | 0 | 30 | 0 | 0 | 0 |
| befund | 0 | 0 | 0 | 30 | 0 | 0 |
| au | 0 | 0 | 0 | 0 | 30 | 0 |
| sonstiges | 0 | 0 | 0 | 0 | 0 | 30 |
