# Design: Lokaler MVZ-Posteingangs-Router

Stand: 2026-10-25 · Status: freigegeben und umgesetzt

## 1. Intent und das Warum

Ein Medizinisches Versorgungszentrum (MVZ) bekommt täglich Patientenmails: Terminwünsche,
Rezeptanfragen, Überweisungen, Befundnachfragen, Krankmeldungen. Der Router ordnet jede Mail
einem Typ zu und zieht die relevanten Felder heraus, **vollständig lokal**. Keine Mail und kein
Feld verlässt die Maschine. Das ist das Datenschutz-Argument.

Das Repo ist ein Demo-Projekt. Im Mittelpunkt steht, **wie mit KI-Agenten gebaut wurde**.
Leser sollen das Repo ohne Begleitung verstehen können. Deshalb ist der Bauprozess das eigentliche Produkt. Er muss im Repo nachvollziehbar
sein. Die Software muss funktionieren, aber nicht glänzen.

## 2. Ziele, Nicht-Ziele, Anti-Ziele

**Ziele**
- Wer das Repo öffnet, versteht in etwa 5 Minuten, wie es gebaut wurde: Spec, Plan,
  Task-für-Task-Umsetzung mit Review und eine unabhängige Abnahme gegen einen Holdout.
- `docker compose up` startet einen lauffähigen Router (API + Ollama), dessen Container keinen
  Internetzugang haben.
- Typ-Klassifikation über einen feinabgestimmten kleinen PyTorch-Transformer.
- Feldextraktion über eine LangChain-Kette mit lokalem Ollama-Modell und strukturierter Ausgabe.
- Das Holdout-Ergebnis steht ehrlich im Repo, auch wenn es unter der Schwelle liegt.

**Nicht-Ziele**
- Keine echte Mail-Anbindung (IMAP/SMTP), keine Benutzerverwaltung, keine Persistenz.
- Kein poliertes Frontend. Eine minimale HTML-Seite zum Ausprobieren genügt.
- Kein Hyperparameter-Tuning über das Nötige hinaus.

**Anti-Ziele** (Ergebnis wäre gescheitert, selbst wenn es technisch läuft)
- Echte oder realistisch personenbezogene Daten. Nur synthetische Daten, Domains nur `*.example`.
- Ein Cloud- oder Netzaufruf zur Laufzeit.
- Bauende Agenten haben den Holdout gelesen. Dann ist die Abnahme wertlos.
- Der echte Name des Repo-Eigentümers oder dessen lokaler Home-Pfad taucht im Repo auf
  (Dateien, Commits, Logs). Gilt auch für absolute Pfade wie `/Users/<name>/…`.
- Ein vom Eigentümer gesperrter Begriff taucht im Repo auf. Die Liste liegt außerhalb des Repos,
  der Orchestrator prüft vor dem Push.
- Ein Repo, das nach „KI hat alles in einem Rutsch generiert“ aussieht.

## 3. Constraints

- **Zeit:** etwa 5 Stunden ab Freigabe. Danach Push auf `https://github.com/cazualderpy/mail-router.git`
  (öffentlich). Die Umsetzung läuft möglichst autonom mit Subagents.
- **Hardware:** MacBook M5 Pro, 24 GB. Docker Desktop hat keinen GPU-Zugriff, die VM steht derzeit
  auf 4 GB RAM. Vorgabe: Docker-RAM auf 8 GB erhöhen. Das macht der Eigentümer in Docker Desktop.
- **Git:** lokaler Autor `cazualderpy <90839438+cazualderpy@users.noreply.github.com>`.
  Jeder Commit endet mit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Gitignore:** `CLAUDE.md` und `.claude/` sind global ignoriert. Die Repo-`.gitignore` gibt sie
  mit `!CLAUDE.md` und `!.claude/` wieder frei. Beide gehören ins Repo, weil sie den Agenten-Prozess zeigen.
- **Netz:** Internet nur in einer einmaligen Setup-Phase (Modell-Downloads: HuggingFace-Basismodell,
  `ollama pull`). Zur Laufzeit hängen die Compose-Services in einem Netz mit `internal: true`.

## 4. Entschiedene Teile des Wie

**Architektur (Compose)**
- `ollama`: offizielles Image, Modell `qwen2.5:3b`, Modelle in einem benannten Volume. CPU-Betrieb.
- `api`: Python/FastAPI. Lädt den Klassifikator aus `models/classifier/` und ruft über LangChain
  (`langchain-ollama`, `ChatOllama` mit strukturierter Ausgabe auf ein Pydantic-Schema) den
  `ollama`-Service auf. Liefert unter `/` eine minimale HTML-Testseite.
- Netz: Beide Services hängen nur in einem `internal: true`-Netz. Für den Host-Zugriff auf die API
  braucht es ein Port-Mapping. Wie das trotz `internal` funktioniert, löst der Builder (siehe 5).
- Setup-Schritt für die Downloads, getrennt vom Laufzeitbetrieb, z. B. `make setup`.
- Verifizierbar: Ein `curl` nach außen aus dem `api`-Container schlägt fehl (als Test/Skript im Repo).

**API-Vertrag** (fix, weil der Holdout dagegen testet)

```
POST /route
Request:  {"sender": str, "subject": str, "body": str}
Response: {
  "type": "termin" | "rezept" | "ueberweisung" | "befund" | "au" | "sonstiges",
  "confidence": float,          # 0..1, Softmax des Klassifikators
  "fields": {
    "patient_name": str | null,
    "geburtsdatum": str | null,   # ISO YYYY-MM-DD
    "anliegen": str | null,       # ein Satz, Deutsch
    "wunschtermin": str | null,   # nur termin; freier Text wie in der Mail
    "medikament": str | null,     # nur rezept
    "fachrichtung": str | null,   # nur ueberweisung
    "au_zeitraum": str | null     # nur au; freier Text
  }
}
GET /health -> {"status": "ok"}
```

Typen: `termin` (Terminwunsch, -verschiebung, -absage), `rezept` (Folgerezept),
`ueberweisung` (Überweisung zum Facharzt), `befund` (Nachfrage zu Labor-/Befundergebnissen),
`au` (Arbeitsunfähigkeitsbescheinigung), `sonstiges` (alles andere, z. B. Öffnungszeiten, Spam).
Nicht zutreffende Felder sind `null`.

**Klassifikator**
- Basismodell: `distilbert-base-german-cased`, feinabgestimmt als Sequence Classification (6 Klassen).
- Training auf dem Host mit PyTorch auf MPS (`uv run …`). Das Artefakt landet in `models/classifier/`
  und wird in den `api`-Container gemountet oder kopiert. Inferenz im Container auf der CPU.
- Trainingsdaten: generiert von einem deterministischen Generator (Seed) im Repo, Deutsch,
  Faker `de_DE`, nur `*.example`-Domains. Vorgabe: Die Formulierungen variieren stark (Tippfehler,
  Umgangssprache, gemischte Anliegen), damit das Modell keine Templates auswendig lernt.
- Validierungsmetriken des Trainings stehen im Repo (z. B. `docs/training.md`).
- Gewichte werden **nicht** committet (≈250 MB, kein LFS). `make setup` lädt die Modelle herunter
  und trainiert. Das Gerät wird automatisch gewählt (MPS, sonst CUDA, sonst CPU), damit es auch auf
  Fremdrechnern läuft. Die README nennt die ungefähre Dauer.
- Latenz: `num_predict` begrenzen, kurzer Prompt, Warm-up-Aufruf beim API-Start.
  Ziel < 30 s pro Mail auf CPU.

**Holdout (unabhängige Abnahme)**
- Wird **vor** dem Plan und der Umsetzung vom Orchestrator (der Hauptsitzung) angelegt, außerhalb
  des Repos unter `~/.mail-router-holdout/`: etwa 60 handgeschriebene Szenarien (≈10 je Typ, inklusive
  schwieriger Fälle) als JSONL mit erwartetem Typ und erwarteten Feldern, dazu `eval.py`.
- `eval.py` spricht nur den API-Vertrag über HTTP an. Es misst Typ-Accuracy, Macro-F1 und
  Feld-Trefferquote. Timeout pro Request: 120 s. Ein Timeout zählt als Fehler bei Typ und Feldern.
- **Feld-Trefferquote** (Builder-relevant, auch wenn `eval.py` verborgen bleibt): Bewertet werden
  alle Felder außer `anliegen`, und zwar pro Szenario für alle 6 Felder.
  - Treffer, wenn Erwartung und Ausgabe beide `null` sind.
  - `geburtsdatum`: exakter Treffer im ISO-Format.
  - `patient_name`, `medikament`, `fachrichtung`: normalisierter Vergleich (Kleinschreibung,
    Whitespace zusammengefasst, Satzzeichen am Rand entfernt). Treffer, wenn der erwartete String
    in der Ausgabe enthalten ist oder umgekehrt.
  - `wunschtermin`, `au_zeitraum`: dasselbe Enthaltensein-Kriterium. Erwartet wird eine wörtliche,
    kurze Spanne aus der Mail, z. B. „nächsten Dienstag vormittags“.
  - Die Extraktion soll deshalb wörtlich aus der Mail übernehmen statt umzuformulieren und bei
    Fehlen `null` liefern statt zu raten.
  - `anliegen` wird nur auf Nicht-Leere geprüft.
- Nachweis des Zeitpunkts: Der **erste Commit nach der Spec** enthält `holdout.sha256`, die
  SHA-256-Hashes aller Holdout-Dateien. Er entsteht vor jedem Code-Commit. Später im Repo
  veröffentlichte Dateien lassen sich dagegen prüfen.
- Abschottung: Die projektweite `.claude/settings.json` verbietet Read/Grep/Glob/Bash-Zugriff auf
  diesen Pfad. Die Builder-Prompts erwähnen den Holdout nicht.
- Abnahmeschwellen: Typ-Accuracy ≥ 0,85, Feld-Trefferquote ≥ 0,70.
- Nach der finalen Abnahme kopiert der Orchestrator Szenarien, `eval.py` und Ergebnis nach
  `holdout/` ins Repo und schreibt `docs/abnahme.md`. Darin steht, wann der Holdout angelegt wurde
  (Commit/Zeitpunkt vor dem ersten Code-Commit) und wie er abgeschottet war.
- Wenn die Schwelle verfehlt wird: höchstens eine Verbesserungsrunde. Die Builder bekommen dabei
  nur aggregierte Metriken pro Typ und Feld, nie Szenarien. Danach wird das Ergebnis ehrlich
  dokumentiert.

**Prozess-Sichtbarkeit im Repo**
- `README.md`: Was es ist, Quickstart, Abschnitt „So wurde das gebaut“ mit Links zu Spec, Plan,
  Abnahme, `CLAUDE.md` und `.claude/`.
- `docs/superpowers/specs/` (dieses Dokument) und `docs/superpowers/plans/` (Implementierungsplan).
- Ein Commit pro Plan-Task mit aussagekräftiger Nachricht. Review-Befunde und Fixes sind als
  eigene Commits sichtbar.
- `CLAUDE.md` mit Projektregeln für Agenten (synthetische Daten, gesperrte Begriffe, Commit-Format,
  Holdout-Verbot).
- Vor dem Push: ein Scan des Repos und der Commit-Historie auf den echten Namen bzw. Home-Pfad,
  auf gesperrte Begriffe und auf Nicht-`.example`-Mailadressen. Der Push nach GitHub braucht die explizite
  Bestätigung des Eigentümers.

## 5. Dem Builder überlassen

- Paketstruktur, Modulnamen, Test-Setup (pytest), Dependency-Management (empfohlen: `uv`).
- Prompt-Gestaltung der Extraktionskette und Few-Shot-Beispiele (nur aus eigenen Trainingsdaten).
- Ob Klassifikator und Extraktion parallel laufen oder nacheinander. Typ-spezifische Felder dürfen
  sich am vorhergesagten Typ orientieren.
- Größe des Trainingsdatensatzes (Richtwert 600–1200), Epochen, Sequenzlänge.
- Lösung für Host-Zugriff auf die API bei `internal`-Netz. Beispiel: ein zweites, nicht-internes Netz
  nur für den Port, während das ausgehende Netz trotzdem blockiert bleibt. Der Nachweis über das
  Egress-Test-Skript ist Pflicht.
- Form der HTML-Testseite.
