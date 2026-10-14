from pathlib import Path
from typing import BinaryIO, Callable, Optional
import codecs
import os
import time

def read_text_smart(path: str) -> str:
    data = Path(path).read_bytes()

    # BOM-based detection
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")   # UTF-8 with BOM
    if data.startswith(b"\xff\xfe\x00\x00") or data.startswith(b"\x00\x00\xfe\xff"):
        return data.decode("utf-32")      # UTF-32 BOM
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16")      # UTF-16 BOM

    # Heuristic for BOM-less UTF-16/32
    head = data[:4096]
    if head:
        nul_ratio = head.count(b"\x00") / len(head)
        if nul_ratio > 0.20:
            if nul_ratio > 0.50:
                for enc in ("utf-32-le", "utf-32-be"):
                    try:
                        return data.decode(enc)
                    except UnicodeDecodeError:
                        pass
            for enc in ("utf-16-le", "utf-16-be"):
                try:
                    return data.decode(enc)
                except UnicodeDecodeError:
                    pass

    # UTF-8 strict, then fallbacks
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("cp1252")
        except UnicodeDecodeError:
            return data.decode("latin-1")
        

def validate_txt_path(path: str) -> Optional[str]:
    """
    Return None if `path` is an acceptable .txt file, otherwise a
    Dutch error message explaining why it was rejected.

    Policy: only .txt is accepted. A .csv/.7z/.exe is refused up front so
    we never silently mangle it (a CSV run as free text destroys its columns).
    """
    if not path.lower().endswith(".txt"):
        return "Alleen .txt-bestanden worden ondersteund (geen .csv, .7z, .exe, enz.)."
    return None


def _is_valid_utf8(head: bytes, rest: BinaryIO, block_size: int = 1 << 20) -> bool:
    """
    Check that `head` plus the remainder of `rest` is valid UTF-8. Decoding
    incrementally means a multi-byte character split across blocks is fine.
    """
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        decoder.decode(head)
        while block := rest.read(block_size):
            decoder.decode(block)
        decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        return False
    return True


def _detect_encoding(path: str, sample_size: int = 4096) -> str:
    """
    Sniff a file's text encoding: BOM + NUL heuristic on the first bytes, then
    UTF-8 validation of the WHOLE file (a sample alone can cut a character in
    half, or miss a cp1252 byte further on), falling back to cp1252.
    """
    with open(path, "rb") as f:
        head = f.read(sample_size)

        if head.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        if head.startswith(b"\xff\xfe\x00\x00") or head.startswith(b"\x00\x00\xfe\xff"):
            return "utf-32"
        if head.startswith(b"\xff\xfe") or head.startswith(b"\xfe\xff"):
            return "utf-16"

        if head:
            nul_ratio = head.count(b"\x00") / len(head)
            if nul_ratio > 0.50:
                return "utf-32"
            if nul_ratio > 0.20:
                return "utf-16"

        return "utf-8" if _is_valid_utf8(head, f) else "cp1252"
    

def iter_lines_smart(
    path: str,
    progress_callback: Callable[[int, int], None] | None = None,
):
    """
    Yield the file's lines one at a time (keeping their line endings), decoding with
    a sniffed encoding, so we never load the whole file into memory.
    """
    enc = _detect_encoding(path)
    total_bytes = os.path.getsize(path)
    bom_bytes = {"utf-8-sig": 3, "utf-16": 2, "utf-32": 4}.get(enc, 0)
    processed_bytes = min(total_bytes, bom_bytes)
    last_reported = time.monotonic()
    with open(path, "r", encoding=enc, errors="replace", newline="") as f:
        for line in f:
            if progress_callback:
                processed_bytes = min(
                    total_bytes,
                    processed_bytes + max(0, len(line.encode(enc, errors="replace")) - bom_bytes),
                )
                now = time.monotonic()
                if now - last_reported >= 0.25:
                    progress_callback(processed_bytes, total_bytes)
                    last_reported = now
            yield line

    if progress_callback:
        progress_callback(total_bytes, total_bytes)