import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "backfill-missing-word-translations.py"


def load_script():
    spec = importlib.util.spec_from_file_location("backfill_missing_word_translations", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BackfillMissingWordTranslationsTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script()

    def test_apply_manual_translations_only_fills_missing_fields(self):
        deck = {
            "words": [
                {
                    "id": "og",
                    "word": "og",
                    "rank": 8,
                    "translationEn": "",
                    "translationsEn": [],
                    "translationZh": "",
                    "translationsZh": [],
                },
                {
                    "id": "jeg",
                    "word": "jeg",
                    "rank": 2,
                    "translationEn": "I",
                    "translationsEn": ["I"],
                    "translationZh": "我",
                    "translationsZh": ["我"],
                },
            ],
        }
        manual = {
            "entries": [
                {
                    "id": "og",
                    "rank": 8,
                    "translationsEn": ["and"],
                    "translationsZh": ["和"],
                },
                {
                    "id": "jeg",
                    "rank": 2,
                    "translationsEn": ["should not apply"],
                    "translationsZh": ["不应写入"],
                },
            ],
        }

        result = self.script.apply_manual_translations(
            deck,
            self.script.build_manual_index(manual["entries"]),
        )

        self.assertEqual(result.en_updated, 1)
        self.assertEqual(result.zh_updated, 1)
        self.assertEqual(deck["words"][0]["translationEn"], "and")
        self.assertEqual(deck["words"][0]["translationsZh"], ["和"])
        self.assertEqual(deck["words"][1]["translationEn"], "I")


if __name__ == "__main__":
    unittest.main()
