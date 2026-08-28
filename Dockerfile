FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for postgres and compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY apps/api/app ./app
COPY apps/api/alembic.ini .
COPY apps/api/app/db/migrations ./app/db/migrations

ENV PYTHONPATH=/app
ENV APP_ENV=production
ENV PORT=8000

EXPOSE 8000

# Run FastAPI via uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
