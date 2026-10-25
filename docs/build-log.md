# Build-Log

Bereinigte Fassung des Ledgers, das der Orchestrator während des Baus geführt hat (Spec, Plan mit 7 Tasks,
Branch `feat/router`). Builder und Reviewer liefen auf Claude Sonnet (Vorgabe des Eigentümers), der Orchestrator
auf Claude Opus. Interne Pfade, Agenten-IDs und Arbeitsverzeichnisse sind entfernt; Commit-Bereiche stehen
in `git log`.

## Pre-flight-Scan

Vor dem ersten Task prüfte der Orchestrator, ob die Schnittstellen zwischen den Tasks zusammenpassen.

| Paar / Task | Erzeugt vs. verbraucht | Ergebnis |
|---|---|---|
| T1 nach T2..T5 | `MAIL_TYPES`, `TYPE_FIELDS`, `Fields`, `RouteRequest`, `to_text` | konsistent |
| T2 nach T3 | `data/{train,val}.jsonl` mit `{sender, subject, body, type, fields}` | konsistent |
| T2 nach T4 | Few-Shots aus `data/train.jsonl` | konsistent |
| T3 nach T5 | `Classifier.predict(req)` liefert `(str, float)` | konsistent |
| T4 nach T5 | `extract(req, type, llm)` vs. `extract_fields(req, type)` | konsistent per Closure im Modul `app` |
| T5 nach T6 | `mail_router.api:app`, Umgebungsvariablen | konsistent |
| T1 intern | 422-Test in T5 stützt sich auf den Validator aus T1 | konsistent |
| T2 intern | `Fields` enthält `anliegen`, Tests schränken es nicht ein | siehe Entscheidung 1 |
| T3 intern | `addopts` ohne `slow` vs. Lauf mit `-m slow` | späteres `-m` überschreibt, ok |
| T5 intern | Warm-up vs. `TestClient(create_app)` | siehe Entscheidung 2 |
| T6 intern | Egress-Check auf ollama-Image ohne `curl` | Implementierer wählt das Werkzeug, ok |
| T7 intern | Links auf noch nicht existierendes `docs/abnahme.md` | vom Plan ausgenommen, ok |

## Entscheidungen des Orchestrators

Jede mit den Kosten, falls sie falsch war.

1. **`anliegen` als kurzer deutscher Satz.** Der Generator setzt es so, es wird für Few-Shots gebraucht.
   Falls falsch: nur die Few-Shot-Qualität leidet.
2. **Warm-up nur beim modulweiten `app`, nicht in `create_app`.** Sonst bräuchten API-Tests Ollama.
   Falls falsch: kein Warm-up in Tests, unkritisch.
3. **Fix-Runden 4 und 5 sowie Final-Review ebenfalls auf Sonnet** statt auf einem stärkeren Modell
   (ausdrückliche Vorgabe des Eigentümers). Falls falsch: hartnäckige Findings werden eher geparkt.
4. **Holdout-Sperre betrifft auch den Orchestrator.** Nach Abschluss aller Builder-Tasks wollte er sie für
   den Eval-Lauf aufheben und das in `docs/abnahme.md` dokumentieren. Falls falsch: Die Abnahme-Reihenfolge
   bleibt im Repo transparent. (Die Aufhebung wurde vom Permission-System blockiert, der Eigentümer führte
   den Lauf selbst aus, siehe Abnahme.)
5. **Ledger wird bereinigt (keine absoluten Pfade) und als dieses Build-Log ins Repo kopiert.** Der Prozess
   soll sichtbar sein. Falls falsch: eine Datei löschen.
6. **Holdout-Abnahme läuft vor dem Final-Review**, damit `docs/abnahme.md`, `holdout/` und die
   README-Anpassungen mitgeprüft werden. Falls falsch: Der Final-Review sieht einen Stand mit Ergebnis statt
   Platzhalter, kein Nachteil.

## Ergebnis je Task

Jeder Task: frischer Builder, danach unabhängiger Review. Fix-Runden sind auf höchstens 5 begrenzt;
keine wurde ausgeschöpft.

**Task 1 (Schemas und Typen).** Review: Spec erfüllt, aber die Typreihenfolge (`au` vor `befund`) wich von
der Spec ab; Fix-Runde 1 (1 Finding behoben). Danach sauber. Zurückgestellt: `confidence` ohne Bound 0..1,
kein Test für leeren Betreff mit Body, `TYPE_FIELDS`-Reihenfolge weicht von `MAIL_TYPES` ab (kosmetisch).

**Task 2 (Datengenerator).** Der Builder meldete die Beobachtung, dass Mails über Dritte ("ich"-Kerntexte)
dieselben Texte nutzen. Review: 3 Important (Betreff verriet das Label, `sonstiges`-Betreff passte nicht zum
Body, englisches `anliegen`); Fix-Runde 1 (3 behoben). Danach sauber. Zurückgestellt: doppelte
Geburtsdatum-Labels, Grammatik-Artefakte ('16.11..', 'zur Kardiologen'), Bereich 'von 28.11. bis 28.11.',
`anliegen` mit leerem Slot ('Folgerezept ().'), schwacher `test_variety`, DOB-Span ungetestet,
dünne Tests für `sonstiges`-Betreff und deutsches `anliegen`. Folge: Task 4 muss saubere Few-Shots wählen.

**Task 3 (Klassifikator).** Builder: Validation-Accuracy 1,0, weil die synthetischen Daten leicht sind.
Außerdem brach `uv run pytest`, weil `.pth`-Dateien in `.venv` unter macOS das Hidden-Flag tragen und
Python sie überspringt (vom Orchestrator bestätigt). Review: Spec erfüllt; Fix-Runde 1 behob den Import-Fehler.
Zurückgestellt: ungenutztes `labels`-Argument in `evaluate()`, `load()` bricht bei Leerzeilen, `metrics` und
`write_doc` ungetestet, Fix-Report nur mit Kurzergebnis statt Rohausgabe, `addopts`-Formatierung.
Hinweis: Val 1,0 darf nicht als Qualitätsbeleg dargestellt werden (steht so in den Einschränkungen).

**Task 4 (Feld-Extraktion).** Review: Important, `parse_birthdate` akzeptierte 31.02.; Fix-Runde 1 (1 behoben).
Zurückgestellt: `extract()` fängt Parse-Exceptions nicht (Task 5 fängt alles ab), Containment-Prüfung lässt sehr
kurze Halluzinationen zu, Few-Shots zeigen kein `medikament`/`fachrichtung`, Jahresgrenze fehlt ('0815' als
Jahr möglich), Datums-Regex ohne Wortgrenzen.

**Task 5 (FastAPI-App).** Builder-Hinweis: `create_app` hat einen optionalen `lifespan`-Parameter über den
Auftrag hinaus. Review: Spec erfüllt, keine Critical/Important. Zurückgestellt: Warm-up blockiert den Start bis
zum Timeout (Background-Task wäre besser), kein Test für leichten Import, `index.html` wird bei jedem Request gelesen.

**Task 6 (Docker Compose).** Builder-Messung: `/route` ca. 4,1 s bei einem einzelnen Aufruf, `EGRESS BLOCKED`,
Image 1,21 GB; zusätzlich ein api-Healthcheck. Review: Spec erfüllt; Isolation per `network inspect` live
bestätigt. Zurückgestellt: der ollama-Egress-Zweig wertet Exit-Code 1 als blockiert (strengerer Match auf
'unreachable|resolution' wäre besser), `uv export 2>/dev/null` verschluckt Fehler.

**Task 7 (README und Doku).** Review: Important, die README überzeichnete die Isolation, weil der Gateway im
`edge`-Netz hängt; Fix-Runde 1 (1 behoben). Zurückgestellt: Setup-Dauer geschätzt, Vergangenheitsform der
Abnahme vor der Abnahme, doppeltes 'Ergebnis:', 'keine Mail verlässt die Maschine' ist für den Gateway nicht
per `egress-check` belegt, ein Zeilenumbruch.

## Abnahme

Alle Builder waren beendet. Die Aufhebung der Holdout-Sperre wurde nicht durchgesetzt; der Repo-Eigentümer
führte den Holdout selbst gegen den laufenden Stack aus. Ergebnis: bestanden (Typ-Accuracy 0,933,
Feld-Trefferquote 0,964), Hashes OK. Details in [abnahme.md](abnahme.md).

## Final-Review der gesamten Branch

Verdikt: mit Auflagen. Behoben in der anschließenden Fix-Runde:

- Important: Gateway-Port war an alle Host-Interfaces gebunden (jetzt nur `127.0.0.1`).
- Important: widersprüchliche Latenzangaben (4 s vs. 1,5 s), jetzt auf den Holdout-Median vereinheitlicht.
- Important: `docs/build-log.md` fehlte (diese Datei).
- Minor: README überzeichnete die Holdout-Sperre, Spec-Status, Gateway im Diagramm nur in `edge`,
  Hinweis zu den `slow`-Tests fehlte.

Bewusst geparkt (jeweils mit Kosten, falls die Entscheidung falsch ist):

- Nicht gepinnte Images und Container als root: Demo-Scope, Zukunftsarbeit. Falls falsch: Rebuild evtl. nicht
  reproduzierbar.
- `geburtsdatum` wird nicht gegen den Mailtext geprüft: Holdout erreicht 1,0 für das Feld, Lücke ist dokumentiert.
  Falls falsch: ein halluziniertes Datum ist möglich.
- Warm-up ohne Timeout; `log.exception` kann Mailfragmente lokal loggen: Logs verlassen den Host nicht.
  Falls falsch: lokale Logs enthalten Mailtext.
- Die Spec enthält einen GitHub-Handle samt noreply-Adresse: gewollt, das Repo ist öffentlich unter diesem Handle.
  Falls falsch: eine Zeile entfernen.
