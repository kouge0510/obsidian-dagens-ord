#!/usr/bin/env python3
"""Backfill missing word-level translations in deck.json from manual overrides."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import NamedTuple


ROOT = Path(__file__).parent.parent
DEFAULT_DECK_PATH = ROOT / "data" / "deck.json"
DEFAULT_MANUAL_PATH = ROOT / "data" / "manual-word-translations.json"


class ApplyResult(NamedTuple):
    en_updated: int
    zh_updated: int
    not_found: int


def has_translation_en(word: dict) -> bool:
    if (word.get("translationEn") or "").strip():
        return True
    return any(item.strip() for item in (word.get("translationsEn") or []) if isinstance(item, str))


def has_translation_zh(word: dict) -> bool:
    if (word.get("translationZh") or "").strip():
        return True
    return any(item.strip() for item in (word.get("translationsZh") or []) if isinstance(item, str))


def word_key(word: dict) -> tuple[str, str]:
    return (
        (word.get("id") or word.get("word") or "").strip(),
        str(word.get("rank") or word.get("index") or ""),
    )


def build_manual_index(entries: list[dict]) -> dict[tuple[str, str], dict]:
    index: dict[tuple[str, str], dict] = {}
    for entry in entries:
        word_id = (entry.get("id") or entry.get("word") or "").strip()
        rank = str(entry.get("rank") or "")
        if word_id and rank:
            index[(word_id, rank)] = entry
    return index


def apply_manual_translations(deck: dict, manual_index: dict[tuple[str, str], dict]) -> ApplyResult:
    en_updated = zh_updated = 0
    not_found = len(manual_index)

    for word in deck.get("words", []):
        entry = manual_index.get(word_key(word))
        if not entry:
            continue

        not_found -= 1

        if not has_translation_en(word):
            values_en = [item.strip() for item in entry.get("translationsEn") or [] if item.strip()]
            if values_en:
                word["translationsEn"] = values_en
                word["translationEn"] = values_en[0]
                en_updated += 1

        if not has_translation_zh(word):
            values_zh = [item.strip() for item in entry.get("translationsZh") or [] if item.strip()]
            if values_zh:
                word["translationsZh"] = values_zh
                word["translationZh"] = values_zh[0]
                zh_updated += 1

    return ApplyResult(en_updated=en_updated, zh_updated=zh_updated, not_found=not_found)


def apply_manual_file(deck_path: Path, manual_path: Path) -> ApplyResult:
    deck = json.loads(deck_path.read_text(encoding="utf-8"))
    payload = json.loads(manual_path.read_text(encoding="utf-8"))
    entries = payload.get("entries", [])
    result = apply_manual_translations(deck, build_manual_index(entries))
    deck_path.write_text(json.dumps(deck, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill missing word translations from manual-word-translations.json",
    )
    parser.add_argument("--deck", type=Path, default=DEFAULT_DECK_PATH)
    parser.add_argument("--manual", type=Path, default=DEFAULT_MANUAL_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = apply_manual_file(args.deck, args.manual)
    print(f"English updated: {result.en_updated}")
    print(f"Chinese updated: {result.zh_updated}")
    print(f"Manual entries not found in deck: {result.not_found}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
