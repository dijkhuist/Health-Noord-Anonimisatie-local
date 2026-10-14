from __future__ import annotations

import os
import tempfile


def _check_readable_txt(path: str, label: str, required: bool = False) -> list[str]:
    if not path:
        return [f"{label}: selecteer een bestand."] if required else []
    if not path.lower().endswith(".txt"):
        return [f"{label}: alleen .txt-bestanden worden ondersteund."]
    if not os.path.isfile(path):
        return [f"{label}: bestand bestaat niet of is geen bestand."]
    try:
        with open(path, "rb"):
            pass
    except OSError:
        return [f"{label}: bestand kan niet worden gelezen."]
    return []


def _check_writable_directory(path: str, label: str) -> list[str]:
    if not path or not os.path.isdir(path):
        return [f"{label}: selecteer een bestaande map."]

    descriptor = None
    probe_path = None
    try:
        descriptor, probe_path = tempfile.mkstemp(prefix=".hn_write_check_", dir=path)
    except OSError:
        return [f"{label}: map is niet beschrijfbaar."]
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if probe_path and os.path.exists(probe_path):
            os.remove(probe_path)
    return []


def validate_run_paths(
    input_file: str | None,
    output_dir: str | None,
    log_dir: str | None,
    optional_files: dict[str, str | None],
) -> list[str]:
    errors = _check_readable_txt(input_file or "", "Invoerbestand", required=True)
    errors.extend(_check_writable_directory(output_dir or "", "Uitvoermap"))
    if log_dir:
        errors.extend(_check_writable_directory(log_dir, "Logmap"))
    for label, path in optional_files.items():
        errors.extend(_check_readable_txt(path or "", label))
    return errors