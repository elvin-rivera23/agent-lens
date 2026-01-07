FROM vllm/vllm-openai:latest

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=5 --start-period=120s \
    CMD curl -f http://localhost:8000/health || exit 1

# Command is set in docker-compose.yml for flexibility
