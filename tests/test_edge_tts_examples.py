import importlib.util
import io
import subprocess
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "edge-tts-examples.py"


def load_script():
    spec = importlib.util.spec_from_file_location("edge_tts_examples", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class EdgeTtsExamplesTest(unittest.TestCase):
    def setUp(self):
        self.script = load_script()
        self.deck = {
            "words": [
                {"id": "jeg", "exampleDa": "Du bliver nødt til at acceptere mig"},
                {"id": "tom", "exampleDa": ""},
                {"id": "det", "exampleDa": "Hun tog kruset og drak det"},
            ],
        }
        self.word_deck = {
            "words": [
                {"id": "jeg", "word": "jeg", "audioWord": "anki-jeg.mp3"},
                {"id": "og", "word": "og", "audioWord": ""},
                {"id": "kan", "word": "kan", "audioWord": None},
                {"id": "det", "word": "det", "audioWord": "anki-det.mp3"},
            ],
        }

    def test_iter_example_items_defaults_to_all_words_with_examples(self):
        items = list(self.script.iter_example_items(self.deck, count=0))

        self.assertEqual([item.cache_key for item in items], ["ex-jeg", "ex-det"])
        self.assertEqual(items[0].text, "Du bliver nødt til at acceptere mig")

    def test_iter_example_items_can_limit_source_words(self):
        items = list(self.script.iter_example_items(self.deck, count=1))

        self.assertEqual([item.cache_key for item in items], ["ex-jeg"])

    def test_iter_missing_word_items_selects_only_unreadable_word_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            (out_dir / "anki-jeg.mp3").write_bytes(b"audio")

            items = list(
                self.script.iter_missing_word_items(
                    self.word_deck,
                    out_dir=out_dir,
                    count=0,
                )
            )

        self.assertEqual([item.cache_key for item in items], ["word-og", "word-kan", "word-det"])
        self.assertEqual([item.text for item in items], ["og", "kan", "det"])
        self.assertEqual(
            [item.output_name for item in items],
            ["tts-word-og.mp3", "tts-word-kan.mp3", "anki-det.mp3"],
        )

    def test_iter_missing_word_items_can_limit_source_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            (out_dir / "anki-jeg.mp3").write_bytes(b"audio")
            items = list(
                self.script.iter_missing_word_items(
                    self.word_deck,
                    out_dir=out_dir,
                    count=2,
                )
            )

        self.assertEqual([item.cache_key for item in items], ["word-og"])

    def test_apply_generated_word_audio_updates_missing_audio_names(self):
        items = [
            self.script.AudioItem(
                cache_key="word-og",
                text="og",
                output_name="tts-word-og.mp3",
                word_id="og",
                audio_field_needs_update=True,
            ),
            self.script.AudioItem(
                cache_key="word-det",
                text="det",
                output_name="anki-det.mp3",
                word_id="det",
                audio_field_needs_update=False,
            ),
        ]

        updated = self.script.apply_generated_word_audio(self.word_deck, items)

        self.assertEqual(updated, 1)
        self.assertEqual(self.word_deck["words"][1]["audioWord"], "tts-word-og.mp3")
        self.assertEqual(self.word_deck["words"][3]["audioWord"], "anki-det.mp3")

    def test_audio_exists_checks_supported_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            self.assertFalse(self.script.audio_exists(out_dir, "ex-jeg"))

            (out_dir / "ex-jeg.mp3").write_bytes(b"audio")

            self.assertTrue(self.script.audio_exists(out_dir, "ex-jeg"))

    def test_audio_exists_ignores_empty_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            (out_dir / "ex-jeg.mp3").write_bytes(b"")

            self.assertFalse(self.script.audio_exists(out_dir, "ex-jeg"))

    def test_build_edge_tts_command_uses_danish_voice_and_mp3_path(self):
        out_path = Path("audio/generated/ex-jeg.mp3")

        command = self.script.build_edge_tts_command(
            voice="da-DK-ChristelNeural",
            text="Godmorgen",
            out_path=out_path,
            rate="+0%",
        )

        self.assertEqual(
            command,
            [
                "edge-tts",
                "--voice",
                "da-DK-ChristelNeural",
                "--rate",
                "+0%",
                "--text",
                "Godmorgen",
                "--write-media",
                str(out_path),
            ],
        )

    def test_generate_audio_records_failure_and_continues(self):
        calls = []

        def fake_runner(command, check, **kwargs):
            calls.append(command)
            if "ex-det.mp3" in command[-1]:
                raise subprocess.CalledProcessError(1, command)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            items = list(self.script.iter_example_items(self.deck, count=0))
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = self.script.generate_audio(
                    items=items,
                    out_dir=out_dir,
                    voice="da-DK-ChristelNeural",
                    rate="+0%",
                    overwrite=False,
                    runner=fake_runner,
                )

        self.assertEqual(result.selected, 2)
        self.assertEqual(result.generated, 1)
        self.assertEqual(result.failed, 1)
        self.assertEqual(len(calls), 4)

    def test_parse_args_supports_jobs(self):
        default_args = self.script.parse_args([])
        custom_args = self.script.parse_args(["--jobs", "8"])

        self.assertEqual(default_args.jobs, 4)
        self.assertEqual(custom_args.jobs, 8)
        self.assertEqual(default_args.retries, 2)

    def test_generate_audio_runs_items_concurrently_when_jobs_is_above_one(self):
        active = 0
        max_active = 0
        lock = threading.Lock()

        def fake_runner(command, check, **kwargs):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with lock:
                active -= 1

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            items = list(self.script.iter_example_items(self.deck, count=0))
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = self.script.generate_audio(
                    items=items,
                    out_dir=out_dir,
                    voice="da-DK-ChristelNeural",
                    rate="+0%",
                    overwrite=False,
                    jobs=2,
                    runner=fake_runner,
                )

        self.assertEqual(result.generated, 2)
        self.assertGreaterEqual(max_active, 2)

    def test_generate_audio_retries_transient_failures(self):
        calls = []

        def fake_runner(command, check, **kwargs):
            calls.append((command, kwargs))
            if len(calls) == 1:
                raise subprocess.CalledProcessError(
                    1,
                    command,
                    stderr="No audio was received",
                )

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            item = self.script.ExampleItem("ex-jeg", "Godmorgen")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = self.script.generate_audio(
                    items=[item],
                    out_dir=out_dir,
                    voice="da-DK-ChristelNeural",
                    rate="+0%",
                    overwrite=False,
                    jobs=1,
                    retries=2,
                    retry_delay=0,
                    runner=fake_runner,
                )

        self.assertEqual(result.generated, 1)
        self.assertEqual(result.failed, 0)
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0][1]["capture_output"])
        self.assertTrue(calls[0][1]["text"])

    def test_generate_audio_removes_partial_file_after_final_failure(self):
        def fake_runner(command, check, **kwargs):
            Path(command[-1]).write_bytes(b"partial")
            raise subprocess.CalledProcessError(
                1,
                command,
                stderr="No audio was received",
            )

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            item = self.script.ExampleItem("ex-jeg", "Godmorgen")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = self.script.generate_audio(
                    items=[item],
                    out_dir=out_dir,
                    voice="da-DK-ChristelNeural",
                    rate="+0%",
                    overwrite=False,
                    jobs=1,
                    retries=0,
                    retry_delay=0,
                    runner=fake_runner,
                )

            self.assertEqual(result.generated, 0)
            self.assertEqual(result.failed, 1)
            self.assertFalse((out_dir / "ex-jeg.mp3").exists())


if __name__ == "__main__":
    unittest.main()
