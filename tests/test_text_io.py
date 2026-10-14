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


if __name__ == "__main__":
    unittest.main()