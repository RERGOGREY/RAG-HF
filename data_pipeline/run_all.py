"""
Полный pipeline: скачать документацию → fetch release notes → собрать корпус → индексировать.

Запуск:
  python data_pipeline/run_all.py
  python data_pipeline/run_all.py --version v4.40.0
  python data_pipeline/run_all.py --libs transformers diffusers --force
  python data_pipeline/run_all.py --skip-download --skip-releases   # только build + ingest
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent


def run_step(name: str, cmd: list[str]) -> bool:
    """Запускает шаг, возвращает True при успехе."""
    print(f"\n{'='*55}")
    print(f"  ▶  {name}")
    print(f"     {' '.join(cmd)}")
    print(f"{'='*55}")
    t0 = time.time()
    result = subprocess.run(cmd, cwd=ROOT)
    elapsed = time.time() - t0
    ok = result.returncode == 0
    status = "ok" if ok else "not ok"
    print(f"\n  {status}  {name} завершён за {elapsed:.1f}с  (код {result.returncode})")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Полный data pipeline: download → releases → build_corpus → ingest"
    )
    parser.add_argument(
        "--libs", nargs="*", default=None,
        help="Список библиотек (по умолч: все)",
    )
    parser.add_argument(
        "--version", default="latest",
        help="Версия документации: 'latest' или тег, например 'v4.40.0'",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Перезаписать уже скачанные данные",
    )
    parser.add_argument(
        "--qdrant-url", default="http://localhost:6333",
        help="URL Qdrant (по умолч: http://localhost:6333)",
    )
    parser.add_argument(
        "--corpus", default="data_pipeline/corpus.jsonl",
        help="Путь к основному JSONL-корпусу (по умолч: data_pipeline/corpus.jsonl)",
    )
    parser.add_argument(
        "--releases", default="data_pipeline/releases.jsonl",
        help="Путь к JSONL с release notes (по умолч: data_pipeline/releases.jsonl)",
    )
    parser.add_argument(
        "--raw-dir", default="data_pipeline/raw",
        help="Папка raw-данных (по умолч: data_pipeline/raw)",
    )
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Пропустить скачивание документации",
    )
    parser.add_argument(
        "--skip-releases", action="store_true",
        help="Пропустить скачивание release notes",
    )
    parser.add_argument(
        "--skip-build", action="store_true",
        help="Пропустить сборку корпуса",
    )
    parser.add_argument(
        "--github-token",
        help="GitHub token для fetch_releases (снимает rate limit)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=100,
        help="Размер батча для Qdrant upsert (по умолч: 100)",
    )
    args = parser.parse_args()

    py          = sys.executable
    steps_ok: list[str]   = []
    steps_fail: list[str] = []
    total_start = time.time()

    ver_label = args.version if args.version != "latest" else "latest (main)"
    print(f"\n HuggingFace Docs RAG — полный pipeline")
    print(f"Версия документации : {ver_label}")
    print(f"Библиотеки          : {args.libs or 'все'}")

    # ── Шаг 1: Скачивание документации ──────────────────────────────────────────
    if not args.skip_download:
        cmd = [py, str(HERE / "download.py"), "--out", args.raw_dir, "--version", args.version]
        if args.libs:
            cmd += ["--libs"] + args.libs
        if args.force:
            cmd += ["--force"]

        if run_step("1/4 · Скачивание документации", cmd):
            steps_ok.append("download")
        else:
            steps_fail.append("download")
            print("\n Остановлено на шаге download.")
            sys.exit(1)
    else:
        print("\n Шаг 1 (download) пропущен")

    # ── Шаг 2: Release Notes ─────────────────────────────────────────────────────
    if not args.skip_releases:
        cmd = [py, str(HERE / "fetch_releases.py"), "--out", args.releases]
        if args.libs:
            cmd += ["--libs"] + args.libs
        if args.github_token:
            cmd += ["--token", args.github_token]

        if run_step("2/4 · Скачивание Release Notes", cmd):
            steps_ok.append("fetch_releases")
        else:
            # не фатально — продолжаем без release notes
            print("\n Release Notes не удалось скачать — продолжаю без них")
            steps_fail.append("fetch_releases")
    else:
        print("\n Шаг 2 (fetch_releases) пропущен")

    # ── Шаг 3: Сборка корпуса ───────────────────────────────────────────────────
    if not args.skip_build:
        cmd = [
            py, str(HERE / "build_corpus.py"),
            "--raw-dir", args.raw_dir,
            "--out",     args.corpus,
        ]

        if run_step("3/4 · Сборка и очистка корпуса", cmd):
            steps_ok.append("build_corpus")
        else:
            steps_fail.append("build_corpus")
            print("\n Остановлено на шаге build_corpus.")
            sys.exit(1)
    else:
        print("\n Шаг 3 (build_corpus) пропущен")

    # ── Шаг 4: Индексация обоих корпусов в Qdrant ────────────────────────────────
    # Сначала индексируем основной корпус (пересоздаёт коллекцию)
    cmd = [
        py, str(HERE / "ingest.py"),
        "--corpus",     args.corpus,
        "--qdrant-url", args.qdrant_url,
        "--batch-size", str(args.batch_size),
    ]
    if not run_step("4/4 · Индексация документации в Qdrant", cmd):
        steps_fail.append("ingest_corpus")
        print("\n Ошибка индексации. Убедитесь, что Qdrant запущен:")
        print("docker-compose up -d qdrant")
        sys.exit(1)
    steps_ok.append("ingest_corpus")

    # Дописываем release notes (--append = не пересоздавать коллекцию)
    releases_path = ROOT / args.releases
    if releases_path.exists() and not args.skip_releases:
        cmd = [
            py, str(HERE / "ingest.py"),
            "--corpus",     args.releases,
            "--qdrant-url", args.qdrant_url,
            "--batch-size", str(args.batch_size),
            "--append",
        ]
        if run_step("4/4 · Индексация Release Notes в Qdrant", cmd):
            steps_ok.append("ingest_releases")
        else:
            steps_fail.append("ingest_releases")

    # ── Итог ─────────────────────────────────────────────────────────────────────
    total_elapsed = time.time() - total_start
    print(f"\n{'='*55}")
    print(f"Pipeline завершён за {total_elapsed/60:.1f} мин")
    print(f"Успешно : {steps_ok}")
    if steps_fail:
        print(f"  Ошибки  : {steps_fail}")
    print(f"{'='*55}")
    print("\nСервис можно запустить командой:")
    print("  docker-compose up -d")
    print("  UI : http://localhost:8501")
    print("  API: http://localhost:8000/docs")


if __name__ == "__main__":
    main()
