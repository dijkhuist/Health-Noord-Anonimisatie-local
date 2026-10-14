import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from src.hn_ano_tool.app.service import (
    MainController,
    ProcessingCancelled,
    Settings,
    _sanitize_error_message,
)


class ServiceTests(unittest.TestCase):
    def test_anonymizer_initialization_failure_writes_failure_log(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.txt"
            output_dir = Path(directory) / "output"
            input_path.write_text("input\n", encoding="utf-8")
            settings = Settings(str(input_path), str(output_dir), None)

            with patch(
                "src.hn_ano_tool.app.service.Anonymizer",
                side_effect=RuntimeError(f"cannot initialize for {input_path}"),
            ):
                with self.assertRaisesRegex(RuntimeError, "cannot initialize"):
                    MainController(settings).run()

            files = list(output_dir.iterdir())
            self.assertEqual(len(files), 1)
            self.assertIn("_log_", files[0].name)
            self.assertNotIn("_anonymized_", files[0].name)
            log_text = files[0].read_text(encoding="utf-8")
            self.assertIn("Status: Mislukt", log_text)
            self.assertNotIn(directory, log_text)

    def test_error_log_masks_private_paths_case_insensitively(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "patient record.txt"
            output_path = Path(directory) / "output"
            whitelist_path = Path(directory) / "private whitelist.txt"
            settings = Settings(
                str(input_path),
                str(output_path),
                str(output_path),
                whitelist_path=str(whitelist_path),
            )
            message = (
                f"Could not open {str(input_path).upper()} or {whitelist_path} "
                f"in {output_path}"
            )

            safe_message = _sanitize_error_message(OSError(message), settings)

        self.assertNotIn(directory, safe_message)
        self.assertIn("patient record.txt", safe_message)
        self.assertIn("[whitelistbestand]", safe_message)
        self.assertIn("[uitvoermap]", safe_message)

    def test_success_reports_progress_and_publishes_complete_output(self):
        class EchoAnonymizer:
            def __init__(self, **_kwargs):
                pass

            def anonymize_stream(self, lines, _stats):
                _stats.by_type.update({"bsn": 2, "extra persoon": 3, "extra locatie": 1})
                yield from lines

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.txt"
            output_dir = Path(directory) / "output"
            input_path.write_text("complete input\n", encoding="utf-8")
            whitelist_path = Path(directory) / "private whitelist terms.txt"
            whitelist_path.write_text("Sensitive medical term", encoding="utf-8")
            progress = []
            phases = []
            settings = Settings(
                str(input_path),
                str(output_dir),
                None,
                extra_names_paths={"patient": str(whitelist_path)},
                disabled_groups={"dates"},
                whitelist_path=str(whitelist_path),
            )

            with patch("src.hn_ano_tool.app.service.Anonymizer", EchoAnonymizer):
                _, output_path, log_path, _ = MainController(settings).run(
                    progress_callback=lambda processed, total: progress.append((processed, total)),
                    phase_callback=phases.append,
                )

            self.assertEqual(Path(output_path).read_text(encoding="utf-8"), "complete input\n")
            self.assertTrue(Path(log_path).exists())
            self.assertEqual(progress[-1], (input_path.stat().st_size, input_path.stat().st_size))
            log_text = Path(log_path).read_text(encoding="utf-8")
            self.assertIn("Status: Geslaagd", log_text)
            self.assertIn("Duur seconden:", log_text)
            self.assertIn("Invoerbestand: input.txt", log_text)
            self.assertIn("Whitelist gebruikt: Ja", log_text)
            self.assertIn("Extra lijsten gebruikt: Patiëntenlijst", log_text)
            self.assertIn("Actieve filtergroepen:\n  - Namen (persoon/patiënt)\n", log_text)
            self.assertIn("Uitgeschakelde filtergroepen:\n  - Datums\n", log_text)
            self.assertIn("Deduce-vervangingen: 2", log_text)
            self.assertIn("Extra-lijstvervangingen: 4", log_text)
            self.assertIn("Totaal vervangingen: 6", log_text)
            self.assertNotIn(str(directory), log_text)
            self.assertNotIn("Sensitive medical term", log_text)
            self.assertEqual(
                phases,
                ["Tekst inlezen en anonimiseren", "Uitvoer en logbestand opslaan"],
            )

    def test_failed_run_does_not_leave_a_final_or_temporary_output(self):
        class FailingAnonymizer:
            def __init__(self, **_kwargs):
                pass

            def anonymize_stream(self, _lines, _stats):
                yield "partial output"
                raise RuntimeError("processing failed")

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.txt"
            output_dir = Path(directory) / "output"
            input_path.write_text("input\n", encoding="utf-8")
            settings = Settings(str(input_path), str(output_dir), None)

            with patch("src.hn_ano_tool.app.service.Anonymizer", FailingAnonymizer):
                with self.assertRaisesRegex(RuntimeError, "processing failed"):
                    MainController(settings).run()

            files = list(output_dir.iterdir())
            self.assertEqual(len(files), 1)
            self.assertIn("_log_", files[0].name)
            self.assertNotIn("_anonymized_", files[0].name)
            log_text = files[0].read_text(encoding="utf-8")
            self.assertIn("Status: Mislukt", log_text)
            self.assertIn("Foutcategorie: RuntimeError", log_text)
            self.assertIn("Foutmelding: processing failed", log_text)

    def test_cancelled_run_does_not_publish_partial_output(self):
        class TwoChunkAnonymizer:
            def __init__(self, **_kwargs):
                pass

            def anonymize_stream(self, _lines, _stats):
                yield "first chunk"
                yield "second chunk"

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.txt"
            output_dir = Path(directory) / "output"
            input_path.write_text("input\n", encoding="utf-8")
            cancel_event = threading.Event()
            settings = Settings(str(input_path), str(output_dir), None)

            def cancel_after_first_chunk(_processed, _total):
                cancel_event.set()

            with patch("src.hn_ano_tool.app.service.Anonymizer", TwoChunkAnonymizer):
                with self.assertRaises(ProcessingCancelled):
                    MainController(settings).run(
                        progress_callback=cancel_after_first_chunk,
                        cancel_event=cancel_event,
                    )

            files = list(output_dir.iterdir())
            self.assertEqual(len(files), 1)
            self.assertIn("_log_", files[0].name)
            self.assertNotIn("_anonymized_", files[0].name)
            self.assertIn(
                "Status: Geannuleerd",
                files[0].read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()