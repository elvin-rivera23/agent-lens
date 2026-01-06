FROM python:3.11-slim

WORKDIR /app

# Install system deps for subprocess execution
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Common packages for generated code execution
RUN pip install --no-cache-dir pygame numpy requests flask

COPY src/ ./src/

# Sandboxed workspace for agent file operations
RUN mkdir -p /workspace && chmod 777 /workspace

ENV PYTHONPATH=/app/src
EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
