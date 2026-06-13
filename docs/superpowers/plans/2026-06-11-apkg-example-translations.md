# APKG Example Translations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `txt`-based example translation import flow with a local extractor that reads the English and Chinese `.apkg` decks, writes all extracted example translations into `data/deck.json`, and renders them in alternating English/Chinese order in the card UI.

**Architecture:** Keep `.apkg` parsing in Python as an offline preprocessing step. Add a new extractor script that reads both decks, indexes notes by `word + rank` with a `word` fallback, and merges `examplesEn` / `examplesZh` into `data/deck.json` while preserving `exampleEn` / `exampleZh` as first-item compatibility fields. Update the Obsidian view to render all aligned translation rows with UI-only placeholder text for missing sides.

**Tech Stack:** Python 3, sqlite3, zipfile, JSON deck data, TypeScript, Obsidian plugin API, existing `unittest`-based Python tests, existing `npm run build` flow

---

## File Structure

### Create

- `scripts/extract-example-translations-from-apkg.py`  
  Read both `.apkg` files, extract example translation arrays, merge them into `data/deck.json`, and print summary counts.

- `tests/test_extract_example_translations_from_apkg.py`  
  Verify extraction helpers, deck backfill behavior, and compatibility-field population.

### Modify

- `src/types.ts`  
  Add `examplesEn?: string[]` and `examplesZh?: string[]` to `WordEntry`.

- `src/view.ts`  
  Replace single-value example translation rendering with alternating multi-row rendering plus legacy fallback behavior.

- `styles.css`  
  Add spacing and placeholder styling for repeated translation rows.

- `README.md`  
  Replace the old `txt` import instructions with the new dual-`.apkg` extraction command and brief behavior notes.

### Keep for backward compatibility

- `scripts/apply-example-translations.py`  
  Leave in place unless a later cleanup explicitly removes it.

## Task 1: Build and test the Python extraction helpers

**Files:**
- Create: `tests/test_extract_example_translations_from_apkg.py`
- Create: `scripts/extract-example-translations-from-apkg.py`

- [ ] **Step 1: Write the failing parser and merge tests**

```python
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "extract-example-translations-from-apkg.py"


def load_script():
    spec = importlib.util.spec_from_file_location(
        "extract_example_translations_from_apkg",
        SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ExtractExampleTranslationsFromApkgTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script()

    def test_merge_translation_lists_sets_array_and_compatibility_fields(self):
        deck = {
            "words": [
                {
                    "id": "jeg",
                    "word": "jeg",
                    "rank": 2,
                    "exampleEn": "",
                    "exampleZh": "",
                }
            ]
        }
        english = {
            ("jeg", "2"): {
                "translations": ["You have to accept me as I am", "The ego is conscious"],
            }
        }
        chinese = {
            ("jeg", "2"): {
                "translations": ["你必须接受我本来的样子"],
            }
        }

        stats = self.script.merge_example_translations(deck, english, chinese)
        word = deck["words"][0]

        self.assertEqual(word["examplesEn"], ["You have to accept me as I am", "The ego is conscious"])
        self.assertEqual(word["examplesZh"], ["你必须接受我本来的样子"])
        self.assertEqual(word["exampleEn"], "You have to accept me as I am")
        self.assertEqual(word["exampleZh"], "你必须接受我本来的样子")
        self.assertEqual(stats.both_present, 1)

    def test_lookup_prefers_word_rank_then_falls_back_to_word(self):
        entries = {
            ("jeg", "2"): {"translations": ["rank match"]},
        }
        fallback_entries = {
            "jeg": {"translations": ["word fallback"]},
        }

        hit = self.script.lookup_entry("jeg", 2, entries, fallback_entries)
        miss = self.script.lookup_entry("mig", 2, entries, fallback_entries)

        self.assertEqual(hit["translations"], ["rank match"])
        self.assertIsNone(miss)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new test file and verify it fails**

Run: `python3 -m unittest tests.test_extract_example_translations_from_apkg -v`  
Expected: `ERROR` because `scripts/extract-example-translations-from-apkg.py` does not exist yet.

- [ ] **Step 3: Write the minimal extraction helpers and merge model**

```python
from __future__ import annotations

import json
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).parent.parent
DEFAULT_DECK_PATH = ROOT / "data" / "deck.json"
DEFAULT_EN_APKG_PATH = Path("/home/kouge/Downloads/DDO_Danish_Frequency_Deck_English.apkg")
DEFAULT_ZH_APKG_PATH = Path("/home/kouge/Downloads/DDO_Danish_Frequency_Deck_Chinese.apkg")


@dataclass
class MergeStats:
    total_words: int = 0
    english_matched: int = 0
    chinese_matched: int = 0
    both_present: int = 0
    one_side_missing: int = 0
    both_missing: int = 0


def rank_key(rank: object) -> str:
    return str(rank or "").strip()


def lookup_entry(
    word: str,
    rank: int | str,
    by_word_rank: dict[tuple[str, str], dict],
    by_word: dict[str, dict],
):
    return by_word_rank.get((word, rank_key(rank))) or by_word.get(word)


def merge_example_translations(
    deck: dict,
    english_by_word_rank: dict[tuple[str, str], dict],
    chinese_by_word_rank: dict[tuple[str, str], dict],
    english_by_word: dict[str, dict] | None = None,
    chinese_by_word: dict[str, dict] | None = None,
) -> MergeStats:
    english_by_word = english_by_word or {}
    chinese_by_word = chinese_by_word or {}
    stats = MergeStats(total_words=len(deck.get("words", [])))

    for word in deck.get("words", []):
        key_word = (word.get("word") or word.get("id") or "").strip()
        key_rank = word.get("rank") or word.get("index") or ""
        en = lookup_entry(key_word, key_rank, english_by_word_rank, english_by_word)
        zh = lookup_entry(key_word, key_rank, chinese_by_word_rank, chinese_by_word)

        examples_en = [item for item in (en or {}).get("translations", []) if item]
        examples_zh = [item for item in (zh or {}).get("translations", []) if item]

        word["examplesEn"] = examples_en
        word["examplesZh"] = examples_zh
        word["exampleEn"] = examples_en[0] if examples_en else ""
        word["exampleZh"] = examples_zh[0] if examples_zh else ""

        if examples_en:
            stats.english_matched += 1
        if examples_zh:
            stats.chinese_matched += 1
        if examples_en and examples_zh:
            stats.both_present += 1
        elif examples_en or examples_zh:
            stats.one_side_missing += 1
        else:
            stats.both_missing += 1

    return stats
```

- [ ] **Step 4: Run the test file and verify it passes**

Run: `python3 -m unittest tests.test_extract_example_translations_from_apkg -v`  
Expected: both tests `ok`.

- [ ] **Step 5: Expand tests for parsing extracted note data**

```python
    def test_build_indexes_keeps_rank_and_word_fallback(self):
        note_rows = [
            {
                "word": "jeg",
                "rank": "2",
                "translations": ["english first", "english second"],
            },
            {
                "word": "mig",
                "rank": "",
                "translations": ["fallback only"],
            },
        ]

        by_word_rank, by_word = self.script.build_indexes(note_rows)

        self.assertEqual(by_word_rank[("jeg", "2")]["translations"], ["english first", "english second"])
        self.assertEqual(by_word["mig"]["translations"], ["fallback only"])
```

- [ ] **Step 6: Implement the tested index-building helper**

```python
def build_indexes(rows: list[dict]) -> tuple[dict[tuple[str, str], dict], dict[str, dict]]:
    by_word_rank: dict[tuple[str, str], dict] = {}
    by_word: dict[str, dict] = {}

    for row in rows:
        word = (row.get("word") or "").strip()
        rank = rank_key(row.get("rank"))
        if not word:
            continue
        if word not in by_word:
            by_word[word] = row
        if rank:
            by_word_rank[(word, rank)] = row

    return by_word_rank, by_word
```

- [ ] **Step 7: Run both extractor-related test files**

Run: `python3 -m unittest tests.test_extract_apkg tests.test_extract_example_translations_from_apkg -v`  
Expected: all tests pass.

## Task 2: Implement `.apkg` note loading and deck write-back

**Files:**
- Modify: `scripts/extract-example-translations-from-apkg.py`
- Test: `tests/test_extract_example_translations_from_apkg.py`

- [ ] **Step 1: Add a failing integration-style unit test for writing the deck**

```python
    def test_write_translations_updates_existing_deck_file(self):
        deck = {
            "total": 1,
            "words": [
                {"word": "jeg", "id": "jeg", "rank": 2, "exampleEn": "", "exampleZh": ""}
            ],
        }
        english = {("jeg", "2"): {"translations": ["I am accepted"]}}
        chinese = {("jeg", "2"): {"translations": ["我被接受"]}}

        with self.script.temp_json_file(deck) as deck_path:
            stats = self.script.write_translations_to_deck(deck_path, english, chinese)
            updated = json.loads(deck_path.read_text(encoding="utf-8"))

        self.assertEqual(updated["words"][0]["examplesEn"], ["I am accepted"])
        self.assertEqual(updated["words"][0]["examplesZh"], ["我被接受"])
        self.assertEqual(stats.total_words, 1)
```

- [ ] **Step 2: Run the test file and verify it fails**

Run: `python3 -m unittest tests.test_extract_example_translations_from_apkg -v`  
Expected: `AttributeError` for `temp_json_file` or `write_translations_to_deck`.

- [ ] **Step 3: Implement extraction from `.apkg` and deck persistence**

```python
def load_note_rows(apkg_path: Path) -> list[dict]:
    if not apkg_path.exists():
        raise FileNotFoundError(f"APKG not found: {apkg_path}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        extract_dir = Path(tmp_dir)
        with zipfile.ZipFile(apkg_path, "r") as zf:
            zf.extractall(extract_dir)

        db_path = extract_dir / "collection.anki2"
        if not db_path.exists():
            raise FileNotFoundError(f"Anki database not found in: {apkg_path}")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT flds FROM notes")
        rows = cursor.fetchall()
        conn.close()

    parsed_rows: list[dict] = []
    for (flds,) in rows:
        fields = flds.split("\x1f")
        if len(fields) < 8:
            continue
        parsed_rows.append(
            {
                "word": fields[0].strip(),
                "rank": fields[7].strip(),
                "translations": parse_entry_example_translations(fields),
            }
        )
    return parsed_rows


def write_translations_to_deck(
    deck_path: Path,
    english_by_word_rank: dict[tuple[str, str], dict],
    chinese_by_word_rank: dict[tuple[str, str], dict],
    english_by_word: dict[str, dict] | None = None,
    chinese_by_word: dict[str, dict] | None = None,
) -> MergeStats:
    deck = json.loads(deck_path.read_text(encoding="utf-8"))
    stats = merge_example_translations(
        deck,
        english_by_word_rank,
        chinese_by_word_rank,
        english_by_word,
        chinese_by_word,
    )
    deck_path.write_text(json.dumps(deck, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats
```

- [ ] **Step 4: Add a parser helper for example translation extraction**

```python
import re


def parse_entry_example_translations(fields: list[str]) -> list[str]:
    content_candidates = [field for field in fields[2:4] if field]
    for content in content_candidates:
        matches = re.findall(r'<div class="example-translation">([^<]+)</div>', content)
        cleaned = [match.strip() for match in matches if match.strip()]
        if cleaned:
            return cleaned
    return []
```

- [ ] **Step 5: Adjust the parser helper if the real deck structure differs**

Use the same step to switch the regex once a sample `.apkg` inspection shows the actual translation markup. Keep the return contract unchanged:

```python
def parse_entry_example_translations(fields: list[str]) -> list[str]:
    html_fields = [field for field in fields[2:4] if field]
    patterns = [
        r'<div class="example-translation">([^<]+)</div>',
        r'<div class="translation example">([^<]+)</div>',
        r'<span class="example-translation">([^<]+)</span>',
    ]
    for html in html_fields:
        for pattern in patterns:
            matches = [item.strip() for item in re.findall(pattern, html) if item.strip()]
            if matches:
                return matches
    return []
```

- [ ] **Step 6: Add CLI entrypoint and summary output**

```python
import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract example translations from English and Chinese APKG decks")
    parser.add_argument("--deck", type=Path, default=DEFAULT_DECK_PATH)
    parser.add_argument("--english-apkg", type=Path, default=DEFAULT_EN_APKG_PATH)
    parser.add_argument("--chinese-apkg", type=Path, default=DEFAULT_ZH_APKG_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    english_rows = load_note_rows(args.english_apkg)
    chinese_rows = load_note_rows(args.chinese_apkg)
    english_by_word_rank, english_by_word = build_indexes(english_rows)
    chinese_by_word_rank, chinese_by_word = build_indexes(chinese_rows)
    stats = write_translations_to_deck(
        args.deck,
        english_by_word_rank,
        chinese_by_word_rank,
        english_by_word,
        chinese_by_word,
    )
    print(f"Total words processed: {stats.total_words}")
    print(f"English matches: {stats.english_matched}")
    print(f"Chinese matches: {stats.chinese_matched}")
    print(f"Both present: {stats.both_present}")
    print(f"One side missing: {stats.one_side_missing}")
    print(f"Both missing: {stats.both_missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Run the extractor unit tests again**

Run: `python3 -m unittest tests.test_extract_example_translations_from_apkg -v`  
Expected: all tests pass.

- [ ] **Step 8: Run the extractor script against the real decks**

Run: `python3 scripts/extract-example-translations-from-apkg.py`  
Expected: summary output with non-zero English and Chinese matches, and `data/deck.json` updated with `examplesEn` / `examplesZh`.

## Task 3: Add front-end support for translation arrays

**Files:**
- Modify: `src/types.ts`
- Modify: `src/view.ts`
- Modify: `styles.css`

- [ ] **Step 1: Add a failing TypeScript type and rendering change**

Update `src/types.ts`:

```ts
export interface WordEntry {
	id: string;
	word: string;
	rank: number;
	pos: string;
	ipa: string | null;
	translationEn: string;
	translationsEn: string[];
	exampleDa: string;
	exampleZh?: string;
	exampleEn?: string;
	examplesZh?: string[];
	examplesEn?: string[];
	examplesDa: string[];
	cefr: string;
	index: number;
	audioWord?: string | null;
}
```

Then prepare `src/view.ts` to call a not-yet-defined helper:

```ts
const translationPairs = this.buildExampleTranslationRows(word);
if (translationPairs.length > 0) {
	const translations = box.createDiv({ cls: "do-example-translations" });
	for (const row of translationPairs) {
		translations.createEl("p", {
			cls: row.lang === "en" ? "do-example-en" : "do-example-zh",
			text: row.text,
		});
	}
}
```

- [ ] **Step 2: Run the build and verify it fails**

Run: `npm run build`  
Expected: TypeScript error that `buildExampleTranslationRows` does not exist.

- [ ] **Step 3: Implement alternating translation-row construction with legacy fallback**

Add this helper inside `DagensOrdView`:

```ts
private buildExampleTranslationRows(
	word: WordEntry,
): Array<{ lang: "en" | "zh"; text: string }> {
	const examplesEn = (word.examplesEn ?? []).filter(Boolean);
	const examplesZh = (word.examplesZh ?? []).filter(Boolean);

	if (examplesEn.length > 0 || examplesZh.length > 0) {
		const rows: Array<{ lang: "en" | "zh"; text: string }> = [];
		const total = Math.max(examplesEn.length, examplesZh.length);
		for (let index = 0; index < total; index += 1) {
			rows.push({
				lang: "en",
				text: examplesEn[index] ?? "[待补充英文翻译]",
			});
			rows.push({
				lang: "zh",
				text: examplesZh[index] ?? "[待补充中文翻译]",
			});
		}
		return rows;
	}

	const rows: Array<{ lang: "en" | "zh"; text: string }> = [];
	if (word.exampleEn) {
		rows.push({ lang: "en", text: word.exampleEn });
	}
	if (word.exampleZh) {
		rows.push({ lang: "zh", text: word.exampleZh });
	}
	return rows;
}
```

- [ ] **Step 4: Replace the old single-line rendering block**

In `renderExample`, swap this:

```ts
if (word.exampleZh || word.exampleEn) {
	const translations = box.createDiv({ cls: "do-example-translations" });
	if (word.exampleZh) {
		translations.createEl("p", {
			cls: "do-example-zh",
			text: word.exampleZh,
		});
	}
	if (word.exampleEn) {
		translations.createEl("p", {
			cls: "do-example-en",
			text: word.exampleEn,
		});
	}
}
```

for this:

```ts
const translationRows = this.buildExampleTranslationRows(word);
if (translationRows.length > 0) {
	const translations = box.createDiv({ cls: "do-example-translations" });
	for (const row of translationRows) {
		translations.createEl("p", {
			cls: row.lang === "en" ? "do-example-en" : "do-example-zh",
			text: row.text,
		});
	}
}
```

- [ ] **Step 5: Add row spacing without changing the overall card design**

Update `styles.css`:

```css
.do-example-translations {
	margin-top: 10px;
	padding-top: 10px;
	border-top: 1px solid var(--background-modifier-border);
}

.do-example-zh,
.do-example-en {
	margin: 0;
	line-height: 1.5;
}

.do-example-en + .do-example-zh {
	margin-top: 2px;
}

.do-example-zh + .do-example-en {
	margin-top: 8px;
}
```

- [ ] **Step 6: Run the build and verify it passes**

Run: `npm run build`  
Expected: build completes successfully and updates `main.js`.

## Task 4: Update docs and verify the end-to-end flow

**Files:**
- Modify: `README.md`
- Modify: `data/deck.json`

- [ ] **Step 1: Replace the old translation import instructions**

Update the README section so it looks like this:

```md
## 导入例句翻译

从两个 Anki `.apkg` 直接提取例句英文和中文翻译，并写入 `data/deck.json`：

```bash
python3 scripts/extract-example-translations-from-apkg.py
npm run build
```

脚本会保留全部提取到的例句翻译，写入：

- `examplesEn`
- `examplesZh`
- `exampleEn`
- `exampleZh`

插件会在丹麦语例句下方按“英文 -> 中文 -> 英文 -> 中文”的顺序显示翻译；如果某一侧缺失，会显示待补充占位文本。
```

- [ ] **Step 2: Run Python tests for the affected scripts**

Run: `python3 -m unittest tests.test_extract_apkg tests.test_backfill_definition_translations tests.test_extract_example_translations_from_apkg -v`  
Expected: all tests pass.

- [ ] **Step 3: Build the plugin after refreshing `data/deck.json`**

Run these commands in order:

```bash
python3 scripts/extract-example-translations-from-apkg.py
npm run build
```

Expected:
- extractor prints summary counts
- `data/deck.json` contains `examplesEn` and `examplesZh`
- TypeScript build succeeds

- [ ] **Step 4: Spot-check the resulting deck data**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path

deck = json.loads(Path("data/deck.json").read_text(encoding="utf-8"))
for word in deck["words"][:5]:
    print(word["word"])
    print("examplesEn:", word.get("examplesEn", [])[:2])
    print("examplesZh:", word.get("examplesZh", [])[:2])
    print("exampleEn:", word.get("exampleEn", ""))
    print("exampleZh:", word.get("exampleZh", ""))
    print("---")
PY
```

Expected: extracted arrays are present where translations were found, and compatibility fields mirror the first entries.

- [ ] **Step 5: Review the rendered card manually in Obsidian**

Check:
- the Danish sentence still appears first
- translations render in alternating English/Chinese order
- missing-side placeholders only appear when one language is absent
- legacy words without arrays still render without UI errors

## Self-Review

- Spec coverage check: the plan covers the new extractor script, persisted arrays, compatibility fields, alternating UI order, placeholder-only rendering, README updates, and verification.
- Placeholder scan: the plan avoids `TODO`, `TBD`, and vague “handle later” steps; the only conditional parser adjustment is explicitly scoped to observed `.apkg` markup while preserving the helper contract.
- Type consistency: the plan consistently uses `examplesEn`, `examplesZh`, `exampleEn`, `exampleZh`, `merge_example_translations`, and `buildExampleTranslationRows`.
