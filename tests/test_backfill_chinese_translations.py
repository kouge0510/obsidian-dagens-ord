import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "backfill-chinese-translations.py"


def load_script():
    spec = importlib.util.spec_from_file_location("backfill_chinese_translations", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BackfillChineseTranslationsTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script()

    def test_backfill_deck_sets_chinese_translation_fields(self):
        deck = {
            "words": [
                {"word": "grønt", "rank": 2842},
                {"word": "ukendt", "rank": 9999},
            ]
        }
        translations = {
            ("grønt", "2842"): ["蔬菜", "绿植"],
        }

        updated = self.script.backfill_deck(deck, translations)

        self.assertEqual(updated, 1)
        self.assertEqual(deck["words"][0]["translationZh"], "蔬菜")
        self.assertEqual(deck["words"][0]["translationsZh"], ["蔬菜", "绿植"])
        self.assertEqual(deck["words"][1]["translationZh"], "")
        self.assertEqual(deck["words"][1]["translationsZh"], [])


if __name__ == "__main__":
    unittest.main()
