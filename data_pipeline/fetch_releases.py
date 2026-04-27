"""
Скачивает Release Notes всех HF-библиотек через GitHub API
и сохраняет как JSONL для дальнейшей индексации в Qdrant.

Каждый релиз → отдельный документ с метаданными:
  {"text": "...", "library": "transformers", "version": "v5.6.0", "type": "release_notes"}

Запуск:
  python data_pipeline/fetch_releases.py
  python data_pipeline/fetch_releases.py --out data_pipeline/releases.jsonl --per-lib 20
  python data_pipeline/fetch_releases.py --token ghp_...   # для снятия rate limit (60→5000 req/h)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("Установите requests: pip install requests")
    sys.exit(1)

# GitHub repo names для каждой библиотеки
GITHUB_REPOS = {
    "transformers": "huggingface/transformers",
    "diffusers":    "huggingface/diffusers",
    "datasets":     "huggingface/datasets",
    "accelerate":   "huggingface/accelerate",
    "peft":         "huggingface/peft",
    "trl":          "huggingface/trl",
    "evaluate":     "huggingface/evaluate",
    "tokenizers":   "huggingface/tokenizers",
    "optimum":      "huggingface/optimum",
}
# hub-docs не имеет релизов в обычном смысле — пропускаем

DEFAULT_OUT     = "data_pipeline/releases.jsonl"
DEFAULT_PER_LIB = 30   # последних релизов на библиотеку


def clean_release_body(text: str) -> str:
    """Убираем мусор из release notes: CI-бейджи, автосгенерированные ссылки."""
    if not text:
        return ""
    # убираем HTML-комментарии
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    # убираем строки вида "* Fix ... by @username in https://..."
    # оставляем только содержательный текст
    text = re.sub(r'\*\*Full Changelog\*\*:.*', '', text)
    # убираем shields/badges
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # схлопываем лишние пустые строки
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def fetch_releases(
    repo: str,
    library: str,
    per_lib: int,
    token: str | None,
    session: requests.Session,
) -> list[dict]:
    """Скачивает per_lib последних релизов для repo."""
    url     = f"https://api.github.com/repos/{repo}/releases"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    docs = []
    page = 1
    collected = 0

    while collected < per_lib:
        resp = session.get(
            url,
            headers=headers,
            params={"per_page": min(per_lib - collected, 100), "page": page},
            timeout=15,
        )

        # rate limit
        if resp.status_code == 403:
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait  = max(reset - int(time.time()), 5)
            print(f"  [{library}] ⏳ GitHub rate limit — жду {wait}с...")
            time.sleep(wait)
            continue

        if resp.status_code != 200:
            print(f"  [{library}] GitHub API вернул {resp.status_code}")
            break

        releases = resp.json()
        if not releases:
            break

        for r in releases:
            if collected >= per_lib:
                break

            body = clean_release_body(r.get("body") or "")
            if not body:
                continue

            version = r.get("tag_name", "unknown")
            name    = r.get("name") or version
            date    = (r.get("published_at") or "")[:10]   # YYYY-MM-DD

            text = f"# {library} {name}\n\nVersion: {version}\nDate: {date}\n\n{body}"

            docs.append({
                "text":     text,
                "source":   f"releases/{version}",
                "library":  library,
                "version":  version,
                "type":     "release_notes",
                "date":     date,
            })
            collected += 1

        page += 1

    return docs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Скачать Release Notes HF-библиотек через GitHub API"
    )
    parser.add_argument(
        "--out", default=DEFAULT_OUT,
        help=f"Выходной JSONL (по умолч: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--per-lib", type=int, default=DEFAULT_PER_LIB,
        help=f"Кол-во последних релизов на библиотеку (по умолч: {DEFAULT_PER_LIB})",
    )
    parser.add_argument(
        "--token",
        help="GitHub Personal Access Token (снимает rate limit: 60→5000 req/h)",
    )
    parser.add_argument(
        "--libs", nargs="*", default=list(GITHUB_REPOS.keys()),
        help="Список библиотек (по умолч: все)",
    )
    parser.add_argument(
        "--append", action="store_true",
        help="Дописать к существующему файлу вместо перезаписи",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).parent.parent
    out_path = base_dir / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    repos = {k: v for k, v in GITHUB_REPOS.items() if k in args.libs}
    if not repos:
        print(f"Библиотеки не найдены: {args.libs}")
        sys.exit(1)

    print(f"Скачиваю Release Notes  ({args.per_lib} релизов × {len(repos)} библиотек)")
    if not args.token:
        print("Без --token GitHub лимит: 60 запросов/час. Добавьте токен для ускорения.")
    print(f"   Выход: {out_path}\n")

    session     = requests.Session()
    total       = 0
    mode        = "a" if args.append else "w"

    with open(out_path, mode, encoding="utf-8") as f:
        for library, repo in repos.items():
            docs = fetch_releases(repo, library, args.per_lib, args.token, session)
            for doc in docs:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")
            total += len(docs)
            print(f"  [{library}] ✅ {len(docs)} release notes сохранено")

    print(f"\n{'='*55}")
    print(f"  Всего документов : {total}")
    print(f"  Файл             : {out_path}")
    print(f"{'='*55}")
    print("\nСледующий шаг — добавить в корпус и переиндексировать:")
    print(f"  python data_pipeline/ingest.py --corpus {args.out}")


if __name__ == "__main__":
    main()
