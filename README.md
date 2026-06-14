# Dagens Ord — Obsidian Daily Danish Plugin

[中文版 / Chinese](README-CN.md)

An Obsidian plugin built on the Anki Danish frequency deck (DDO Danish Frequency Deck). The UI follows a “word of the day” card layout; example sentence audio is generated locally with edge-tts.

![Dagens Ord plugin screenshot](docs/screenshot.png)

> **Example sentence translations (in progress):** 1282 English and 1 Chinese out of ~13,000 unique Danish example sentences.

## Features

- Daily word rotation (deterministic selection by date)
- Deck navigation (← →), starred and mastered markers
- **Today** button jumps back to the current day’s word
- **Word audio**: built-in Danish MP3 from the Anki deck, ready out of the box
- **Example audio**: batch-generated locally via `edge-tts` (no API key required)
- **CEFR filter**: toggle A1–C2 levels individually in settings
- Dark theme aligned with Obsidian’s default dark UI
- Progress saved locally

## Installation

1. Copy the entire `obsidian-dagens-ord` folder (including `audio/anki/`) into `.obsidian/plugins/`
2. Enable **Dagens Ord** under Settings → Community plugins

## Usage

- Click the ![languages](docs/ribbon-icon.png) icon in the ribbon, or run **Open daily Danish** from the command palette
- Word play button: plays built-in Anki pronunciation
- Example play button: requires running the batch generation script first (see below)

## Developer notes

### Batch-generate example audio (local edge-tts)

Verify that `edge-tts` is installed and works on your machine:

```bash
edge-tts --voice da-DK-ChristelNeural --text "Godmorgen, hvordan har du det?" --write-media "audio/test_da.mp3"
```

Then from the plugin directory:

```bash
python3 scripts/edge-tts-examples.py --jobs 4 --retries 3
```

By default the script reads the full `data/deck.json` and generates `audio/generated/ex-<word-id>.mp3` for every entry with an example sentence. Existing files are skipped (resume-friendly); use `--overwrite` to regenerate. Default concurrency is `--jobs 4`; on a stable network you can raise it to `--jobs 8` or higher. If you hit `NoAudioReceived`, lower `--jobs` or increase `--retries`.

### Import Chinese word meanings

Backfill word-level Chinese glosses from a Chinese Anki `.apkg` into `data/deck.json`:

```bash
npm run extract:zh
npm run build
```

The script writes:

- `translationZh`
- `translationsZh`

The plugin shows English and Chinese glosses under each word. These `.apkg` files do not include full EN/ZH sentence translations for Danish examples, so the example area shows Danish only.

### Development

```bash
npm install
npm run extract   # Re-export deck from .apkg
npm run build     # Build main.js
```

### Deck source

`DDO_Danish_Frequency_Deck_English.apkg` — `data/deck.json` currently holds 4442 high-frequency Danish words, 4304 with example sentences. The default daily pool uses all 4442 words; you can lower the count or filter by CEFR level in settings.

## Acknowledgements

This plugin was inspired by [ankidkdeck v2.0](https://github.com/iskoldt-X/ankidkdeck/releases/tag/v2.0) ([iskoldt-X/ankidkdeck](https://github.com/iskoldt-X/ankidkdeck)).

Thanks to [Yifan Huang](https://github.com/Ploverrrr) for their help.
