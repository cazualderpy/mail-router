"""FastAPI-App: /route, /health und eine Testseite."""

import logging
import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from mail_router.schema import Fields, RouteRequest, RouteResponse

log = logging.getLogger(__name__)

INDEX_HTML = Path(__file__).parent / "static" / "index.html"


def create_app(
    classify: Callable[[RouteRequest], tuple[str, float]],
    extract_fields: Callable[[RouteRequest, str], Fields],
    lifespan=None,
) -> FastAPI:
    app = FastAPI(title="mail-router", lifespan=lifespan)

    @app.post("/route", response_model=RouteResponse)
    def route(req: RouteRequest) -> RouteResponse:
        mail_type, confidence = classify(req)
        try:
            fields = extract_fields(req, mail_type)
        except Exception:
            log.exception("Extraktion fehlgeschlagen, liefere leere Felder")
            fields = Fields()
        return RouteResponse(type=mail_type, confidence=confidence, fields=fields)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML.read_text(encoding="utf-8")

    return app


def _build_real_app() -> FastAPI:
    deps: dict = {}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Lazy: Modell und LLM-Client erst beim Start laden, nicht beim Import.
        from mail_router.classifier.predict import Classifier
        from mail_router.extract import build_llm, extract

        deps["classifier"] = Classifier(os.environ.get("CLASSIFIER_PATH", "models/classifier"))
        llm = build_llm(
            os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434"),
            os.environ.get("OLLAMA_MODEL", "qwen2.5:3b"),
        )
        deps["extract"] = lambda req, t: extract(req, t, llm)
        try:
            warm = RouteRequest(sender="warmup@mail.example", subject="Warmup", body="Warmup")
            deps["extract"](warm, "sonstiges")
        except Exception:
            log.exception("Warm-up von Ollama fehlgeschlagen")
        yield
        deps.clear()

    return create_app(
        lambda req: deps["classifier"].predict(req),
        lambda req, t: deps["extract"](req, t),
        lifespan=lifespan,
    )


app = _build_real_app()
