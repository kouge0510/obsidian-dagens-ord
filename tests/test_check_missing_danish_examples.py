import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "check-missing-danish-examples.py"


def load_script():
    spec = importlib.util.spec_from_file_location("check_missing_danish_examples", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CheckMissingDanishExamplesTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script()

    def test_analyze_deck_counts_missing_and_lists_words(self):
        deck = {
            "words": [
                {
                    "id": "jeg",
                    "word": "jeg",
                    "rank": 2,
                    "pos": "pronoun",
                    "exampleDa": "Du bliver nødt til at acceptere mig",
                    "examplesDa": ["Du bliver nødt til at acceptere mig"],
                },
                {
                    "id": "er",
                    "word": "er",
                    "rank": 5,
                    "pos": "verb",
                    "exampleDa": "",
                    "examplesDa": [],
                },
                {
                    "id": "og",
                    "word": "og",
                    "rank": 3,
                    "pos": "conjunction",
                    "exampleDa": "",
                    "examplesDa": ["Han og hun"],
                },
            ],
        }

        report = self.script.analyze_deck(deck)

        self.assertEqual(report.total_words, 3)
        self.assertEqual(report.with_example, 2)
        self.assertEqual([item.id for item in report.missing], ["er"])
        self.assertEqual([item.id for item in report.inconsistent], ["og"])

    def test_export_missing_includes_fillable_example_fields(self):
        import tempfile

        deck = {
            "words": [
                {
                    "id": "er",
                    "word": "er",
                    "rank": 1,
                    "pos": "symbol",
                    "exampleDa": "",
                    "examplesDa": [],
                },
            ],
        }
        report = self.script.analyze_deck(deck)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.json"
            self.script.export_missing(deck, report, path)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertIn("instructions", payload)
        self.assertEqual(payload["missing"][0]["exampleDa"], "")
        self.assertEqual(payload["missing"][0]["examplesDa"], [])


if __name__ == "__main__":
    unittest.main()
