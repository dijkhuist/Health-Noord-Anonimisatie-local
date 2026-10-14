import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.hn_ano_tool.io import text_io


class TextIOProgressTests(unittest.TestCase):
    def test_progress_callback_counts_bytes_without_text_stream_tell(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.txt"
            path.write_bytes(b"one\ntwo\n")
            progress = []

            with patch.object(text_io.time, "monotonic", side_effect=[0.0, 1.0, 2.0]):
                lines = list(
                    text_io.iter_lines_smart(
                        str(path),
                        lambda processed, total: progress.append((processed, total)),
                    )
                )

        self.assertEqual(lines, ["one\n", "two\n"])
        self.assertEqual(progress, [(4, 8), (8, 8), (8, 8)])


class TextIOEncodingTests(unittest.TestCase):
    def _read(self, data: bytes) -> str:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.txt"
            path.write_bytes(data)
            return "".join(text_io.iter_lines_smart(str(path)))

    def test_utf8_character_split_by_sample_boundary_stays_utf8(self):
        text = "a" * 4095 + "é\nPatiënt Jansen\n"

        self.assertEqual(self._read(text.encode("utf-8")), text)

    def test_cp1252_byte_after_sample_is_not_replaced(self):
        text = "a" * 5000 + "\nPatiënt Jansen\n"

        self.assertEqual(self._read(text.encode("cp1252")), text)

    def test_valid_utf8_is_read_as_utf8(self):
        text = "Patiënt Jansen woont in Leeuwarden.\n" * 500

        self.assertEqual(self._read(text.encode("utf-8")), text)


if __name__ == "__main__":
    unittest.main()