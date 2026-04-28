# HuggingFace Docs RAG

RAG-система для поиска и ответов на вопросы по документации HuggingFace.  
Поиск: `multilingual-E5-large` → `Qdrant` → `BGE Reranker Large`. Генерация: `Qwen3-32B` (Groq).

## Требования

- Docker & Docker Compose
- Python 3.10+ (только для запуска data pipeline локально)
- [Groq API key](https://console.groq.com/keys) (бесплатный тир) — вводится в UI при каждом запросе

## Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone https://github.com/RERGOGREY/RAG-HF.git
cd RAG-HF
```

### 2. Создать `.env`

```bash
cp .env.example .env
```

Groq API key в `.env` не нужен — он вводится в UI на каждый запрос.

### 3. Запустить сервисы

```bash
docker compose up -d
```

Запускаются три контейнера: Qdrant, Redis и приложение (FastAPI + Streamlit).

Проверить, что всё поднялось:

```bash
curl http://localhost:8000/health
```

### 4. Загрузить и проиндексировать документацию

```bash
pip install -e .
python data_pipeline/run_all.py
```

Скачивает документацию 10 библиотек HuggingFace, собирает корпус и индексирует его в Qdrant. Занимает ~15–30 минут.

### 5. Открыть интерфейс

| Сервис | URL |
|--------|-----|
| Streamlit UI | http://localhost:8501 |
| FastAPI docs | http://localhost:8000/docs |
| Qdrant Dashboard | http://localhost:6333/dashboard |

Введи Groq API key в боковой панели Streamlit и задай вопрос. Ключ хранится только в текущей сессии браузера.

---

## Data pipeline подробнее

Шаги можно запускать по отдельности:

```bash
# Скачать .md файлы (параллельно, git sparse-checkout)
python data_pipeline/download.py

# Скачать GitHub Releases (changelog'и)
python data_pipeline/fetch_releases.py

# Очистить и собрать corpus.jsonl
python data_pipeline/build_corpus.py

# Проиндексировать в Qdrant
python data_pipeline/ingest.py
```

Скачать документацию конкретной версии:

```bash
python data_pipeline/download.py --version v4.40.0
```

Поддерживаемые библиотеки: `transformers` · `diffusers` · `datasets` · `accelerate` · `peft` · `trl` · `evaluate` · `tokenizers` · `optimum` · `hub-docs`

---

## API

### Задать вопрос

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I apply LoRA fine-tuning with PEFT?",
    "groq_api_key": "gsk_..."
  }'
```

### Только векторный поиск (без генерации, ключ не нужен)

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "gradient checkpointing", "top_k": 5}'
```

### Статистика кэша

```bash
curl http://localhost:8000/cache/stats
```

---

## Конфигурация

| Переменная | Описание | По умолчанию |
|-----------|----------|-------------|
| `GROQ_MODEL` | Модель генерации | `qwen/qwen3-32b` |
| `EMBEDDING_MODEL` | Модель эмбеддингов | `intfloat/multilingual-e5-large` |
| `RERANKER_MODEL` | Модель переранжирования | `BAAI/bge-reranker-large` |
| `QDRANT_URL` | URL векторной БД | `http://qdrant:6333` |
| `CORPUS_PATH` | Путь к корпусу | `data_pipeline/corpus.jsonl` |
| `CHUNK_SIZE` | Размер чанка (символов) | `600` |
| `TOP_K_RETRIEVE` | Кандидатов из Qdrant | `40` |
| `TOP_K_FINAL` | Финальных чанков после rerank | `5` |

---

## Структура проекта

```
hf_rag/
  pipeline.py      # E5-large → Qdrant → BGE Reranker → Qwen3-32B
  api.py           # FastAPI эндпоинты (/ask, /search, /health)
  ui.py            # Streamlit интерфейс
  cache.py         # Redis кэш (TTL 1 час)
  config.py        # Pydantic Settings

data_pipeline/
  download.py       # Параллельное скачивание 10 HF-библиотек
  fetch_releases.py # Скачивание GitHub Releases
  build_corpus.py   # Очистка .md → corpus.jsonl
  ingest.py         # Индексация в Qdrant
  run_all.py        # Оркестратор: download → releases → build → ingest

docker/
  Dockerfile        # Python 3.10 + CPU PyTorch
  supervisord.conf  # FastAPI + Streamlit в одном контейнере
docker-compose.yml  # app + qdrant + redis
pyproject.toml      # Зависимости
```
