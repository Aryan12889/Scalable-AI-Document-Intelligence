FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (build-essential for some pip packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project definition
COPY pyproject.toml .
COPY README.md .

# Install dependencies
RUN pip install --no-cache-dir -e .

# Copy Code
COPY app /app/app
COPY frontend /app/frontend

# Environment
ENV PYTHONUNBUFFERED=1

# Default Command (API) - can be overridden in compose
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
