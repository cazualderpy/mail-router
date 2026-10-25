# MVZ-Posteingangs-Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lokaler Router, der synthetische Patientenmails per feinabgestimmtem DistilBERT nach Typ klassifiziert und per LangChain + Ollama Felder extrahiert. Läuft per Docker Compose ohne Internetzugang.

**Architecture:** Python-Paket `mail_router` mit vier Bausteinen: Schema, Datengenerator, Klassifikator, Extraktion. Darauf sitzt eine FastAPI-App. Compose startet `ollama` und `api` in einem `internal`-Netz. Ein `gateway` (nginx) hängt zusätzlich im Edge-Netz und reicht nur Port 8000 durch.

**Tech Stack:** Python 3.12 (uv), PyTorch, transformers, FastAPI, Pydantic v2, langchain-ollama, pytest, Docker Compose, Ollama `qwen2.5:3b`.

**Spec:** `docs/superpowers/specs/2026-10-25-mail-router-design.md`

## Global Constraints

- Nur synthetische Daten. Mailadressen und Domains ausschließlich `*.example`.
- Kein Netzaufruf zur Laufzeit. Downloads (HuggingFace, `ollama pull`) nur in `make setup`.
- Keine absoluten Home-Pfade und keine echten Personennamen in Dateien oder Commits. Relative Pfade verwenden.
- Ein Commit pro Task. Jede Commit-Nachricht endet mit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Python **3.12** fest über `.python-version`. Der Host hat 3.15, dafür gibt es keine torch-Wheels.
- Typen exakt: `termin`, `rezept`, `ueberweisung`, `befund`, `au`, `sonstiges`.
- Felder exakt: `patient_name`, `geburtsdatum` (ISO `YYYY-MM-DD`), `anliegen`, `wunschtermin` (nur termin), `medikament` (nur rezept), `fachrichtung` (nur ueberweisung), `au_zeitraum` (nur au). Nicht zutreffend → `null`.
- Extraktion übernimmt wörtliche Spannen aus der Mail (außer `anliegen` und `geburtsdatum`) und liefert bei Fehlen `null` statt zu raten.
- Basismodell `distilbert/distilbert-base-german-cased`. Ollama-Modell `qwen2.5:3b`. Klassifikator-Gewichte in `models/classifier/` (git-ignoriert).
- Die Gerätewahl beim Training ist automatisch: MPS → CUDA → CPU.
- Latenz-Ziel < 30 s pro Mail auf CPU: `num_predict` ≤ 256, `temperature` 0, Warm-up beim Start.

## Review Focus

1. Ollama ist nicht erreichbar oder liefert Müll. Erwartung: `/route` antwortet trotzdem mit 200, mit dem Typ des Klassifikators und allen Feldern `null`. Test in Task 5.
2. Das LLM halluziniert Werte, die nicht in der Mail stehen. Erwartung: Solche Werte werden auf `null` gesetzt. Test in Task 4.
3. Geburtsdaten stehen in fremden Formaten (`02.11.1990`, `*07.06.1968`, `12 March 1979`, `1985-09-30`, `12. März 1979`). Erwartung: Das Ergebnis ist ISO. Test in Task 4.
4. Leere Mail (Betreff und Body leer) oder fehlende Keys. Erwartung: 422, kein 500. Test in Task 5.
5. Sehr lange Mail (> 512 Tokens). Erwartung: Der Text wird abgeschnitten, kein Absturz. Test in Task 3.

---

### Task 1: Projektgerüst und Schema

**Files:**
- Create: `pyproject.toml`, `.python-version`, `mail_router/__init__.py`, `mail_router/schema.py`
- Test: `tests/test_schema.py`

**Interfaces:**
- Produces:
  - `MAIL_TYPES: tuple[str, ...]` (die 6 Typen in obiger Reihenfolge)
  - `TYPE_FIELDS: dict[str, str | None]`, d. h. das typ-spezifische Feld pro Typ: `{"termin": "wunschtermin", "rezept": "medikament", "ueberweisung": "fachrichtung", "au": "au_zeitraum", "befund": None, "sonstiges": None}`
  - Pydantic-Modelle `RouteRequest(sender: str, subject: str, body: str)`, `Fields` (alle 7 Felder `str | None = None`), `RouteResponse(type: Literal[...], confidence: float, fields: Fields)`
  - `def to_text(req: RouteRequest) -> str`, liefert `f"Betreff: {subject}\n\n{body}"`. Das ist die einzige Textform für Klassifikator und Extraktion.

- [ ] **Step 1: Write the failing test**

```python
def test_route_request_rejects_empty_mail():
    with pytest.raises(ValidationError):
        RouteRequest(sender="a@b.example", subject="  ", body="")

def test_fields_default_null():
    assert Fields().model_dump() == {k: None for k in ["patient_name","geburtsdatum","anliegen","wunschtermin","medikament","fachrichtung","au_zeitraum"]}

def test_to_text():
    assert to_text(RouteRequest(sender="x@y.example", subject="Hi", body="Text")) == "Betreff: Hi\n\nText"

def test_type_fields_cover_all_types():
    assert set(TYPE_FIELDS) == set(MAIL_TYPES)
```

- [ ] **Step 2: Run** `uv run pytest tests/test_schema.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement.** Set up `pyproject.toml` with dependencies `torch`, `transformers`, `fastapi`, `uvicorn`, `pydantic>=2`, `langchain-ollama`, `langchain-core`, `faker`, `accelerate`, dev group `pytest`, `httpx`, plus `.python-version` = `3.12`. Add pytest marker `slow` (deselected by default via `addopts = "-m 'not slow'"`). `RouteRequest` raises a model validator error if `subject` and `body` are both empty after strip.
- [ ] **Step 4: Run** `uv run pytest -v`. Expected: 4 passed.
- [ ] **Step 5: Commit** `feat: Projektgerüst und API-Schema`

### Task 2: Synthetischer Trainingsdaten-Generator

**Files:**
- Create: `mail_router/data/__init__.py`, `mail_router/data/generate.py`, `data/train.jsonl`, `data/val.jsonl` (generated, committed)
- Test: `tests/test_generate.py`

**Interfaces:**
- Consumes: `MAIL_TYPES`, `TYPE_FIELDS`, `Fields` from Task 1
- Produces:
  - `@dataclass Example(sender: str, subject: str, body: str, type: str, fields: Fields)`
  - `def generate(n_per_type: int, seed: int) -> list[Example]`
  - CLI `uv run python -m mail_router.data.generate` → writes 150 per type, seed 42, split 80/20 (stratified, seed 42) to `data/train.jsonl` / `data/val.jsonl`. One line per example: `{"sender","subject","body","type","fields":{...}}`

Variation is the point (spec: no memorisable templates). Per type at least 8 phrasing variants combined with random greetings and sign-offs, formal/informal, ~15 % English, ~15 % lowercase/typos, optional birthdate in different formats (`dd.mm.yyyy`, `*dd.mm.yyyy`, `geb. am …`, ISO, `12 March 1979`), sometimes a third person (child/parent as patient), sometimes a secondary topic. Names via Faker `de_DE`/`en_GB`, sender always `<local>@<domain>.example`. Note `TYPE_FIELDS`: only the type-specific field is set, the others are `null`.

- [ ] **Step 1: Write the failing tests**

```python
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
        for k in ("patient_name","wunschtermin","medikament","fachrichtung","au_zeitraum"):
            v = getattr(e.fields, k)
            if v: assert v.lower() in e.body.lower()

def test_only_type_specific_field_set():
    for e in generate(30, seed=0):
        for t, f in TYPE_FIELDS.items():
            if f and t != e.type: assert getattr(e.fields, f) is None

def test_variety():
    bodies = [e.body for e in generate(100, seed=0)]
    assert len(set(bodies)) / len(bodies) > 0.95
```

- [ ] **Step 2: Run** `uv run pytest tests/test_generate.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `generate`** as described above, plus the `__main__` CLI.
- [ ] **Step 4: Run** the tests. Expected: PASS. Then `uv run python -m mail_router.data.generate`. Expected: 720 / 180 lines.
- [ ] **Step 5: Commit** `feat: synthetischer Datengenerator und Trainingsdaten`

### Task 3: Klassifikator (Training und Inferenz)

**Files:**
- Create: `mail_router/classifier/__init__.py`, `mail_router/classifier/train.py`, `mail_router/classifier/predict.py`, `docs/training.md` (generated by training)
- Test: `tests/test_classifier.py`

**Interfaces:**
- Consumes: `MAIL_TYPES`, `RouteRequest`, `to_text`, `data/*.jsonl`
- Produces:
  - `def pick_device() -> str` → `"mps" | "cuda" | "cpu"`
  - CLI `uv run python -m mail_router.classifier.train --out models/classifier [--epochs 4]`, saves model + tokenizer with `id2label` in `MAIL_TYPES` order, writes `docs/training.md` (val accuracy, macro-F1, classification report, confusion matrix, epochs, device, duration)
  - `class Classifier: __init__(self, path: str); predict(self, req: RouteRequest) -> tuple[str, float]` (label, softmax probability). CPU inference, `truncation=True, max_length=256`.

- [ ] **Step 1: Write the failing tests**

```python
def test_pick_device_valid():
    assert pick_device() in {"mps", "cuda", "cpu"}

@pytest.mark.slow
def test_predict_shape_and_long_input():
    clf = Classifier("models/classifier")
    label, conf = clf.predict(RouteRequest(sender="a@b.example", subject="Rezept", body="Bitte Rezept für Ramipril. " * 400))
    assert label in MAIL_TYPES and 0.0 <= conf <= 1.0

@pytest.mark.slow
def test_obvious_cases():
    clf = Classifier("models/classifier")
    assert clf.predict(RouteRequest(sender="a@b.example", subject="AU", body="Ich brauche eine Krankschreibung bis Freitag."))[0] == "au"
```

- [ ] **Step 2: Run** `uv run pytest tests/test_classifier.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement** `pick_device`, `train.py` (plain PyTorch loop or `Trainer`, lr 5e-5, batch 16, max_length 256, seed 42) and `predict.py`.
- [ ] **Step 4: Train** with `uv run python -m mail_router.classifier.train --out models/classifier`. Expected: `docs/training.md` exists, val accuracy is noted. Then `uv run pytest -m slow tests/test_classifier.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: DistilBERT-Klassifikator mit Training und Inferenz` (including `docs/training.md`, without `models/`)

### Task 4: Feldextraktion (LangChain + Ollama)

**Files:**
- Create: `mail_router/extract.py`
- Test: `tests/test_extract.py`

**Interfaces:**
- Consumes: `RouteRequest`, `Fields`, `TYPE_FIELDS`, `to_text`
- Produces:
  - `def parse_birthdate(s: str | None) -> str | None`
  - `def normalize_fields(raw: Fields, mail_type: str, text: str) -> Fields`
  - `def build_llm(base_url: str, model: str = "qwen2.5:3b") -> Runnable`, wraps `ChatOllama(..., temperature=0, num_predict=256).with_structured_output(Fields)`
  - `def extract(req: RouteRequest, mail_type: str, llm: Runnable) -> Fields`, runs prompt | llm and then `normalize_fields`. `llm` is any Runnable that returns `Fields`, which tests can replace with `RunnableLambda`.

`normalize_fields` rules:
- Fields not belonging to `mail_type` → `null` (via `TYPE_FIELDS`).
- `patient_name`, `wunschtermin`, `medikament`, `fachrichtung`, `au_zeitraum` not contained in the text (case-insensitive) → `null`.
- `geburtsdatum` through `parse_birthdate`.
- Empty strings → `null`.

The prompt is German. It names the type, demands verbatim spans and `null` when missing, and includes 2–3 few-shot examples from `data/train.jsonl`, hard-coded.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("raw,iso", [("02.11.1990","1990-11-02"),("*07.06.1968","1968-06-07"),("12 March 1979","1979-03-12"),("12. März 1979","1979-03-12"),("1985-09-30","1985-09-30"),("geb. am 3.3.1938","1938-03-03"),("unbekannt",None),(None,None)])
def test_parse_birthdate(raw, iso):
    assert parse_birthdate(raw) == iso

def test_normalize_drops_hallucinations_and_foreign_fields():
    text = "Bitte Rezept für Ramipril 5 mg. Gerda Pohl"
    raw = Fields(patient_name="Gerda Pohl", medikament="Ramipril 5 mg", wunschtermin="morgen", fachrichtung="Kardiologie", anliegen="Folgerezept")
    out = normalize_fields(raw, "rezept", text)
    assert out.medikament == "Ramipril 5 mg" and out.patient_name == "Gerda Pohl"
    assert out.wunschtermin is None and out.fachrichtung is None and out.anliegen == "Folgerezept"

def test_normalize_drops_value_not_in_text():
    out = normalize_fields(Fields(medikament="Aspirin"), "rezept", "Rezept für Ramipril bitte")
    assert out.medikament is None

def test_extract_uses_llm_and_normalizes():
    fake = RunnableLambda(lambda _: Fields(patient_name="Tim Sauer", medikament="L-Thyroxin", geburtsdatum="01.02.1990"))
    req = RouteRequest(sender="t@s.example", subject="rezept", body="mein L-Thyroxin ist alle. Tim Sauer, 01.02.1990")
    out = extract(req, "rezept", fake)
    assert out.geburtsdatum == "1990-02-01" and out.medikament == "L-Thyroxin"
```

- [ ] **Step 2: Run** `uv run pytest tests/test_extract.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** as specified above.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** `feat: Feldextraktion per LangChain-Kette mit Ollama`

### Task 5: FastAPI-App

**Files:**
- Create: `mail_router/api.py`, `mail_router/static/index.html`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `Classifier.predict`, `extract`, `build_llm`, schema
- Produces:
  - `def create_app(classify: Callable[[RouteRequest], tuple[str, float]], extract_fields: Callable[[RouteRequest, str], Fields]) -> FastAPI`
  - Module variable `app` for uvicorn. It builds the real dependencies from the env vars `CLASSIFIER_PATH` (default `models/classifier`), `OLLAMA_BASE_URL` (default `http://ollama:11434`) and `OLLAMA_MODEL` (default `qwen2.5:3b`), lazily on the startup event, with one warm-up call to Ollama whose errors are only logged.
  - Routes: `POST /route` → `RouteResponse`, `GET /health` → `{"status":"ok"}`, `GET /` → `index.html` (form: sender/subject/body, shows JSON result)

If `extract_fields` raises an exception, `/route` logs it and returns `Fields()` (all `null`) with status 200.

- [ ] **Step 1: Write the failing tests** (TestClient, fakes instead of models)

```python
def make(extract_fields=lambda r, t: Fields(patient_name="X")):
    return TestClient(create_app(lambda r: ("rezept", 0.9), extract_fields))

def test_route_contract():
    r = make().post("/route", json={"sender":"a@b.example","subject":"s","body":"b"})
    assert r.status_code == 200
    assert r.json() == {"type":"rezept","confidence":0.9,"fields":{**{k: None for k in Fields.model_fields}, "patient_name":"X"}}

def test_extraction_failure_degrades():
    def boom(r, t): raise ConnectionError("ollama down")
    r = make(boom).post("/route", json={"sender":"a@b.example","subject":"s","body":"b"})
    assert r.status_code == 200 and r.json()["type"] == "rezept"
    assert all(v is None for v in r.json()["fields"].values())

@pytest.mark.parametrize("payload", [{"sender":"a@b.example","subject":"","body":"  "}, {"subject":"s"}])
def test_bad_request_422(payload):
    assert make().post("/route", json=payload).status_code == 422

def test_health_and_index():
    c = make()
    assert c.get("/health").json() == {"status":"ok"}
    assert "<form" in c.get("/").text
```

- [ ] **Step 2: Run** `uv run pytest tests/test_api.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `create_app`, `app` and `index.html` (vanilla JS fetch, no CDN, because it has to work offline).
- [ ] **Step 4: Run** `uv run pytest -v`. Expected: all fast tests pass.
- [ ] **Step 5: Commit** `feat: FastAPI-App mit Route, Health und Testseite`

### Task 6: Docker Compose ohne Internetzugang

**Files:**
- Create: `Dockerfile`, `compose.yaml`, `deploy/nginx.conf`, `Makefile`, `scripts/check_egress.sh`, `.dockerignore`

**Interfaces:**
- Consumes: `mail_router.api:app`, `models/classifier/`
- Produces: `make setup` (uv sync, generate data, download base model, train, `ollama pull` over the setup network), `make up`, `make down`, `make test`, `make egress-check`. API on the host at `http://localhost:8000`.

Network design, as decided:
- Network `backend` with `internal: true`: contains `ollama`, `api`, `gateway`.
- Network `edge` (normal): contains only `gateway`, which publishes `8000:8000`.
- `gateway` = `nginx:alpine` with `proxy_pass http://api:8000`, `proxy_read_timeout 180s`.
- `ollama-pull`: Compose service with `profiles: [setup]` on `edge`, same volume `ollama`. It runs `ollama serve` in the background and then `ollama pull qwen2.5:3b`.
- The `api` image is `python:3.12-slim` with CPU torch, model mounted read-only (`./models/classifier:/app/models/classifier:ro`).
- `ollama` gets `OLLAMA_KEEP_ALIVE=24h`.

- [ ] **Step 1: Write `scripts/check_egress.sh`.** It runs `docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('https://example.com', timeout=5)"`, and the same for `ollama` with `ollama pull tinyllama` or `wget`. Exit 0 only if **both** fail. It prints `EGRESS BLOCKED` / `EGRESS OPEN`.
- [ ] **Step 2: Write Dockerfile, compose.yaml, nginx.conf, Makefile.**
- [ ] **Step 3: Verify.** Run `make setup` (if the model already exists, the train step may be skipped) and `make up`. Then:
  - `curl -s localhost:8000/health` → `{"status":"ok"}`
  - `curl -s -X POST localhost:8000/route -H 'Content-Type: application/json' -d '{"sender":"a@b.example","subject":"Rezept","body":"Bitte Folgerezept für Ramipril 5 mg. Gerda Pohl, geb. 19.08.1949"}'` → type `rezept`, `medikament` contains Ramipril, latency < 30 s
  - `make egress-check` → `EGRESS BLOCKED`
- [ ] **Step 4: Commit** `feat: Docker Compose mit internem Netz und Egress-Nachweis`

### Task 7: README mit Bauprozess

**Files:**
- Create: `README.md`

Contents:
1. One-paragraph pitch: local, privacy-preserving, synthetic data.
2. Architecture diagram (Mermaid: gateway → api → classifier / ollama, backend network internal).
3. Quickstart (`make setup`, `make up`, open `localhost:8000`, approximate durations, Docker RAM 8 GB).
4. Section **„So wurde das gebaut“**. Links to spec, plan, `CLAUDE.md`, `.claude/settings.json` (holdout lock), `holdout.sha256`, `docs/training.md`, `docs/abnahme.md`. Describes the workflow: brainstorming → spec → reviewer check → holdout before code → plan → one subagent per task with review → independent acceptance. Points to `git log` as evidence.
5. Limitations, stated honestly: synthetic data only, CPU latency, not a medical product.

- [ ] **Step 1: Write** the README. Write the acceptance numbers as a placeholder line `Ergebnis: siehe docs/abnahme.md`; the orchestrator fills that file.
- [ ] **Step 2: Verify** that every relative link points to a file that exists (except `docs/abnahme.md`, `holdout/`).
- [ ] **Step 3: Commit** `docs: README mit Architektur und Bauprozess`

---

**After the plan (orchestrator only, not builder agents):** run the holdout eval against the running stack; if needed, one round of improvements with aggregated metrics only; copy `holdout/`, check hashes, write `docs/abnahme.md`, scan for blocked terms, name and home path, push after the owner's approval.
