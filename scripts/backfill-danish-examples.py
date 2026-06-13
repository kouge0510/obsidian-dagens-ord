#!/usr/bin/env python3
"""Backfill missing Danish examples in deck.json from an Anki .apkg deck."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).parent.parent
DEFAULT_DECK_PATH = ROOT / "data" / "deck.json"
DEFAULT_APKG_PATH = Path("/home/kouge/Downloads/DDO_Danish_Frequency_Deck_English.apkg")
DEFAULT_ANKI_DB_PATH = ROOT / "data" / ".apkg-tmp" / "collection.anki2"


def parse_examples(content_html: str) -> list[str]:
    return re.findall(r'<div class="example">E\.g\., "([^"]+)"', content_html)


def load_examples_from_db(db_path: Path) -> dict[tuple[str, str], list[str]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT flds FROM notes")

    examples_by_key: dict[tuple[str, str], list[str]] = {}
    for (flds,) in cursor.fetchall():
        fields = flds.split("\x1f")
        if len(fields) < 8:
            continue

        word = fields[0].strip()
        rank = fields[7].strip()
        content = fields[2] if len(fields) > 2 else ""
        examples = parse_examples(content)
        if word and rank and examples:
            examples_by_key[(word, rank)] = examples

    conn.close()
    return examples_by_key


def load_examples_from_apkg(apkg_path: Path) -> dict[tuple[str, str], list[str]]:
    if not apkg_path.exists():
        raise FileNotFoundError(f"APKG not found: {apkg_path}")

    with tempfile.TemporaryDirectory() as td:
        extract_dir = Path(td)
        with zipfile.ZipFile(apkg_path, "r") as zf:
            zf.extract("collection.anki2", extract_dir)

        db_path = extract_dir / "collection.anki2"
        if not db_path.exists():
            raise FileNotFoundError(f"Anki database not found in: {apkg_path}")

        return load_examples_from_db(db_path)


def word_key(word: dict) -> tuple[str, str]:
    return (
        (word.get("word") or word.get("id") or "").strip(),
        str(word.get("rank") or word.get("index") or ""),
    )


def is_missing_example(word: dict) -> bool:
    if (word.get("exampleDa") or "").strip():
        return False
    examples = word.get("examplesDa") or []
    return not any(isinstance(item, str) and item.strip() for item in examples)


def backfill_deck(deck: dict, examples_by_key: dict[tuple[str, str], list[str]]) -> int:
    updated = 0

    for word in deck.get("words", []):
        if not is_missing_example(word):
            continue

        examples = examples_by_key.get(word_key(word))
        if not examples:
            continue

        word["exampleDa"] = examples[0]
        word["examplesDa"] = examples
        updated += 1

    return updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill missing Danish examples into deck.json",
    )
    parser.add_argument("--deck", type=Path, default=DEFAULT_DECK_PATH)
    parser.add_argument("--apkg", type=Path, default=DEFAULT_APKG_PATH)
    parser.add_argument(
        "--anki-db",
        type=Path,
        default=None,
        help="Use extracted collection.anki2 instead of unpacking --apkg",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    deck = json.loads(args.deck.read_text(encoding="utf-8"))

    if args.anki_db:
        examples_by_key = load_examples_from_db(args.anki_db)
        source = args.anki_db
    else:
        examples_by_key = load_examples_from_apkg(args.apkg)
        source = args.apkg

    updated = backfill_deck(deck, examples_by_key)
    args.deck.write_text(
        json.dumps(deck, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Example source: {source}")
    print(f"Examples loaded: {len(examples_by_key)}")
    print(f"Deck words updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
