# APKG Example Translation Design

**Goal:** Replace the current `txt`-based example translation import with a local extraction flow that reads English and Chinese translations from the two Anki `.apkg` decks, stores the extracted results in `data/deck.json`, and renders them in the card as alternating English/Chinese lines.

## Context

The plugin already has:

- `scripts/extract-apkg.py` for extracting the main deck data from the English `.apkg`
- `data/deck.json` as the local persisted deck data consumed by the plugin
- `src/view.ts` rendering logic that displays `exampleDa`, `exampleEn`, and `exampleZh`

The current translation workflow depends on `scripts/apply-example-translations.py`, which reads `data/translated-examples-combined.txt` and writes `exampleEn` and `exampleZh` back into `data/deck.json`.

The new workflow should remove the dependency on the `txt` source and instead derive translation data directly from:

- `/home/kouge/Downloads/DDO_Danish_Frequency_Deck_English.apkg`
- `/home/kouge/Downloads/DDO_Danish_Frequency_Deck_Chinese.apkg`

## Requirements

### Functional requirements

1. Add a script that reads both `.apkg` files and extracts example translations locally.
2. Persist the extracted results back into `data/deck.json`.
3. Preserve all extracted translations instead of truncating to a single translation.
4. Keep compatibility with the current single-value fields by continuing to populate:
   - `exampleEn`
   - `exampleZh`
5. Add multi-value fields for the full extracted example translation lists:
   - `examplesEn`
   - `examplesZh`
6. Render the translation block in this visual order:
   - English 1
   - Chinese 1
   - English 2
   - Chinese 2
   - ...
7. If one side is missing for a given translation index, render a placeholder in the UI:
   - `[待补充英文翻译]`
   - `[待补充中文翻译]`
8. Do not store placeholder strings in `data/deck.json`; placeholders are a view concern only.

### Non-functional requirements

1. Keep the plugin usable with existing `deck.json` files that only have `exampleEn` and `exampleZh`.
2. Prefer deterministic matching rules that minimize accidental cross-word mismatches.
3. Keep the extraction as an offline, local preprocessing step rather than runtime `.apkg` parsing inside the Obsidian plugin.

## Architecture

The solution is split into two responsibilities:

1. **Extraction step**: a Python script reads the English and Chinese `.apkg` decks, builds translation indexes, and writes the merged example translation arrays into `data/deck.json`.
2. **Rendering step**: the Obsidian view reads `examplesEn` and `examplesZh` when available and renders them as alternating English/Chinese lines, while falling back to the legacy single-value fields when the arrays are absent.

This keeps deck parsing and sqlite access out of the runtime plugin code, preserves the existing local-json workflow, and limits front-end changes to typed rendering updates.

## Data Model

Each `WordEntry` in `data/deck.json` should keep the existing fields and gain two optional array fields:

```json
{
  "exampleDa": "Du bliver nødt til at acceptere mig, som jeg er",
  "examplesDa": [
    "Du bliver nødt til at acceptere mig, som jeg er"
  ],
  "exampleEn": "You have to accept me as I am",
  "examplesEn": [
    "You have to accept me as I am",
    "..."
  ],
  "exampleZh": "你必须接受我本来的样子",
  "examplesZh": [
    "你必须接受我本来的样子",
    "..."
  ]
}
```

Compatibility rules:

- `exampleEn = examplesEn[0] || ""`
- `exampleZh = examplesZh[0] || ""`
- If arrays are absent, the UI falls back to the legacy single-value fields.

## Matching Strategy

`data/deck.json` remains the source of truth for the output order and the set of words to enrich.

The translation extraction script should build per-deck lookup indexes with these match priorities:

1. Exact match on `word + rank`
2. Fallback match on `word`

`word + rank` is the preferred key because it is already present in `deck.json` and provides a better guard against accidental collisions than `word` alone.

The script should only fall back to `word` matching when the `word + rank` lookup fails.

## Extraction Rules

For each matched note in each `.apkg`, the script should extract:

- the Danish headword
- the rank
- the Danish example list already present in the source note
- the language-specific translation list for examples

The script does not need to rewrite `examplesDa`; it may rely on the existing Danish examples already present in `data/deck.json`, unless the implementation discovers that note-level indexing is necessary to align translations safely.

The output for each word should be:

- `examplesEn`: all extracted English example translations
- `examplesZh`: all extracted Chinese example translations
- `exampleEn`: first English translation or empty string
- `exampleZh`: first Chinese translation or empty string

## Alignment Rules

English and Chinese example translations are aligned by array index, not by text similarity.

That means:

- English item 1 pairs with Chinese item 1
- English item 2 pairs with Chinese item 2
- and so on

If one side has fewer entries:

- keep the available entries in the stored arrays
- render a placeholder only in the UI for the missing side at that index

This avoids polluting persisted data with synthetic placeholders and keeps the raw extracted result intact.

## UI Rendering Rules

The example translation block in `src/view.ts` should change from "render at most one Chinese line and one English line" to "render all available aligned translation rows".

Rendering behavior:

1. If `examplesEn` or `examplesZh` is present, compute `max(len(examplesEn), len(examplesZh))`.
2. For each index:
   - render the English line first
   - render the Chinese line second
3. For missing entries at a given index:
   - render `[待补充英文翻译]` for a missing English line
   - render `[待补充中文翻译]` for a missing Chinese line
4. If neither array field exists, fall back to the legacy single-value display using `exampleEn` and `exampleZh`.

Styling should preserve the current card look while allowing multiple translation rows with readable spacing.

## File-Level Changes

### New

- `scripts/extract-example-translations-from-apkg.py`

### Modify

- `src/types.ts`
- `src/view.ts`
- `styles.css`
- `README.md`

### Possibly de-emphasize or leave in place for backward compatibility

- `scripts/apply-example-translations.py`

The old script does not need to be deleted immediately, but the README should stop presenting it as the primary path for importing example translations.

## Error Handling

The extraction script should:

- fail clearly if either `.apkg` path is missing
- fail clearly if `collection.anki2` cannot be found after extraction
- print summary counts for:
  - total words processed
  - words matched in English deck
  - words matched in Chinese deck
  - words with both sides present
  - words missing one or both sides

The UI should not fail if translation arrays are missing or empty.

## Testing and Verification

The implementation should include targeted verification for both Python extraction logic and TypeScript rendering compatibility.

Verification goals:

1. Confirm the new extraction script can parse both `.apkg` files and write back to `data/deck.json`.
2. Confirm `exampleEn` / `exampleZh` remain populated from the first extracted translation.
3. Confirm `examplesEn` / `examplesZh` retain all extracted translations.
4. Confirm the UI renders alternating English/Chinese rows in the requested order.
5. Confirm placeholder text appears only when one side is missing.
6. Confirm older `deck.json` data without the new arrays still renders without breaking.

## Out of Scope

- Runtime `.apkg` parsing inside the Obsidian plugin
- Cloud APIs or external translation services
- Changing the daily word selection logic
- Redesigning the entire card layout beyond the required translation block updates
