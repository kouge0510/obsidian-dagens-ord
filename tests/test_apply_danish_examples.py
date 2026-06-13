import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "apply-danish-examples.py"


def load_script():
    spec = importlib.util.spec_from_file_location("apply_danish_examples", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ApplyDanishExamplesTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script()

    def test_apply_entries_writes_example_fields(self):
        deck = {
            "words": [
                {"id": "er", "word": "er", "rank": 1, "exampleDa": "", "examplesDa": []},
            ],
        }
        entries = [
            {
                "id": "er",
                "word": "er",
                "rank": 1,
                "exampleDa": "Det er min bil.",
                "examplesDa": ["Det er min bil.", "Er du klar?"],
            },
        ]

        result = self.script.apply_entries(deck, entries)

        self.assertEqual(result.matched, 1)
        self.assertEqual(deck["words"][0]["exampleDa"], "Det er min bil.")
        self.assertEqual(
            deck["words"][0]["examplesDa"],
            ["Det er min bil.", "Er du klar?"],
        )

    def test_apply_file_reads_missing_block_from_export_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck_path = Path(tmp) / "deck.json"
            input_path = Path(tmp) / "missing.json"
            deck_path.write_text(
                json.dumps(
                    {
                        "words": [
                            {"id": "er", "word": "er", "rank": 1, "exampleDa": "", "examplesDa": []},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            input_path.write_text(
                json.dumps(
                    {
                        "missing": [
                            {
                                "id": "er",
                                "word": "er",
                                "rank": 1,
                                "exampleDa": "Det er min bil.",
                                "examplesDa": [],
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = self.script.apply_file(deck_path, input_path)
            deck = json.loads(deck_path.read_text(encoding="utf-8"))

        self.assertEqual(result.matched, 1)
        self.assertEqual(deck["words"][0]["exampleDa"], "Det er min bil.")
        self.assertEqual(deck["words"][0]["examplesDa"], ["Det er min bil."])


if __name__ == "__main__":
    unittest.main()
