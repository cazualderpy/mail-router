FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1
WORKDIR /app

# CPU-only torch (kleines Image); Versionen aus uv.lock, ohne torch/CUDA-Pakete.
COPY pyproject.toml uv.lock ./
RUN pip install uv \
    && TORCH_VERSION=$(uv export --frozen --no-dev --no-hashes --no-emit-project 2>/dev/null | sed -n 's/^torch==\([^ ;]*\).*/\1/p') \
    && pip install --index-url https://download.pytorch.org/whl/cpu "torch==${TORCH_VERSION}" \
    && uv export --frozen --no-dev --no-hashes --no-emit-project \
         --no-emit-package torch --no-emit-package triton \
         --no-emit-package cuda-bindings --no-emit-package cuda-pathfinder --no-emit-package cuda-toolkit \
         $(uv export --frozen --no-dev --no-hashes --no-emit-project 2>/dev/null | sed -n 's/^\(nvidia-[^=]*\)==.*/--no-emit-package \1/p') \
         > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt \
    && pip uninstall -y uv

COPY mail_router ./mail_router
ENV CLASSIFIER_PATH=/app/models/classifier OLLAMA_BASE_URL=http://ollama:11434 OLLAMA_MODEL=qwen2.5:3b
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "mail_router.api:app", "--host", "0.0.0.0", "--port", "8000"]
