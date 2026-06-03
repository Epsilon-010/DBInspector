# --- builder: install deps into a dedicated layer ---
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy ONLY pyproject.toml first so deps cache on every subsequent code edit.
COPY pyproject.toml ./
# Need a minimal app dir for the editable install to validate.
RUN mkdir -p app && touch app/__init__.py
RUN pip install --user '.[api]'

# --- runtime: slim image with only the wheels + app code ---
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/root/.local/bin:$PATH

WORKDIR /app

# Bring in the installed packages from the builder.
COPY --from=builder /root/.local /root/.local

# App code.
COPY app/ ./app/
COPY pyproject.toml ./

EXPOSE 8000

# Bind 0.0.0.0 so the port is reachable from outside the container.
CMD ["python", "-m", "uvicorn", "app.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
