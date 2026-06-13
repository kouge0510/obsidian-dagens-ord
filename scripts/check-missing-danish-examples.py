#!/usr/bin/env python3
"""Report words missing Danish example sentences in data/deck.json."""
# python3 scripts/check-missing-danish-examples.py --export data/missing-danish-examples.json
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import NamedTuple


ROOT = Path(__file__).parent.parent
DEFAULT_DECK_PATH = ROOT / "data" / "deck.json"


class WordRef(NamedTuple):
    id: str
    word: str
    rank: int | str
    pos: str = ""


class MissingExamplesReport(NamedTuple):
    total_words: int
    with_example: int
    missing: list[WordRef]
    inconsistent: list[WordRef]


def normalize_examples(word: dict) -> list[str]:
    raw = word.get("examplesDa") or []
    if not isinstance(raw, list):
        return []
    return [item.strip() for item in raw if isinstance(item, str) and item.strip()]


def has_example_da(word: dict) -> bool:
    return bool((word.get("exampleDa") or "").strip())


def analyze_deck(deck: dict) -> MissingExamplesReport:
    words = deck.get("words", [])
    missing: list[WordRef] = []
    inconsistent: list[WordRef] = []
    with_example = 0

    for word in words:
        word_id = (word.get("id") or word.get("word") or "").strip()
        text = (word.get("word") or word_id).strip()
        rank = word.get("rank") or word.get("index") or ""
        pos = (word.get("pos") or "").strip()
        ref = WordRef(id=word_id, word=text, rank=rank, pos=pos)

        example_da = has_example_da(word)
        examples_da = normalize_examples(word)

        if example_da or examples_da:
            with_example += 1
            if examples_da and not example_da:
                inconsistent.append(ref)
            continue

        missing.append(ref)

    return MissingExamplesReport(
        total_words=len(words),
        with_example=with_example,
        missing=missing,
        inconsistent=inconsistent,
    )


def format_word_line(ref: WordRef) -> str:
    pos = f" [{ref.pos}]" if ref.pos else ""
    return f"{ref.word} (id={ref.id}, rank={ref.rank}){pos}"


def print_report(report: MissingExamplesReport, show_limit: int) -> None:
    missing_count = len(report.missing)
    print(f"Total words: {report.total_words}")
    print(f"With Danish example: {report.with_example}")
    print(f"Missing Danish example: {missing_count}")
    print(f"Inconsistent (examplesDa without exampleDa): {len(report.inconsistent)}")

    if report.missing:
        print("\nMissing words:")
        for ref in report.missing[:show_limit]:
            print(f"  - {format_word_line(ref)}")
        if missing_count > show_limit:
            print(f"  ... and {missing_count - show_limit} more")

    if report.inconsistent:
        print("\nInconsistent words:")
        for ref in report.inconsistent[:show_limit]:
            print(f"  - {format_word_line(ref)}")
        if len(report.inconsistent) > show_limit:
            print(f"  ... and {len(report.inconsistent) - show_limit} more")


def fillable_entry(ref: WordRef, word: dict | None, missing_primary: bool) -> dict:
    examples_da = normalize_examples(word or {})
    entry = {
        "id": ref.id,
        "word": ref.word,
        "rank": ref.rank,
        "pos": ref.pos,
        "exampleDa": "",
        "examplesDa": [] if missing_primary else examples_da,
    }
    return entry


def export_missing(deck: dict, report: MissingExamplesReport, path: Path) -> None:
    words_by_key: dict[tuple[str, str], dict] = {}
    for word in deck.get("words", []):
        key = (
            (word.get("id") or word.get("word") or "").strip(),
            str(word.get("rank") or word.get("index") or ""),
        )
        words_by_key[key] = word

    payload = {
        "instructions": (
            "Fill exampleDa for each item. "
            "Optionally add more lines in examplesDa. "
            "Then run: python3 scripts/apply-danish-examples.py --input "
            + str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)
        ),
        "missing": [
            fillable_entry(ref, words_by_key.get((ref.id, str(ref.rank))), missing_primary=True)
            for ref in report.missing
        ],
        "inconsistent": [
            fillable_entry(ref, words_by_key.get((ref.id, str(ref.rank))), missing_primary=False)
            for ref in report.inconsistent
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List words missing Danish examples in deck.json",
    )
    parser.add_argument("--deck", type=Path, default=DEFAULT_DECK_PATH)
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum missing words to print (default: 50)",
    )
    parser.add_argument(
        "--export",
        type=Path,
        help="Optional JSON export path for full missing/inconsistent lists",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    deck = json.loads(args.deck.read_text(encoding="utf-8"))
    report = analyze_deck(deck)
    print_report(report, show_limit=max(0, args.limit))

    if args.export:
        export_missing(deck, report, args.export)
        print(f"\nExported fillable lists to {args.export}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
