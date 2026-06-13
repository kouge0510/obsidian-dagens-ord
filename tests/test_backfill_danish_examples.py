import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "backfill-danish-examples.py"


def load_script():
    spec = importlib.util.spec_from_file_location("backfill_danish_examples", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BackfillDanishExamplesTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script()

    def test_backfill_deck_only_updates_missing_examples(self):
        deck = {
            "words": [
                {
                    "id": "jeg",
                    "word": "jeg",
                    "rank": 2,
                    "exampleDa": "Existing",
                    "examplesDa": ["Existing"],
                },
                {
                    "id": "er",
                    "word": "er",
                    "rank": 5,
                    "exampleDa": "",
                    "examplesDa": [],
                },
            ],
        }
        examples = {
            ("jeg", "2"): ["Should not apply"],
            ("er", "5"): ["Er det rigtigt?", "Er du klar?"],
        }

        updated = self.script.backfill_deck(deck, examples)

        self.assertEqual(updated, 1)
        self.assertEqual(deck["words"][0]["exampleDa"], "Existing")
        self.assertEqual(deck["words"][1]["exampleDa"], "Er det rigtigt?")
        self.assertEqual(deck["words"][1]["examplesDa"], ["Er det rigtigt?", "Er du klar?"])

    def test_is_missing_example_treats_nonempty_examples_da_as_present(self):
        word = {"exampleDa": "", "examplesDa": ["Eksempel"]}
        self.assertFalse(self.script.is_missing_example(word))


if __name__ == "__main__":
    unittest.main()
