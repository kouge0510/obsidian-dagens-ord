#!/usr/bin/env python3
"""Backfill missing deck translations from Anki's fallback definition field."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path


ROOT = Path(__file__).parent.parent
DEFAULT_DECK_PATH = ROOT / "data" / "deck.json"
DEFAULT_ANKI_DB_PATH = ROOT / "data" / ".apkg-tmp" / "collection.anki2"


def parse_translations(content_html: str) -> list[str]:
    return re.findall(r'<div class="translation"><b>([^<]+)</b>', content_html)


def load_fallback_translations(db_path: Path) -> dict[tuple[str, str], list[str]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT flds FROM notes")

    translations: dict[tuple[str, str], list[str]] = {}
    for (flds,) in cursor.fetchall():
        fields = flds.split("\x1f")
        if len(fields) < 8:
            continue
        word = fields[0].strip()
        rank = fields[7].strip()
        fallback = parse_translations(fields[3]) if len(fields) > 3 else []
        if word and rank and fallback:
            translations[(word, rank)] = fallback

    conn.close()
    return translations


def backfill_deck(deck: dict, fallback: dict[tuple[str, str], list[str]]) -> int:
    updated = 0
    for word in deck.get("words", []):
        existing = [t for t in (word.get("translationsEn") or []) if t]
        if word.get("translationEn") or existing:
            continue

        key = (word.get("word") or word.get("id") or "", str(word.get("rank") or ""))
        translations = fallback.get(key)
        if not translations:
            continue

        word["translationEn"] = translations[0]
        word["translationsEn"] = translations
        updated += 1

    return updated


def main() -> int:
    deck = json.loads(DEFAULT_DECK_PATH.read_text(encoding="utf-8"))
    fallback = load_fallback_translations(DEFAULT_ANKI_DB_PATH)
    updated = backfill_deck(deck, fallback)
    DEFAULT_DECK_PATH.write_text(
        json.dumps(deck, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Fallback definitions loaded: {len(fallback)}")
    print(f"Deck words updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
