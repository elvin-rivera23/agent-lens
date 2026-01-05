FROM vllm/vllm-openai:latest

# Set environment variables
ENV MODEL_NAME=${MODEL:-meta-llama/Meta-Llama-3-8B-Instruct}
ENV MAX_MODEL_LEN=${MAX_MODEL_LEN:-8192}
ENV GPU_MEMORY_UTILIZATION=${GPU_MEMORY_UTILIZATION:-0.85}

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start vLLM server
CMD ["python", "-m", "vllm.entrypoints.openai.api_server", \
    "--model", "${MODEL_NAME}", \
    "--max-model-len", "${MAX_MODEL_LEN}", \
    "--gpu-memory-utilization", "${GPU_MEMORY_UTILIZATION}", \
    "--host", "0.0.0.0", \
    "--port", "8000"]
