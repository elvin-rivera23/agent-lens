FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    prometheus-client \
    psutil

COPY src/ /app/

EXPOSE 9835

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:9835/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9835"]
