#!/usr/bin/env python3
"""Backfill Chinese word translations from the Chinese Anki deck."""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).parent.parent
DEFAULT_DECK_PATH = ROOT / "data" / "deck.json"
DEFAULT_APKG_PATH = Path("/home/kouge/Downloads/DDO_Danish_Frequency_Deck_Chinese.apkg")


def parse_translations(content_html: str) -> list[str]:
    return re.findall(r'<div class="translation"><b>([^<]+)</b>', content_html)


def parse_entry_translations(fields: list[str]) -> list[str]:
    translations = parse_translations(fields[2]) if len(fields) > 2 else []
    if translations:
        return translations
    return parse_translations(fields[3]) if len(fields) > 3 else []


def load_translations(apkg_path: Path) -> dict[tuple[str, str], list[str]]:
    if not apkg_path.exists():
        raise FileNotFoundError(f"APKG not found: {apkg_path}")

    with tempfile.TemporaryDirectory() as td:
        extract_dir = Path(td)
        with zipfile.ZipFile(apkg_path, "r") as zf:
            zf.extract("collection.anki2", extract_dir)

        db_path = extract_dir / "collection.anki2"
        if not db_path.exists():
            raise FileNotFoundError(f"Anki database not found in: {apkg_path}")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT flds FROM notes")
        rows = cursor.fetchall()
        conn.close()

    translations: dict[tuple[str, str], list[str]] = {}
    for (flds,) in rows:
        fields = flds.split("\x1f")
        if len(fields) < 8:
            continue

        word = fields[0].strip()
        rank = fields[7].strip()
        entries = parse_entry_translations(fields)
        if word and rank and entries:
            translations[(word, rank)] = entries

    return translations


def backfill_deck(deck: dict, translations: dict[tuple[str, str], list[str]]) -> int:
    updated = 0

    for word in deck.get("words", []):
        key = (word.get("word") or word.get("id") or "", str(word.get("rank") or ""))
        values = [item for item in translations.get(key, []) if item]
        word["translationsZh"] = values
        word["translationZh"] = values[0] if values else ""
        if values:
            updated += 1

    return updated


def main() -> int:
    deck = json.loads(DEFAULT_DECK_PATH.read_text(encoding="utf-8"))
    translations = load_translations(DEFAULT_APKG_PATH)
    updated = backfill_deck(deck, translations)
    DEFAULT_DECK_PATH.write_text(
        json.dumps(deck, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Chinese translations loaded: {len(translations)}")
    print(f"Deck words updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
