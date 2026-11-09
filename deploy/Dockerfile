# syntax=docker/dockerfile:1
# SPDX-License-Identifier: SAEL-1.0
# Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
# Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
# License: Sovereign Authorship Enforced License (SAEL v1.0)
FROM python:3.12-slim AS base
WORKDIR /app
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir build && pip install --no-cache-dir -e . 2>/dev/null || true
COPY modules/ ./modules/
COPY scripts/ ./scripts/
RUN pip install --no-cache-dir uvicorn fastapi httpx cryptography pytest pytest-asyncio
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD curl -fs http://127.0.0.1:8000/health || exit 1
USER 65534:65534
ENTRYPOINT ["uvicorn", "modules.supervisor.service:app", "--host", "0.0.0.0", "--port", "8000"]
