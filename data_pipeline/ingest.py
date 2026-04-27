"""
Индексирует corpus.jsonl в Qdrant.
Использует index_corpus() из hf_rag/pipeline.py.

Запуск:
  python data_pipeline/ingest.py
  python data_pipeline/ingest.py --corpus data_pipeline/corpus.jsonl --qdrant-url http://localhost:6333
  python data_pipeline/ingest.py --corpus data_pipeline/releases.jsonl --append
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_CORPUS = "data_pipeline/corpus.jsonl"
DEFAULT_QDRANT = "http://localhost:6333"
DEFAULT_BATCH  = 100


def main() -> None:
    parser = argparse.ArgumentParser(description="Индексация corpus.jsonl в Qdrant")
    parser.add_argument(
        "--corpus", default=DEFAULT_CORPUS,
        help=f"Путь к JSONL-корпусу (по умолч: {DEFAULT_CORPUS})",
    )
    parser.add_argument(
        "--qdrant-url", default=os.environ.get("QDRANT_URL", DEFAULT_QDRANT),
        help=f"URL Qdrant (по умолч: {DEFAULT_QDRANT})",
    )
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH,
        help=f"Размер батча для upsert (по умолч: {DEFAULT_BATCH})",
    )
    parser.add_argument(
        "--append", action="store_true",
        help="Дописать в существующую коллекцию (не пересоздавать). Для release notes.",
    )
    args = parser.parse_args()

    corpus_path = ROOT / args.corpus
    if not corpus_path.exists():
        print(f"Корпус не найден: {corpus_path}")
        sys.exit(1)

    os.environ["QDRANT_URL"] = args.qdrant_url

    from hf_rag.config import settings
    from hf_rag.pipeline import index_corpus

    mode = "дополнение (append)" if args.append else "полная переиндексация"
    print(f"Индексация корпуса в Qdrant  [{mode}]")
    print(f"Корпус    : {corpus_path}")
    print(f"Qdrant    : {args.qdrant_url}")
    print(f"Коллекция : {settings.qdrant_collection}")
    print(f"Батч      : {args.batch_size}\n")

    t0 = time.time()
    n_docs, n_chunks = index_corpus(
        str(corpus_path),
        batch_size=args.batch_size,
        append=args.append,
    )
    elapsed = time.time() - t0

    print(f"\n{'='*55}")
    print(f"  Документов проиндексировано : {n_docs}")
    print(f"  Чанков загружено            : {n_chunks}")
    print(f"  Коллекция                   : {settings.qdrant_collection}")
    print(f"  Время                       : {elapsed:.1f}с")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
