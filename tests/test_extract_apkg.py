import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "extract-apkg.py"


def load_script():
    spec = importlib.util.spec_from_file_location("extract_apkg", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ExtractApkgTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script()

    def test_parse_translations_reads_definition_field(self):
        html = (
            '<div class="definition-item">fortale sig'
            '<div class="translation"><b>let something slip</b>: '
            "To reveal a secret unintentionally.</div></div>"
        )

        self.assertEqual(self.script.parse_translations(html), ["let something slip"])

    def test_parse_translations_falls_back_to_definition_field(self):
        fields = [
            "fortalt",
            "<div>summary</div>",
            "",
            '<div class="definition-item">fortale sig'
            '<div class="translation"><b>let something slip</b></div></div>',
        ]

        self.assertEqual(
            self.script.parse_entry_translations(fields),
            ["let something slip"],
        )


if __name__ == "__main__":
    unittest.main()
