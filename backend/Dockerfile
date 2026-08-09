FROM python:3.11-slim

WORKDIR /app

# Install deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Render injects PORT (default 10000); local Docker Compose falls back to 8001.
EXPOSE 8001

# Run with 2 workers; override via CMD in compose for dev
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8001} --workers 2"]
