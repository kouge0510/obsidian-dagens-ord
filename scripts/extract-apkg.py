#!/usr/bin/env python3
"""Extract Danish Frequency Deck from Anki .apkg to JSON + audio files."""
# python3 "/home/kouge/Desktop/obsidian addons/obsidian-dagens-ord/scripts/extract-apkg.py" "/home/kouge/Downloads/DDO_Danish_Frequency_Deck_English.apkg" "/home/kouge/Desktop/obsidian addons/obsidian-dagens-ord/data/deck.json"
# it was used to extract the english deck from the anki app
import json
import re
import shutil
import sqlite3
import sys
import zipfile
from pathlib import Path


def parse_pos(summary_html: str) -> str:
    headers = re.findall(r'pos-group-header">([^<]+)', summary_html)
    if not headers:
        return "unknown"
    header = headers[0]
    match = re.search(r"\(([^)]+)\)", header)
    if match:
        pos = match.group(1).lower()
        if "noun" in pos:
            return "noun"
        if "verb" in pos:
            return "verb"
        if "adjective" in pos or "adj" in pos:
            return "adjective"
        if "adverb" in pos:
            return "adverb"
        if "pronoun" in pos:
            return "pronoun"
        if "preposition" in pos:
            return "preposition"
        if "conjunction" in pos:
            return "conjunction"
        if "article" in pos:
            return "article"
        if "symbol" in pos:
            return "symbol"
        return pos.split()[-1]
    return header.split(",")[0].strip()


def parse_ipa(summary_html: str) -> str | None:
    match = re.search(r'ipa-row">\s*(\[[^\]]+\])', summary_html)
    return match.group(1) if match else None


def parse_sounds(html: str) -> list[str]:
    return re.findall(r"\[sound:([^\]]+)\]", html)


def parse_translations(content_html: str) -> list[str]:
    return re.findall(r'<div class="translation"><b>([^<]+)</b>', content_html)


def parse_entry_translations(fields: list[str]) -> list[str]:
    translations = parse_translations(fields[2]) if len(fields) > 2 else []
    if translations:
        return translations
    return parse_translations(fields[3]) if len(fields) > 3 else []


def parse_examples(content_html: str) -> list[str]:
    return re.findall(r'<div class="example">E\.g\., "([^"]+)"', content_html)


def rank_to_cefr(rank: int, total: int) -> str:
    ratio = rank / total
    if ratio <= 0.12:
        return "A1"
    if ratio <= 0.35:
        return "A2"
    if ratio <= 0.65:
        return "B1"
    if ratio <= 0.85:
        return "B2"
    return "C1"


def extract_apkg(apkg_path: Path, output_path: Path, max_audio: int = 2000) -> None:
    root = output_path.parent.parent
    extract_dir = output_path.parent / ".apkg-tmp"
    anki_audio_dir = root / "audio" / "anki"

    with zipfile.ZipFile(apkg_path, "r") as zf:
        zf.extractall(extract_dir)

    media_map: dict[str, str] = json.loads((extract_dir / "media").read_text())
    index_to_name = media_map
    name_to_index = {v: k for k, v in media_map.items()}

    db_path = extract_dir / "collection.anki2"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT flds FROM notes")
    rows = cursor.fetchall()
    conn.close()

    words = []
    needed_audio: set[str] = set()

    for (flds,) in rows:
        fields = flds.split("\x1f")
        if len(fields) < 8:
            continue

        word = fields[0].strip()
        if not word:
            continue

        summary = fields[1]
        content = fields[2]
        rank_str = fields[7].strip()
        try:
            rank = int(rank_str)
        except ValueError:
            rank = len(words) + 1

        translations = parse_entry_translations(fields)
        examples = parse_examples(content)
        sounds = parse_sounds(summary)
        audio_word = sounds[0] if sounds else None

        words.append({
            "id": word,
            "word": word,
            "rank": rank,
            "pos": parse_pos(summary),
            "ipa": parse_ipa(summary),
            "translationEn": translations[0] if translations else "",
            "translationsEn": translations,
            "exampleDa": examples[0] if examples else "",
            "examplesDa": examples,
            "audioWord": audio_word,
        })

    words.sort(key=lambda w: w["rank"])
    total = len(words)

    for w in words:
        w["cefr"] = rank_to_cefr(w["rank"], total)
        w["index"] = w["rank"]

    for w in words[:max_audio]:
        if w.get("audioWord"):
            needed_audio.add(w["audioWord"])

    anki_audio_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for filename in sorted(needed_audio):
        idx = name_to_index.get(filename)
        if idx is None:
            continue
        src = extract_dir / idx
        if not src.exists():
            continue
        dst = anki_audio_dir / filename
        if not dst.exists():
            shutil.copy2(src, dst)
            copied += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"total": total, "words": words}, f, ensure_ascii=False, indent=2)

    print(f"Extracted {total} words to {output_path}")
    print(f"Copied {copied} new audio files to {anki_audio_dir} ({len(needed_audio)} referenced)")


if __name__ == "__main__":
    apkg = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "/home/kouge/Downloads/DDO_Danish_Frequency_Deck_English.apkg"
    )
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
        Path(__file__).parent.parent / "data" / "deck.json"
    )
    extract_apkg(apkg, out)
