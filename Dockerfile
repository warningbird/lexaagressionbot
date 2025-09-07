# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (tzdata optional for correct timestamps)
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better layer caching)
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy application source
COPY . .

# Runtime env
ENV BOT_TOKEN="" \
    OPENAI_API_KEY="" \
    OPENAI_MODEL="gpt-4o-mini"

# Default command
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import socket; import sys; s=socket.socket(); sys.exit(0)"

CMD ["python", "main.py"]


