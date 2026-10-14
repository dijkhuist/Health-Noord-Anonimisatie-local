from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def preferences_path() -> Path:
    local_app_data = Path(
        os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    )
    return local_app_data / "HealthNoord" / "AnonymisatieTool" / "preferences.json"


def load_preferences() -> dict[str, object]:
    try:
        with preferences_path().open("r", encoding="utf-8") as preferences_file:
            data = json.load(preferences_file)
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(data, dict):
        return {}

    disabled_groups = data.get("disabled_groups", [])
    if not isinstance(disabled_groups, list):
        disabled_groups = []
    if "whitelist_path" in data:
        save_preferences(set(disabled_groups))
    return {
        "disabled_groups": disabled_groups,
    }


def save_preferences(disabled_groups: set[str]) -> None:
    path = preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"disabled_groups": sorted(disabled_groups)}
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".preferences_",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as preferences_file:
            json.dump(data, preferences_file, ensure_ascii=True, indent=2)
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)