# Multi-Platform Production Dockerfile for FlytBase Asset Intelligence Copilot
# Optimized for DigitalOcean App Platform and Docker Swarm/Kubernetes
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (curl for container health probes, build essentials)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application, database artifacts, dataset, scripts and static assets
COPY backend/ /app/backend/
COPY artifacts/ /app/artifacts/
COPY sample-data/ /app/sample-data/
COPY scripts/ /app/scripts/
COPY tests/ /app/tests/

# Pre-compile analytical DuckDB database and semantic overlay views
RUN mkdir -p /app/artifacts && \
    python3 scripts/run_ingestion.py --data-dir /app/sample-data --db-path /app/artifacts/copilot.duckdb

# Set container environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    HOST=0.0.0.0 \
    REFERENCE_TODAY=2026-10-17 \
    DATASET_ROOT=/app/sample-data \
    ARTIFACTS_DIR=/app/artifacts

# Expose default HTTP port
EXPOSE 8080

# Healthcheck probe for DigitalOcean App Platform / Kubernetes
HEALTHCHECK --interval=20s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/api/health || exit 1

# Start FastAPI server under Uvicorn
CMD ["sh", "-c", "uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
