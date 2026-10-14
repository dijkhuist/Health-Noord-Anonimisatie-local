import tempfile
import unittest
from pathlib import Path

from src.hn_ano_tool.gui.preflight import validate_run_paths


class PreflightTests(unittest.TestCase):
    def test_valid_input_output_and_optional_lists_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "input.txt"
            whitelist_path = root / "whitelist.txt"
            input_path.write_text("text", encoding="utf-8")
            whitelist_path.write_text("term", encoding="utf-8")

            errors = validate_run_paths(
                str(input_path),
                directory,
                None,
                {"Whitelist": str(whitelist_path), "Patiëntenlijst": None},
            )

        self.assertEqual(errors, [])

    def test_missing_input_and_optional_file_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            errors = validate_run_paths(
                None,
                directory,
                None,
                {"Whitelist": str(Path(directory) / "missing.txt")},
            )

        self.assertIn("Invoerbestand: selecteer een bestand.", errors)
        self.assertIn("Whitelist: bestand bestaat niet of is geen bestand.", errors)

    def test_non_txt_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.csv"
            input_path.write_text("data", encoding="utf-8")
            errors = validate_run_paths(str(input_path), directory, None, {})

        self.assertIn(
            "Invoerbestand: alleen .txt-bestanden worden ondersteund.",
            errors,
        )


if __name__ == "__main__":
    unittest.main()