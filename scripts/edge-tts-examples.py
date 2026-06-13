#!/usr/bin/env python3
"""Generate Danish example sentence audio with the local edge-tts CLI."""
# python3 "/home/kouge/Desktop/obsidian addons/obsidian-dagens-ord/scripts/edge-tts-examples.py" --mode word --jobs 4
# npm run build
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Iterable, NamedTuple


ROOT = Path(__file__).parent.parent
DEFAULT_DECK_PATH = ROOT / "data" / "deck.json"
DEFAULT_EXAMPLE_OUT_DIR = ROOT / "audio" / "generated"
DEFAULT_WORD_OUT_DIR = ROOT / "audio" / "anki"
DEFAULT_VOICE = "da-DK-ChristelNeural"
DEFAULT_JOBS = 4
DEFAULT_RETRIES = 2
DEFAULT_RETRY_DELAY = 2.0
SUPPORTED_EXTENSIONS = (".mp3", ".ogg", ".wav")


class ExampleItem(NamedTuple):
    cache_key: str
    text: str
    output_name: str | None = None
    word_id: str | None = None
    audio_field_needs_update: bool = False


AudioItem = ExampleItem


class BatchResult(NamedTuple):
    selected: int
    skipped: int
    generated: int
    failed: int
    completed_items: list[AudioItem]


Runner = Callable[..., object]


class ItemResult(NamedTuple):
    generated: int
    failed: int
    completed_item: AudioItem | None


def load_deck(path: Path = DEFAULT_DECK_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_deck(path: Path, deck: dict) -> None:
    path.write_text(json.dumps(deck, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iter_example_items(deck: dict, count: int = 0) -> Iterable[ExampleItem]:
    words = deck.get("words", [])
    if count > 0:
        words = words[:count]

    for word in words:
        example = (word.get("exampleDa") or "").strip()
        word_id = (word.get("id") or "").strip()
        if not word_id or not example:
            continue
        yield ExampleItem(cache_key=f"ex-{word_id}", text=example)


def iter_missing_word_items(
    deck: dict,
    out_dir: Path,
    count: int = 0,
) -> Iterable[AudioItem]:
    words = deck.get("words", [])
    if count > 0:
        words = words[:count]

    for word in words:
        word_id = (word.get("id") or "").strip()
        text = (word.get("word") or "").strip()
        if not word_id or not text:
            continue

        existing_name = (word.get("audioWord") or "").strip()
        needs_update = not existing_name
        output_name = existing_name or f"tts-word-{word_id}.mp3"
        cache_key = f"word-{word_id}"

        if not needs_update and audio_exists(out_dir, existing_name.removesuffix(".mp3").removesuffix(".ogg").removesuffix(".wav")):
            continue

        yield AudioItem(
            cache_key=cache_key,
            text=text,
            output_name=output_name,
            word_id=word_id,
            audio_field_needs_update=needs_update,
        )


def audio_exists(out_dir: Path, cache_key: str) -> bool:
    return any(
        (path := out_dir / f"{cache_key}{ext}").exists() and path.stat().st_size > 0
        for ext in SUPPORTED_EXTENSIONS
    )


def build_edge_tts_command(
    voice: str,
    text: str,
    out_path: Path,
    rate: str,
) -> list[str]:
    return [
        "edge-tts",
        "--voice",
        voice,
        "--rate",
        rate,
        "--text",
        text,
        "--write-media",
        str(out_path),
    ]


def generate_one_audio(
    item: ExampleItem,
    out_dir: Path,
    voice: str,
    rate: str,
    retries: int,
    retry_delay: float,
    runner: Runner,
) -> ItemResult:
    output_name = item.output_name or f"{item.cache_key}.mp3"
    out_path = out_dir / output_name
    command = build_edge_tts_command(
        voice=voice,
        text=item.text,
        out_path=out_path,
        rate=rate,
    )
    print(f"  -> 生成 {item.cache_key}: {item.text[:60]}...")

    last_error: subprocess.CalledProcessError | OSError | None = None
    for attempt in range(retries + 1):
        try:
            runner(command, check=True, capture_output=True, text=True)
            return ItemResult(generated=1, failed=0, completed_item=item)
        except (subprocess.CalledProcessError, OSError) as err:
            last_error = err
            remove_partial_file(out_path)
            if attempt < retries:
                print(
                    f"  ! {item.cache_key} 第 {attempt + 1} 次失败，准备重试...",
                    file=sys.stderr,
                )
                if retry_delay > 0:
                    time.sleep(retry_delay)

    print(f"  x 失败 {item.cache_key}: {format_runner_error(last_error)}", file=sys.stderr)
    return ItemResult(generated=0, failed=1, completed_item=None)


def remove_partial_file(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def format_runner_error(err: subprocess.CalledProcessError | OSError | None) -> str:
    if err is None:
        return "unknown error"
    if isinstance(err, subprocess.CalledProcessError):
        stderr = (err.stderr or "").strip()
        if stderr:
            return stderr.splitlines()[-1]
    return str(err)


def generate_audio(
    items: Iterable[ExampleItem],
    out_dir: Path,
    voice: str,
    rate: str,
    overwrite: bool,
    jobs: int = DEFAULT_JOBS,
    retries: int = DEFAULT_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY,
    runner: Runner = subprocess.run,
) -> BatchResult:
    selected = skipped = generated = failed = 0
    completed_items: list[AudioItem] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    pending: list[ExampleItem] = []

    for item in items:
        selected += 1

        output_stem = Path(item.output_name or f"{item.cache_key}.mp3").stem
        if not overwrite and audio_exists(out_dir, output_stem):
            skipped += 1
            print(f"  - 跳过已存在: {item.cache_key}")
            continue

        pending.append(item)

    if not pending:
        return BatchResult(
            selected=selected,
            skipped=skipped,
            generated=generated,
            failed=failed,
            completed_items=completed_items,
        )

    worker_count = max(1, jobs)
    if worker_count == 1:
        for item in pending:
            result = generate_one_audio(
                item,
                out_dir,
                voice,
                rate,
                retries,
                retry_delay,
                runner,
            )
            generated += result.generated
            failed += result.failed
            if result.completed_item:
                completed_items.append(result.completed_item)
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(
                    generate_one_audio,
                    item,
                    out_dir,
                    voice,
                    rate,
                    retries,
                    retry_delay,
                    runner,
                )
                for item in pending
            ]
            for future in as_completed(futures):
                result = future.result()
                generated += result.generated
                failed += result.failed
                if result.completed_item:
                    completed_items.append(result.completed_item)

    return BatchResult(
        selected=selected,
        skipped=skipped,
        generated=generated,
        failed=failed,
        completed_items=completed_items,
    )


def apply_generated_word_audio(deck: dict, items: Iterable[AudioItem]) -> int:
    updates = {item.word_id: item.output_name for item in items if item.word_id and item.audio_field_needs_update}
    updated = 0
    if not updates:
        return 0

    for word in deck.get("words", []):
        word_id = (word.get("id") or "").strip()
        output_name = updates.get(word_id)
        if not output_name:
            continue
        if word.get("audioWord") != output_name:
            word["audioWord"] = output_name
            updated += 1

    return updated


def resolve_out_dir(mode: str, out_dir: Path | None) -> Path:
    if out_dir is not None:
        return out_dir
    return DEFAULT_WORD_OUT_DIR if mode == "word" else DEFAULT_EXAMPLE_OUT_DIR


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Danish word or example audio via edge-tts.",
    )
    parser.add_argument("--deck", type=Path, default=DEFAULT_DECK_PATH)
    parser.add_argument("--mode", choices=("example", "word"), default="example")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--rate", default="+0%")
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Words from deck to scan (0 = all words, default)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum example audio files to attempt after filtering (0 = all)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate audio even when an output file already exists",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=DEFAULT_JOBS,
        help=f"Parallel edge-tts processes to run (default: {DEFAULT_JOBS})",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Retries per failed item (default: {DEFAULT_RETRIES})",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=DEFAULT_RETRY_DELAY,
        help=f"Seconds to wait between retries (default: {DEFAULT_RETRY_DELAY})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    deck = load_deck(args.deck)
    out_dir = resolve_out_dir(args.mode, args.out_dir)
    if args.mode == "word":
        items = list(iter_missing_word_items(deck, out_dir=out_dir, count=args.count))
    else:
        items = list(iter_example_items(deck, count=args.count))
    if args.limit > 0:
        items = items[: args.limit]

    label = "单词" if args.mode == "word" else "例句"
    print(f"共选择 {len(items)} 个{label}，输出目录: {out_dir}，并发: {args.jobs}")
    result = generate_audio(
        items=items,
        out_dir=out_dir,
        voice=args.voice,
        rate=args.rate,
        overwrite=args.overwrite,
        jobs=args.jobs,
        retries=args.retries,
        retry_delay=args.retry_delay,
    )

    if args.mode == "word":
        updated = apply_generated_word_audio(deck, result.completed_items)
        if updated:
            save_deck(args.deck, deck)
            print(f"已回写 deck.json 中的 audioWord: {updated}")

    print(
        "完成: "
        f"选择 {result.selected}, "
        f"跳过 {result.skipped}, "
        f"生成 {result.generated}, "
        f"失败 {result.failed}"
    )
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
