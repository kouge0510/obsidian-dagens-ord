import importlib.util
import json
import sys
import tempfile
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
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ExtractExampleTranslationsFromApkgTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script()

    def test_parse_entry_example_translations_uses_definition_items_with_examples(self):
        fields = [
            "jeg",
            "<div>summary</div>",
            (
                '<div class="meaning-block">'
                '<div class="definition-item"><span class="def-text">1</span>'
                '<div class="translation"><b>I</b>: Used by speaker.</div>'
                '<div class="example">E.g., "Du bliver nødt til at acceptere mig, som jeg er"</div>'
                "</div>"
                '<div class="definition-item"><span class="def-text">2</span>'
                '<div class="translation"><b>self</b>: inner self.</div>'
                '<div class="example">E.g., "Det sunde menneske er for Freud et menneske med et stort jeg"</div>'
                "</div>"
                "</div>"
            ),
            (
                '<div class="definition-item">nogens andet jeg'
                '<div class="translation"><b>someone\'s alter ego</b></div>'
                "</div>"
            ),
        ]

        self.assertEqual(
            self.script.parse_entry_example_translations(fields),
            ["I", "self"],
        )

    def test_build_indexes_keeps_rank_and_word_fallback(self):
        rows = [
            {"word": "jeg", "rank": "2", "translations": ["I", "self"]},
            {"word": "mig", "rank": "", "translations": ["me"]},
        ]

        by_word_rank, by_word = self.script.build_indexes(rows)

        self.assertEqual(by_word_rank[("jeg", "2")]["translations"], ["I", "self"])
        self.assertEqual(by_word["mig"]["translations"], ["me"])

    def test_lookup_prefers_word_rank_then_falls_back_to_word(self):
        by_word_rank = {("jeg", "2"): {"translations": ["I"]}}
        by_word = {"jeg": {"translations": ["fallback"]}}

        hit = self.script.lookup_entry("jeg", 2, by_word_rank, by_word)
        fallback = self.script.lookup_entry("mig", 1, {}, {"mig": {"translations": ["me"]}})
        miss = self.script.lookup_entry("ham", 1, by_word_rank, by_word)

        self.assertEqual(hit["translations"], ["I"])
        self.assertEqual(fallback["translations"], ["me"])
        self.assertIsNone(miss)

    def test_merge_example_translations_sets_array_and_compatibility_fields(self):
        deck = {
            "words": [
                {"id": "jeg", "word": "jeg", "rank": 2, "exampleEn": "", "exampleZh": ""},
                {"id": "mig", "word": "mig", "rank": 10, "exampleEn": "old", "exampleZh": "旧"},
            ]
        }
        english = {("jeg", "2"): {"translations": ["I", "self"]}}
        chinese = {("jeg", "2"): {"translations": ["我"]}}

        stats = self.script.merge_example_translations(deck, english, chinese)
        jeg = deck["words"][0]
        mig = deck["words"][1]

        self.assertEqual(jeg["examplesEn"], ["I", "self"])
        self.assertEqual(jeg["examplesZh"], ["我"])
        self.assertEqual(jeg["exampleEn"], "I")
        self.assertEqual(jeg["exampleZh"], "我")
        self.assertEqual(mig["examplesEn"], [])
        self.assertEqual(mig["examplesZh"], [])
        self.assertEqual(mig["exampleEn"], "")
        self.assertEqual(mig["exampleZh"], "")
        self.assertEqual(stats.total_words, 2)
        self.assertEqual(stats.english_matched, 1)
        self.assertEqual(stats.chinese_matched, 1)
        self.assertEqual(stats.both_present, 1)
        self.assertEqual(stats.one_side_missing, 0)
        self.assertEqual(stats.both_missing, 1)

    def test_write_translations_to_deck_updates_existing_file(self):
        deck = {
            "total": 1,
            "words": [
                {"id": "jeg", "word": "jeg", "rank": 2, "exampleEn": "", "exampleZh": ""}
            ],
        }
        english = {("jeg", "2"): {"translations": ["I"]}}
        chinese = {("jeg", "2"): {"translations": ["我"]}}

        with tempfile.TemporaryDirectory() as td:
            deck_path = Path(td) / "deck.json"
            deck_path.write_text(json.dumps(deck, ensure_ascii=False), encoding="utf-8")

            stats = self.script.write_translations_to_deck(deck_path, english, chinese)
            updated = json.loads(deck_path.read_text(encoding="utf-8"))

        self.assertEqual(updated["words"][0]["examplesEn"], ["I"])
        self.assertEqual(updated["words"][0]["examplesZh"], ["我"])
        self.assertEqual(updated["words"][0]["exampleEn"], "I")
        self.assertEqual(updated["words"][0]["exampleZh"], "我")
        self.assertEqual(stats.total_words, 1)


if __name__ == "__main__":
    unittest.main()
