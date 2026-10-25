# Abnahme gegen den unabhängigen Holdout

Stand: 2026-10-25 · Ergebnis: **bestanden**

## Ablauf

1. **Vor dem ersten Code-Commit** hat die orchestrierende Sitzung 60 handgeschriebene Szenarien
   (10 je Typ, inklusive schwieriger Fälle) und `eval.py` außerhalb des Repos angelegt.
   Ihre SHA-256-Hashes stehen in [`holdout.sha256`](../holdout.sha256), committet in `cab8e67`,
   also vor dem ersten Code-Commit `c2a8121`.
2. **Abschottung:** [`.claude/settings.json`](../.claude/settings.json) verbietet Lesen, Editieren und
   Shell-Zugriff auf den Holdout-Pfad. Die Builder- und Reviewer-Prompts erwähnen keine Szenarien.
   Die Sperre galt auch für die orchestrierende Sitzung. Ein Versuch, sie für den Eval-Lauf
   aufzuheben, wurde vom Permission-System blockiert.
3. **Durchführung:** Der Repo-Eigentümer hat `eval.py` selbst gegen den laufenden Docker-Stack
   (`make up`, Gateway auf `localhost:8000`) ausgeführt und den Holdout danach nach
   [`holdout/`](../holdout/) kopiert.
4. **Integrität:** `shasum -a 256 -c` gegen `holdout.sha256` ergibt `eval.py: OK` und
   `scenarios.jsonl: OK`. Szenarien und Metrik sind also seit dem Commit vor dem Bauen unverändert.
5. **Nachbesserung:** Es gab keine Verbesserungsrunde, weil die Schwellen im ersten Lauf erreicht wurden.

## Ergebnis ([`holdout/ergebnis.json`](../holdout/ergebnis.json))

| Metrik | Wert | Schwelle |
|---|---|---|
| Typ-Accuracy | **0,933** (56/60) | ≥ 0,85 |
| Macro-F1 | 0,932 | – |
| Feld-Trefferquote | **0,964** | ≥ 0,70 |
| `anliegen` nicht leer | 0,983 | – |
| Fehler/Timeouts | 0 | – |
| Median-Latenz | 1,48 s | < 30 s |

F1 pro Typ: termin 0,947 · rezept 0,952 · ueberweisung 0,952 · befund 0,947 · au 0,952 ·
sonstiges 0,842.

Trefferquote pro Feld: patient_name 0,95 · geburtsdatum 1,0 · wunschtermin 0,933 · medikament 1,0 ·
fachrichtung 0,967 · au_zeitraum 0,933.

## Fehlklassifikationen

| ID | Erwartet | Vorhergesagt | Mail (gekürzt) |
|---|---|---|---|
| h007 | termin | sonstiges | „Kann ich zur Blutabnahme vorbeikommen? Am 3.12. würde gut passen.“ |
| h036 | befund | rezept | „wie war der schilddrüsenwert?“ |
| h059 | sonstiges | ueberweisung | Bewerbung als Medizinische Fachangestellte |
| h060 | sonstiges | au | Frage zu einer IGeL-Rechnung |

Muster: Kurze, ungewöhnliche Formulierungen und `sonstiges`-Themen, die im Generator fehlen
(Bewerbung, Rechnung), landen bei einem der fachlichen Typen. Der Klassifikator kennt nur die
Formulierungsvielfalt des synthetischen Generators. Mehr Themen für `sonstiges` und ein
Konfidenz-Schwellwert mit Rückfall auf `sonstiges` wären die nächsten Schritte.

## Feldfehler

13 einzelne Feldfehler in 12 Szenarien, vor allem freie Zeitangaben (`wunschtermin` 4×,
`au_zeitraum` 4×). Dort extrahiert das Modell eine andere oder längere Spanne, als erwartet wird.
Dazu kommen Namen (`patient_name` 3×), etwa bei Mails, in denen Eltern für ein Kind schreiben.
`geburtsdatum` und `medikament` waren fehlerfrei.

## Einordnung

Die Val-Accuracy von 1,0 im Training ([docs/training.md](training.md)) zeigt nur, dass die
synthetischen Daten leicht sind. Aussagekräftig ist der Holdout, weil er anders geschrieben
wurde als der Generator und den bauenden Agenten nicht zugänglich war. Auch er ist synthetisch
und klein (60 Mails). Er belegt, dass die Pipeline grundsätzlich funktioniert, nicht dass sie
für echte Patientenpost taugt.
