from pathlib import Path
from typing import Optional

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


def _detect_encoding(path: str, sample_size: int = 4096) -> str:
    """
    Sniff a file's text encoding from its first bytes (BOM + NUL heuristic).
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
        
    try:
        head.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"
    

def iter_lines_smart(path: str):
    """
    Yield the file's lines one at a time (keeping their line endings), decoding with
    a sniffed encoding, so we never load the whole file into memory.
    """
    enc = _detect_encoding(path)
    with open(path, "r", encoding=enc, errors="replace", newline="") as f:
        for line in f:
            yield line