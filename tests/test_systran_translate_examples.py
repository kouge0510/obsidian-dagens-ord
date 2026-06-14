import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "systran-translate-examples.py"


def load_script():
    spec = importlib.util.spec_from_file_location("systran_translate_examples", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SystranTranslateExamplesTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script()

    def test_collect_texts_only_missing(self):
        deck = {
            "words": [
                {
                    "id": "er",
                    "exampleDa": "Det er en rigtig god dag i dag.",
                    "examplesDa": ["Hvor er du henne?"],
                    "exampleEn": "",
                    "exampleZh": "",
                    "examplesEn": [],
                    "examplesZh": [],
                },
                {
                    "id": "jeg",
                    "exampleDa": "Du bliver nødt til at acceptere mig, som jeg er",
                    "examplesDa": ["Du bliver nødt til at acceptere mig, som jeg er"],
                    "exampleEn": "I",
                    "exampleZh": "我",
                    "examplesEn": ["I"],
                    "examplesZh": ["我"],
                    "translationsEn": ["I", "self"],
                    "translationsZh": ["我", "自我"],
                },
            ]
        }

        texts = self.script.collect_texts(deck, only_missing=True)

        self.assertEqual(
            texts,
            [
                "Det er en rigtig god dag i dag.",
                "Du bliver nødt til at acceptere mig, som jeg er",
            ],
        )

    def test_collect_texts_ignores_examples_da(self):
        deck = {
            "words": [
                {
                    "id": "vej",
                    "exampleDa": "de .. kører ud ad en støvet vej i en gammel, åben Ford",
                    "examplesDa": [
                        "de .. kører ud ad en støvet vej i en gammel, åben Ford",
                        "Den europæiske union er vejen til det nye Europa i den europæiske udvikling",
                        "Det kildede hele vejen ned ad ryggen",
                    ],
                    "exampleEn": "road",
                    "exampleZh": "道路",
                    "examplesEn": [
                        "road",
                        "The European Union is the road to the new Europe of European development",
                        "pathway",
                    ],
                    "examplesZh": ["道路", "方法", "过程"],
                    "translationsEn": ["road", "street", "path", "route", "way", "pathway"],
                    "translationsZh": ["道路", "方法", "过程"],
                }
            ]
        }

        texts_en = self.script.collect_texts(deck, only_missing=True, target="en")
        texts_zh = self.script.collect_texts(deck, only_missing=True, target="zh")

        self.assertEqual(texts_en, ["de .. kører ud ad en støvet vej i en gammel, åben Ford"])
        self.assertEqual(texts_zh, ["de .. kører ud ad en støvet vej i en gammel, åben Ford"])

    def test_seed_cache_from_deck_imports_good_primary_translation(self):
        deck = {
            "words": [
                {
                    "id": "vej",
                    "exampleDa": "Den europæiske union er vejen til det nye Europa i den europæiske udvikling",
                    "exampleEn": "The European Union is the road to the new Europe of European development",
                    "exampleZh": "方法",
                    "translationsEn": ["road", "street"],
                    "translationsZh": ["道路", "方法"],
                }
            ]
        }
        cache = {"en": {}, "zh": {}}

        seeded = self.script.seed_cache_from_deck(deck, cache, only_missing=True)

        self.assertEqual(seeded, 1)
        self.assertIn(
            "Den europæiske union er vejen til det nye Europa i den europæiske udvikling",
            cache["en"],
        )

    def test_apply_translations_updates_primary_and_arrays(self):
        deck = {
            "words": [
                {
                    "id": "er",
                    "exampleDa": "Det er en rigtig god dag i dag.",
                    "examplesDa": [
                        "Det er en rigtig god dag i dag.",
                        "Hvor er du henne?",
                    ],
                    "exampleEn": "",
                    "exampleZh": "",
                    "examplesEn": [],
                    "examplesZh": [],
                }
            ]
        }
        cache = {
            "en": {
                "Det er en rigtig god dag i dag.": "It is a really good day today.",
                "Hvor er du henne?": "Where are you?",
            },
            "zh": {
                "Det er en rigtig god dag i dag.": "今天真是美好的一天。",
                "Hvor er du henne?": "你在哪里？",
            },
        }

        updated, skipped = self.script.apply_translations(deck, cache, only_missing=True)

        word = deck["words"][0]
        self.assertEqual(updated, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(word["exampleEn"], "It is a really good day today.")
        self.assertEqual(word["exampleZh"], "今天真是美好的一天。")
        self.assertEqual(word["examplesEn"], [])
        self.assertEqual(word["examplesZh"], [])

    def test_parse_translation_payload_reads_outputs(self):
        payload = {
            "outputs": [
                {"output": "It is a really good day today."},
            ]
        }

        result = self.script.parse_translation_payload(payload)

        self.assertEqual(result, "It is a really good day today.")

    def test_apply_translations_prefers_cache_over_existing_gloss(self):
        deck = {
            "words": [
                {
                    "id": "jeg",
                    "exampleDa": "Du bliver nødt til at acceptere mig, som jeg er",
                    "examplesDa": ["Du bliver nødt til at acceptere mig, som jeg er"],
                    "exampleEn": "I",
                    "exampleZh": "我",
                    "examplesEn": ["I"],
                    "examplesZh": ["我"],
                    "translationsEn": ["I", "self"],
                    "translationsZh": ["我", "自我"],
                }
            ]
        }
        cache = {
            "en": {
                "Du bliver nødt til at acceptere mig, som jeg er": "You have to accept me as I am",
            },
            "zh": {
                "Du bliver nødt til at acceptere mig, som jeg er": "你必须接受我本来的样子",
            },
        }

        self.script.apply_translations(deck, cache, only_missing=True)

        word = deck["words"][0]
        self.assertEqual(word["exampleEn"], "You have to accept me as I am")
        self.assertEqual(word["exampleZh"], "你必须接受我本来的样子")
        self.assertEqual(word["examplesEn"], ["I"])
        self.assertEqual(word["examplesZh"], ["我"])
        payload = {
            "outputs": [
                {
                    "output": {
                        "documents": [
                            {
                                "trans_units": [
                                    {
                                        "sentences": [
                                            {
                                                "alt_transes": [
                                                    {"target": {"text": "Today is a very good day."}}
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        }

        result = self.script.parse_translation_payload(payload)

        self.assertEqual(result, "Today is a very good day.")

    def test_main_dry_run_does_not_write_deck(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            deck_path = tmp_path / "deck.json"
            deck_path.write_text(
                json.dumps(
                    {
                        "words": [
                            {
                                "id": "er",
                                "exampleDa": "Det er en rigtig god dag i dag.",
                                "examplesDa": [],
                                "exampleEn": "",
                                "exampleZh": "",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            original = deck_path.read_text(encoding="utf-8")

            result = self.script.main(
                [
                    "--deck",
                    str(deck_path),
                    "--dry-run",
                ]
            )

            self.assertEqual(result, 0)
            self.assertEqual(deck_path.read_text(encoding="utf-8"), original)

    def test_auto_restart_on_browser_translate_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            deck_path = tmp_path / "deck.json"
            cache_path = tmp_path / "cache.json"
            deck_path.write_text(
                json.dumps(
                    {
                        "words": [
                            {
                                "id": "er",
                                "exampleDa": "Det er en rigtig god dag i dag.",
                                "examplesDa": [],
                                "exampleEn": "",
                                "exampleZh": "",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            cache_path.write_text(
                json.dumps({"en": {}, "zh": {}}),
                encoding="utf-8",
            )

            def fail_translation(*_args, **_kwargs):
                raise self.script.BrowserTranslateError(
                    "Translation failed for target=en after 3 attempts"
                )

            with patch.object(self.script, "run_browser_translation", side_effect=fail_translation):
                with patch.object(self.script, "restart_self") as restart_self:
                    with self.assertRaises(SystemExit) as ctx:
                        self.script.main(
                            [
                                "--deck",
                                str(deck_path),
                                "--cache",
                                str(cache_path),
                                "--only-missing",
                            ]
                        )
                    self.assertEqual(ctx.exception.code, 1)
                    restart_self.assert_not_called()

                    restart_self.reset_mock()
                    with self.assertRaises(SystemExit):
                        self.script.main(
                            [
                                "--deck",
                                str(deck_path),
                                "--cache",
                                str(cache_path),
                                "--only-missing",
                                "--auto-restart",
                                "--restart-wait",
                                "0",
                            ]
                        )
                    restart_self.assert_called_once_with(wait_seconds=0.0)


if __name__ == "__main__":
    unittest.main()
