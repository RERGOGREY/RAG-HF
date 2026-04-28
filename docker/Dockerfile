FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential supervisor curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-версия PyTorch (без CUDA) — иначе pip тянет ~3 GB NVIDIA-пакетов
RUN pip install --no-cache-dir \
    torch==2.4.0 --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY hf_rag/ ./hf_rag/
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 8000 8501

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
