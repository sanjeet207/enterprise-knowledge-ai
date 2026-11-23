# Enterprise Knowledge AI Platform: API image.
# The language model (Ollama) is not inside this image; the app reaches it over OLLAMA_URL.
# Stage 1: build the React interface. vite.config.ts writes the result to ../app/static.
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: the API image.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache \
    FLASHRANK_CACHE_DIR=/opt/flashrank-cache

WORKDIR /srv

# Dependencies first, so this layer is cached until requirements.txt changes.
# The extra index gives the CPU-only torch build (hundreds of MB smaller than the default one).
COPY requirements.txt .
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Bake the embedding and reranker models into the image so the first question is not slowed by downloads.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); from flashrank import Ranker; Ranker(model_name='ms-marco-MiniLM-L-12-v2', cache_dir='/opt/flashrank-cache')"

COPY app ./app
# The built interface replaces whatever copy of app/static the repository holds.
COPY --from=web /app/static ./app/static
COPY scripts ./scripts

# Source files keep the host's file modes when copied (a 600 file would be unreadable to the user below),
# so make everything readable regardless of where the image is built.
RUN chmod -R a+rX /srv/app /srv/scripts

# Run as a normal user, not root.
RUN useradd --system --no-create-home appuser
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
