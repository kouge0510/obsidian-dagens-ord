#!/usr/bin/env python3
"""Apply filled Danish examples from JSON back into data/deck.json."""
# python3 scripts/apply-danish-examples.py --input data/missing-danish-examples.json
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import NamedTuple


ROOT = Path(__file__).parent.parent
DEFAULT_DECK_PATH = ROOT / "data" / "deck.json"
DEFAULT_INPUT_PATH = ROOT / "data" / "missing-danish-examples.json"


class ApplyResult(NamedTuple):
    matched: int
    skipped_empty: int
    not_found: int


def word_key(word: dict) -> tuple[str, str]:
    return (
        (word.get("id") or word.get("word") or "").strip(),
        str(word.get("rank") or word.get("index") or ""),
    )


def normalize_examples(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [item.strip() for item in raw if isinstance(item, str) and item.strip()]


def resolve_example_fields(entry: dict) -> tuple[str, list[str]] | None:
    examples_da = normalize_examples(entry.get("examplesDa"))
    example_da = (entry.get("exampleDa") or "").strip()

    if not example_da and examples_da:
        example_da = examples_da[0]
    if not example_da:
        return None
    if not examples_da:
        examples_da = [example_da]

    return example_da, examples_da


def iter_fill_entries(payload: dict) -> list[dict]:
    entries: list[dict] = []
    for key in ("missing", "inconsistent"):
        block = payload.get(key)
        if isinstance(block, list):
            entries.extend(block)
    return entries


def build_entry_index(entries: list[dict]) -> dict[tuple[str, str], dict]:
    index: dict[tuple[str, str], dict] = {}
    for entry in entries:
        word_id = (entry.get("id") or entry.get("word") or "").strip()
        rank = str(entry.get("rank") or "")
        if not word_id:
            continue
        index[(word_id, rank)] = entry
    return index


def apply_entries(deck: dict, entries: list[dict]) -> ApplyResult:
    index = build_entry_index(entries)
    matched = skipped_empty = 0
    not_found = len(index)

    for word in deck.get("words", []):
        key = word_key(word)
        entry = index.get(key)
        if not entry:
            continue

        not_found -= 1
        resolved = resolve_example_fields(entry)
        if not resolved:
            skipped_empty += 1
            continue

        example_da, examples_da = resolved
        word["exampleDa"] = example_da
        word["examplesDa"] = examples_da
        matched += 1

    return ApplyResult(matched=matched, skipped_empty=skipped_empty, not_found=not_found)


def apply_file(deck_path: Path, input_path: Path) -> ApplyResult:
    deck = json.loads(deck_path.read_text(encoding="utf-8"))
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    result = apply_entries(deck, iter_fill_entries(payload))
    deck_path.write_text(json.dumps(deck, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply filled Danish examples from JSON into deck.json",
    )
    parser.add_argument("--deck", type=Path, default=DEFAULT_DECK_PATH)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = apply_file(args.deck, args.input)
    print(f"Applied: {result.matched}")
    print(f"Skipped empty: {result.skipped_empty}")
    print(f"Not found in deck: {result.not_found}")
    return 0 if result.matched else 1


if __name__ == "__main__":
    raise SystemExit(main())
