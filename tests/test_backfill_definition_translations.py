import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "backfill-definition-translations.py"


def load_script():
    spec = importlib.util.spec_from_file_location("backfill_definition_translations", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BackfillDefinitionTranslationsTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script()

    def test_backfill_deck_only_updates_missing_translations(self):
        deck = {
            "words": [
                {"word": "må", "rank": 50, "translationEn": "", "translationsEn": []},
                {"word": "har", "rank": 9, "translationEn": "has", "translationsEn": ["has"]},
            ]
        }
        fallback = {
            ("må", "50"): ["hit or miss"],
            ("har", "9"): ["fallback should not replace"],
        }

        updated = self.script.backfill_deck(deck, fallback)

        self.assertEqual(updated, 1)
        self.assertEqual(deck["words"][0]["translationEn"], "hit or miss")
        self.assertEqual(deck["words"][0]["translationsEn"], ["hit or miss"])
        self.assertEqual(deck["words"][1]["translationEn"], "has")


if __name__ == "__main__":
    unittest.main()
