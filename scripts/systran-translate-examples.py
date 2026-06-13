#!/usr/bin/env python3
"""Translate Danish examples in deck.json via SYSTRAN web UI (logged-in browser)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, NamedTuple
from urllib.parse import urlencode, urlparse

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


ROOT = Path(__file__).parent.parent
DEFAULT_DECK_PATH = ROOT / "data" / "deck.json"
DEFAULT_CACHE_PATH = ROOT / "data" / ".systran-example-cache.json"
DEFAULT_BROWSER_PROFILE = ROOT / "data" / ".systran-browser-profile"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
DEFAULT_SOURCE = "da"
DEFAULT_TARGETS = ("en", "zh")
TRANSLATE_HOSTS = ("translate.systran.net", "trs.systran.net")
TRANSLATE_PATH_HINTS = ("/translationTools/text", "/translate")
WEB_TRANSLATE_JSON = "/node/translate/json"
BLANK_WAIT_MS = 20_000
MAX_SUBMIT_RETRIES = 3


class TranslateStats(NamedTuple):
    unique_texts: int
    translated_en: int
    translated_zh: int
    words_updated: int
    skipped: int


class BrowserTranslateError(RuntimeError):
    pass


def normalize_examples(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [item.strip() for item in raw if isinstance(item, str) and item.strip()]


def is_sentence(text: str) -> bool:
    return len(text.split()) >= 3


def is_word_gloss_translation(da: str, translated: str, glosses: list[str]) -> bool:
    if not da or not translated or not glosses:
        return False
    if not is_sentence(da):
        return False
    return translated in glosses


def example_pair_needs_translation(da: str, en: str, zh: str, word: dict) -> bool:
    if not da:
        return False
    if not en or not zh:
        return True
    glosses_en = normalize_examples(word.get("translationsEn"))
    glosses_zh = normalize_examples(word.get("translationsZh"))
    if is_word_gloss_translation(da, en, glosses_en):
        return True
    if is_word_gloss_translation(da, zh, glosses_zh):
        return True
    return False


def example_needs_translation(word: dict, only_missing: bool) -> bool:
    example_da = (word.get("exampleDa") or "").strip()
    examples_da = normalize_examples(word.get("examplesDa"))
    if not example_da and not examples_da:
        return False
    if not only_missing:
        return True

    example_en = (word.get("exampleEn") or "").strip()
    example_zh = (word.get("exampleZh") or "").strip()
    examples_en = normalize_examples(word.get("examplesEn"))
    examples_zh = normalize_examples(word.get("examplesZh"))

    if example_da and example_pair_needs_translation(example_da, example_en, example_zh, word):
        return True
    for index, text in enumerate(examples_da):
        en = examples_en[index] if index < len(examples_en) else ""
        zh = examples_zh[index] if index < len(examples_zh) else ""
        if example_pair_needs_translation(text, en, zh, word):
            return True
    return False


def collect_texts(deck: dict, only_missing: bool) -> list[str]:
    texts: set[str] = set()
    for word in deck.get("words", []):
        if not example_needs_translation(word, only_missing):
            continue
        example_da = (word.get("exampleDa") or "").strip()
        if example_da:
            texts.add(example_da)
        for item in normalize_examples(word.get("examplesDa")):
            texts.add(item)
    return sorted(texts)


def load_cache(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {"en": {}, "zh": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "en": {k: v for k, v in (data.get("en") or {}).items() if k and v},
        "zh": {k: v for k, v in (data.get("zh") or {}).items() if k and v},
    }


def save_cache(path: Path, cache: dict[str, dict[str, str]]) -> None:
    path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def extract_web_translation(output: object) -> str | None:
    if isinstance(output, str) and output.strip():
        return output.strip()
    if not isinstance(output, dict):
        return None

    documents = output.get("documents")
    if isinstance(documents, list):
        for document in documents:
            if not isinstance(document, dict):
                continue
            for unit in document.get("trans_units") or []:
                if not isinstance(unit, dict):
                    continue
                for sentence in unit.get("sentences") or []:
                    if not isinstance(sentence, dict):
                        continue
                    for alt in sentence.get("alt_transes") or []:
                        if not isinstance(alt, dict):
                            continue
                        target = alt.get("target")
                        if isinstance(target, dict):
                            text = (target.get("text") or "").strip()
                            if text:
                                return text
    return None


def parse_translation_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise BrowserTranslateError(f"Unexpected translation payload: {payload!r}")

    if payload.get("error"):
        error = payload["error"]
        if isinstance(error, dict):
            message = error.get("message") or str(error)
        else:
            message = str(error)
        raise BrowserTranslateError(message)

    outputs = payload.get("outputs")
    if isinstance(outputs, list) and outputs:
        first = outputs[0]
        if isinstance(first, dict):
            if first.get("error"):
                raise BrowserTranslateError(str(first["error"]))
            web_text = extract_web_translation(first.get("output"))
            if web_text:
                return web_text
            output = first.get("output")
            if isinstance(output, str) and output.strip():
                return output.strip()
        if isinstance(first, str) and first.strip():
            return first.strip()

    for key in ("output", "translation", "translatedText", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        web_text = extract_web_translation(value)
        if web_text:
            return web_text

    raise BrowserTranslateError(f"No translation found in payload: {json.dumps(payload)[:300]}")


def build_translate_page_url(source: str, target: str) -> str:
    query = urlencode({"source": source, "target": target})
    return f"https://translate.systran.net/en/translationTools/text?{query}"


def is_translate_page(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.hostname not in TRANSLATE_HOSTS:
        return False
    return any(hint in parsed.path for hint in TRANSLATE_PATH_HINTS)


def pick_translate_page(context: BrowserContext, preferred_url: str | None = None) -> Page:
    pages = [page for context in [context] for page in context.pages if not page.is_closed()]
    if preferred_url:
        for page in pages:
            if preferred_url.rstrip("/") in page.url:
                return page
    for page in pages:
        if is_translate_page(page.url):
            return page
    for page in pages:
        host = urlparse(page.url).hostname or ""
        if any(host.endswith(item) for item in TRANSLATE_HOSTS):
            return page
    if pages:
        return pages[0]
    return context.new_page()


def connect_browser(playwright: Playwright, cdp_url: str) -> Browser:
    try:
        return playwright.chromium.connect_over_cdp(cdp_url)
    except Exception as exc:
        raise SystemExit(
            "Could not connect to Chrome via CDP.\n"
            "Start Chrome with remote debugging (user-data-dir is required on recent Chrome):\n"
            "  google-chrome --remote-debugging-port=9222 \\\n"
            "    --user-data-dir=\"$HOME/.config/google-chrome-systran-debug\"\n"
            "Then open https://translate.systran.net , sign in, and run this script again.\n"
            "Or skip CDP and use the built-in browser window instead:\n"
            "  python3 scripts/systran-translate-examples.py --launch-browser --probe\n"
            f"CDP URL tried: {cdp_url}\n"
            f"Error: {exc}"
        ) from exc


def page_has_translate_textarea(page: Page) -> bool:
    if "auth.systran.net" in page.url:
        return False
    textarea = page.locator("textarea")
    try:
        return textarea.count() > 0 and textarea.first.is_visible()
    except PlaywrightError:
        return False


def wait_for_translate_ui(
    page: Page,
    timeout_ms: int,
) -> None:
    if "auth.systran.net" in page.url:
        raise BrowserTranslateError(
            "SYSTRAN login page is still open. Sign in in the browser window, then rerun."
        )
    page.wait_for_selector("textarea", state="visible", timeout=timeout_ms)
    page.wait_for_timeout(500)


def is_translate_json_response(url: str) -> bool:
    return url.endswith(WEB_TRANSLATE_JSON)


def submit_translation(page: Page, text: str) -> str:
    textarea = page.locator("textarea").first
    textarea.click()
    with page.expect_response(
        lambda response: is_translate_json_response(response.url) and response.request.method == "POST",
        timeout=BLANK_WAIT_MS,
    ) as response_info:
        textarea.fill(text)
        page.keyboard.press("Control+Enter")

    response = response_info.value
    if not response.ok:
        raise BrowserTranslateError(
            f"Translation request failed: HTTP {response.status} {response.text()[:300]}"
        )
    return parse_translation_payload(response.json())


def clear_translate_input(page: Page) -> None:
    """Clear the source box in-place (like Backspace), without reloading the page."""
    textarea = page.locator("textarea").first
    textarea.click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.wait_for_timeout(100)


class BrowserTranslator:
    def __init__(
        self,
        context: BrowserContext,
        page: Page,
        *,
        source: str,
        timeout_ms: int,
    ) -> None:
        self.context = context
        self.page = page
        self.source = source
        self.timeout_ms = timeout_ms
        self._active_pair: tuple[str, str] | None = None

    def ensure_language_pair(self, source: str, target: str) -> None:
        pair = (source, target)
        if self._active_pair == pair and page_has_translate_textarea(self.page):
            return

        self.page.goto(
            build_translate_page_url(source, target),
            wait_until="domcontentloaded",
            timeout=self.timeout_ms,
        )
        wait_for_translate_ui(self.page, self.timeout_ms)
        self._active_pair = pair

    def translate_on_current_page(self, text: str) -> str:
        if not self._active_pair:
            raise BrowserTranslateError("No active translate language pair loaded")
        _, target = self._active_pair
        last_error: Exception | None = None

        for attempt in range(MAX_SUBMIT_RETRIES):
            try:
                if not page_has_translate_textarea(self.page):
                    raise BrowserTranslateError("Translate textarea not found")
                result = submit_translation(self.page, text)
                if result.strip():
                    clear_translate_input(self.page)
                    return result
                last_error = BrowserTranslateError("Translation result was blank")
                clear_translate_input(self.page)
            except (BrowserTranslateError, PlaywrightTimeoutError, PlaywrightError) as exc:
                last_error = exc
                clear_translate_input(self.page)

        raise BrowserTranslateError(
            f"Translation failed for target={target} after {MAX_SUBMIT_RETRIES} attempts"
        ) from last_error

    def translate_once(self, text: str, *, source: str, target: str) -> str:
        self.ensure_language_pair(source, target)
        return self.translate_on_current_page(text)

    @classmethod
    def connect_cdp(
        cls,
        playwright: Playwright,
        *,
        cdp_url: str,
        source: str,
        timeout_ms: int,
        page_url: str | None,
    ) -> BrowserTranslator:
        browser = connect_browser(playwright, cdp_url)
        if not browser.contexts:
            raise SystemExit("Connected browser has no contexts.")
        context = browser.contexts[0]
        page = pick_translate_page(context, page_url)
        return cls._from_context(context, page, source=source, timeout_ms=timeout_ms)

    @classmethod
    def connect_launch(
        cls,
        playwright: Playwright,
        *,
        profile_dir: Path,
        source: str,
        timeout_ms: int,
        page_url: str | None,
    ) -> tuple[BrowserTranslator, BrowserContext]:
        profile_dir.mkdir(parents=True, exist_ok=True)
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = pick_translate_page(context, page_url)
        page.goto(
            build_translate_page_url(source, "en"),
            wait_until="domcontentloaded",
            timeout=timeout_ms,
        )
        try:
            wait_for_translate_ui(page, timeout_ms=15_000)
        except BrowserTranslateError:
            print(
                "Browser opened. Log into SYSTRAN in this window, "
                "open Text Translation, then press Enter here to continue."
            )
            input()
            wait_for_translate_ui(page, timeout_ms)
        translator = cls._from_context(context, page, source=source, timeout_ms=timeout_ms)
        translator._active_pair = (source, "en")
        return translator, context

    @classmethod
    def _from_context(
        cls,
        context: BrowserContext,
        page: Page,
        *,
        source: str,
        timeout_ms: int,
    ) -> BrowserTranslator:
        print(f"Using translate page: {page.url}")
        print("Translation mode: SYSTRAN web UI")
        return cls(context, page, source=source, timeout_ms=timeout_ms)

    def translate(self, text: str, target: str) -> str:
        if target == "en":
            return self.translate_once(text, source=self.source, target="en")
        if target == "zh":
            return self.translate_once(text, source=self.source, target="zh")
        return self.translate_once(text, source=self.source, target=target)


def apply_translations(
    deck: dict,
    cache: dict[str, dict[str, str]],
    *,
    only_missing: bool,
) -> tuple[int, int]:
    updated = 0
    skipped = 0

    for word in deck.get("words", []):
        if not example_needs_translation(word, only_missing):
            skipped += 1
            continue

        example_da = (word.get("exampleDa") or "").strip()
        examples_da = normalize_examples(word.get("examplesDa"))
        if not example_da and examples_da:
            example_da = examples_da[0]
        if not examples_da and example_da:
            examples_da = [example_da]
        if not example_da and not examples_da:
            skipped += 1
            continue

        examples_en = [cache["en"].get(text, "") for text in examples_da]
        examples_zh = [cache["zh"].get(text, "") for text in examples_da]

        if only_missing:
            existing_en = normalize_examples(word.get("examplesEn"))
            existing_zh = normalize_examples(word.get("examplesZh"))
            examples_en = [
                cached if cached else (existing_en[index] if index < len(existing_en) else "")
                for index, cached in enumerate(examples_en)
            ]
            examples_zh = [
                cached if cached else (existing_zh[index] if index < len(existing_zh) else "")
                for index, cached in enumerate(examples_zh)
            ]

        word["examplesEn"] = examples_en
        word["examplesZh"] = examples_zh
        example_en = cache["en"].get(example_da, "") if example_da else ""
        example_zh = cache["zh"].get(example_da, "") if example_da else ""
        if only_missing:
            if not example_en:
                example_en = (word.get("exampleEn") or "").strip()
            if not example_zh:
                example_zh = (word.get("exampleZh") or "").strip()
        word["exampleEn"] = example_en or (examples_en[0] if examples_en else "")
        word["exampleZh"] = example_zh or (examples_zh[0] if examples_zh else "")
        updated += 1

    return updated, skipped


def translate_texts_with_browser(
    texts: list[str],
    translator: BrowserTranslator,
    cache: dict[str, dict[str, str]],
    cache_path: Path,
    *,
    sleep_seconds: float,
    force: bool = False,
    on_checkpoint: Callable[[dict[str, dict[str, str]]], None] | None = None,
) -> tuple[int, int]:
    translated_en = 0
    translated_zh = 0
    total = len(texts)
    pending_da = list(texts) if force else [text for text in texts if text not in cache["en"]]
    pending_zh_keys = list(texts) if force else [text for text in texts if text not in cache["zh"]]
    skipped_en = total - len(pending_da)
    skipped_zh = total - len(pending_zh_keys)

    if skipped_en:
        print(f"Skipping {skipped_en} Danish sentence(s) with English already cached", flush=True)
    if skipped_zh:
        print(f"Skipping {skipped_zh} Danish sentence(s) with Chinese already cached", flush=True)

    if pending_da:
        translator.ensure_language_pair(translator.source, "en")
        print(
            f"Phase 1/2: {len(pending_da)} Danish -> English remaining "
            f"({skipped_en}/{total} already done)",
            flush=True,
        )
        for index, danish in enumerate(pending_da, start=1):
            cache["en"][danish] = translator.translate_on_current_page(danish)
            translated_en += 1
            save_cache(cache_path, cache)
            global_index = skipped_en + index
            print(f"[EN {global_index}/{total}] {danish[:70]}", flush=True)
            if on_checkpoint and global_index % 25 == 0:
                on_checkpoint(cache)
            if sleep_seconds > 0 and index < len(pending_da):
                time.sleep(sleep_seconds)

    if pending_zh_keys:
        missing_en = [text for text in pending_zh_keys if not cache["en"].get(text)]
        if missing_en:
            translator.ensure_language_pair(translator.source, "en")
            print(f"Filling {len(missing_en)} missing English line(s) before phase 2...", flush=True)
            for danish in missing_en:
                cache["en"][danish] = translator.translate_on_current_page(danish)
                translated_en += 1
                save_cache(cache_path, cache)

        translator.ensure_language_pair("en", "zh")
        print(
            f"Phase 2/2: {len(pending_zh_keys)} English -> Chinese remaining "
            f"({skipped_zh}/{total} already done)",
            flush=True,
        )
        for index, danish in enumerate(pending_zh_keys, start=1):
            english = cache["en"][danish]
            cache["zh"][danish] = translator.translate_on_current_page(english)
            translated_zh += 1
            save_cache(cache_path, cache)
            global_index = skipped_zh + index
            print(f"[ZH {global_index}/{total}] {danish[:70]}", flush=True)
            if on_checkpoint and global_index % 25 == 0:
                on_checkpoint(cache)
            if sleep_seconds > 0 and index < len(pending_zh_keys):
                time.sleep(sleep_seconds)

    return translated_en, translated_zh


def probe_browser(
    *,
    cdp_url: str,
    page_url: str | None,
    timeout_ms: int,
    launch_browser: bool,
    profile_dir: Path,
) -> int:
    with sync_playwright() as playwright:
        launched_context = None
        if launch_browser:
            translator, launched_context = BrowserTranslator.connect_launch(
                playwright,
                profile_dir=profile_dir,
                source=DEFAULT_SOURCE,
                timeout_ms=timeout_ms,
                page_url=page_url,
            )
        else:
            translator = BrowserTranslator.connect_cdp(
                playwright,
                cdp_url=cdp_url,
                source=DEFAULT_SOURCE,
                timeout_ms=timeout_ms,
                page_url=page_url,
            )
        sample = "Det er en rigtig god dag i dag."
        translator.ensure_language_pair(DEFAULT_SOURCE, "en")
        en = translator.translate_on_current_page(sample)
        translator.ensure_language_pair("en", "zh")
        zh = translator.translate_on_current_page(en)
        print(f"Sample EN: {en}")
        print(f"Sample ZH: {zh}")
        if launched_context is not None:
            launched_context.close()
    return 0


def restart_self(*, wait_seconds: float) -> None:
    if wait_seconds > 0:
        print(f"Waiting {wait_seconds:.0f}s before restart...", flush=True)
        time.sleep(wait_seconds)
    print("Restarting translation...", flush=True)
    os.execv(sys.executable, [sys.executable, *sys.argv])


def run_browser_translation(
    args: argparse.Namespace,
    deck: dict,
    texts: list[str],
    cache: dict[str, dict[str, str]],
    *,
    checkpoint_deck: Callable[[dict[str, dict[str, str]]], None],
    timeout_ms: int,
    page_url: str | None,
) -> tuple[int, int, int, int]:
    with sync_playwright() as playwright:
        launched_context = None
        if args.launch_browser:
            translator, launched_context = BrowserTranslator.connect_launch(
                playwright,
                profile_dir=args.browser_profile,
                source=args.source,
                timeout_ms=timeout_ms,
                page_url=page_url,
            )
        else:
            translator = BrowserTranslator.connect_cdp(
                playwright,
                cdp_url=args.cdp_url,
                source=args.source,
                timeout_ms=timeout_ms,
                page_url=page_url,
            )
        translated_en, translated_zh = translate_texts_with_browser(
            texts,
            translator,
            cache,
            args.cache,
            sleep_seconds=max(0.0, args.sleep),
            force=args.force,
            on_checkpoint=checkpoint_deck,
        )
        if launched_context is not None:
            launched_context.close()

    updated, skipped = apply_translations(deck, cache, only_missing=args.only_missing)
    args.deck.write_text(
        json.dumps(deck, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return translated_en, translated_zh, updated, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deck", type=Path, default=DEFAULT_DECK_PATH)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE_PATH)
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    parser.add_argument(
        "--launch-browser",
        action="store_true",
        help="Open a dedicated Chrome window (keeps login in data/.systran-browser-profile)",
    )
    parser.add_argument("--browser-profile", type=Path, default=DEFAULT_BROWSER_PROFILE)
    parser.add_argument("--page-url", default="", help="Prefer an already-open SYSTRAN tab URL")
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--sleep", type=float, default=0.5)
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Skip entries that already have real sentence translations (not word glosses)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-translate even if a sentence is already in the cache",
    )
    parser.add_argument(
        "--apply-cache-to-deck",
        action="store_true",
        help="Write cached translations into deck.json without calling SYSTRAN",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--auto-restart",
        action="store_true",
        help="On browser translation failure, wait and restart this script with the same arguments",
    )
    parser.add_argument(
        "--restart-wait",
        type=float,
        default=120.0,
        help="Seconds to wait before auto-restart (default: 120)",
    )
    parser.add_argument("--probe", action="store_true", help="Test browser translation with one sample sentence")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    timeout_ms = max(5_000, int(args.timeout * 1000))
    page_url = args.page_url.strip() or None

    if args.probe:
        return probe_browser(
            cdp_url=args.cdp_url,
            page_url=page_url,
            timeout_ms=timeout_ms,
            launch_browser=args.launch_browser,
            profile_dir=args.browser_profile,
        )

    deck = json.loads(args.deck.read_text(encoding="utf-8"))
    texts = collect_texts(deck, args.only_missing)
    if args.limit > 0:
        texts = texts[: args.limit]

    print(f"Unique Danish example texts: {len(texts)}")
    mode = "only missing / bad glosses" if args.only_missing else "all examples"
    if args.force:
        mode += ", force re-translate"
    print(f"Mode: {mode}")

    if args.dry_run:
        for text in texts[:10]:
            print(f"  - {text}")
        if len(texts) > 10:
            print(f"  ... and {len(texts) - 10} more")
        return 0

    cache = load_cache(args.cache)
    cached_en = sum(1 for text in texts if text in cache["en"])
    cached_zh = sum(1 for text in texts if text in cache["zh"])
    pending_en = len(texts) if args.force else sum(1 for text in texts if text not in cache["en"])
    pending_zh = len(texts) if args.force else sum(1 for text in texts if text not in cache["zh"])

    if args.apply_cache_to_deck:
        updated, skipped = apply_translations(deck, cache, only_missing=args.only_missing)
        args.deck.write_text(
            json.dumps(deck, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"Applied cache to deck. cached_en={cached_en}, cached_zh={cached_zh}, "
            f"words_updated={updated}, skipped={skipped}"
        )
        return 0

    print(
        f"Cache: English {cached_en}/{len(texts)}, Chinese {cached_zh}/{len(texts)}"
    )
    if not args.force and (cached_en or cached_zh):
        print("Resume mode: already cached sentences will be skipped (do not use --force)")
    print(f"Pending: English {pending_en}, Chinese {pending_zh}")

    def checkpoint_deck(current_cache: dict[str, dict[str, str]]) -> None:
        apply_translations(deck, current_cache, only_missing=args.only_missing)
        args.deck.write_text(
            json.dumps(deck, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    try:
        translated_en, translated_zh, updated, skipped = run_browser_translation(
            args,
            deck,
            texts,
            cache,
            checkpoint_deck=checkpoint_deck,
            timeout_ms=timeout_ms,
            page_url=page_url,
        )
    except BrowserTranslateError as exc:
        checkpoint_deck(cache)
        print(f"Browser translation failed: {exc}", flush=True)
        if args.auto_restart:
            restart_self(wait_seconds=max(0.0, args.restart_wait))
        raise SystemExit(1) from exc

    stats = TranslateStats(
        unique_texts=len(texts),
        translated_en=translated_en,
        translated_zh=translated_zh,
        words_updated=updated,
        skipped=skipped,
    )
    print(
        "Done. "
        f"unique_texts={stats.unique_texts}, "
        f"new_en={stats.translated_en}, "
        f"new_zh={stats.translated_zh}, "
        f"words_updated={stats.words_updated}, "
        f"skipped={stats.skipped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
