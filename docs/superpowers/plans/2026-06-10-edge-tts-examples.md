# Edge TTS Examples Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate local Danish TTS audio for every word example using the installed `edge-tts` command.

**Architecture:** Add a focused Python batch script that reads `data/deck.json`, selects words with `exampleDa`, and writes `audio/generated/ex-<id>.mp3`. Keep playback compatibility by matching the cache keys already used by the plugin.

**Tech Stack:** Python standard library, external `edge-tts` CLI, existing Obsidian TypeScript plugin.

---

### Task 1: Script Unit Tests

**Files:**
- Create: `tests/test_edge_tts_examples.py`
- Create: `scripts/edge-tts-examples.py`

- [ ] Write failing tests that import `scripts/edge-tts-examples.py` with `importlib.util.spec_from_file_location`.
- [ ] Cover selecting only words with `exampleDa`, defaulting to all words, skipping existing files, and building `edge-tts --voice da-DK-ChristelNeural --text ... --write-media ...`.
- [ ] Run `python3 -m unittest tests/test_edge_tts_examples.py -v` and confirm failure because the script is not implemented.

### Task 2: Edge TTS Batch Script

**Files:**
- Create: `scripts/edge-tts-examples.py`

- [ ] Implement `load_deck`, `iter_example_items`, `audio_exists`, `build_edge_tts_command`, `generate_audio`, and CLI parsing.
- [ ] Defaults: `--voice da-DK-ChristelNeural`, `--count 0` for all words, `--out-dir audio/generated`, skip existing files, `--overwrite` opt-in.
- [ ] Continue after per-item failures and print totals for selected, skipped, generated, and failed.
- [ ] Run unit tests and confirm pass.

### Task 3: Documentation and Plugin Instructions

**Files:**
- Modify: `README.md`
- Modify: `src/settings.ts`

- [ ] Replace Gemini batch instructions with local `edge-tts` instructions.
- [ ] Mention that `deck.json` contains 4442 entries, the default plugin learning range is 2000, and the new script generates examples for all words that have examples.
- [ ] Run `npm run build` to verify TypeScript and bundling still pass.
