# extra_lists.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# import the existing helpers you already use today
from .utils import (
    merge_name_lists,
    build_name_alias_pattern_from_names,
    build_name_alias_pattern,
    build_namen_pattern,
)

# Keys that should be treated as "person name lists"
PERSON_KEYS = {
    "patient", "patiënt", "medewerker", "employee", "persoon", "persons"
}

# Keys that should be treated as "location lists"
LOCATION_KEYS = {
    "locatie", "locaties", "location", "locations"
}


@dataclass(frozen=True)
class ExtraListsConfig:
    """
    Normalized configuration for extra lists.

    - person_paths: 0..n files that contain names (patients, employees, etc.)
    - location_path: optional file with locations
    """
    person_paths: tuple[str, ...] = ()
    location_path: Optional[str] = None


def normalize_extra_lists(
    extra_names_path: str | None = None,
    extra_names_paths: dict[str, str] | None = None,
) -> ExtraListsConfig:
    """
    Converts all supported inputs into a normalized config.

    Backwards-compat rule:
      - If only extra_names_path is provided, treat it as a person list.
    """
    person_paths: list[str] = []
    location_path: Optional[str] = None

    if extra_names_paths:
        for k, p in extra_names_paths.items():
            if not p:
                continue

            k_norm = (k or "").strip().casefold()

            if k_norm in PERSON_KEYS:
                person_paths.append(p)
            elif k_norm in LOCATION_KEYS:
                location_path = p
            else:
                # Unknown keys: ignore by default to avoid surprising behavior.
                # If you want unknown keys to behave as person lists, uncomment:
                # person_paths.append(p)
                pass

    # Backwards compat: single path = person list
    if not person_paths and extra_names_path:
        person_paths.append(extra_names_path)

    return ExtraListsConfig(person_paths=tuple(person_paths), location_path=location_path)


def build_extra_name_patterns(cfg: ExtraListsConfig) -> dict[str, object]:
    """
    Builds the dict that anonymization uses:
      - "persoon" => NameAliasPattern (alias-aware)
      - "locatie" => re.Pattern (simple list)
    """
    patterns: dict[str, object] = {}

    # 1) Persons: merge multiple lists, build alias-aware pattern
    if cfg.person_paths:
        if len(cfg.person_paths) == 1:
            # single file path – keep behaviour close to existing code
            personen_pat = build_name_alias_pattern(
                cfg.person_paths[0],
                include_first=True,
                include_last=True,
                include_full=True,
                unique_only=True,
                min_alias_len=3,
            )
        else:
            merged_personen = merge_name_lists(*cfg.person_paths)
            personen_pat = build_name_alias_pattern_from_names(
                merged_personen,
                include_first=True,
                include_last=True,
                include_full=True,
                unique_only=True,
                min_alias_len=3,
            )

        if personen_pat:
            patterns["persoon"] = personen_pat

    # 2) Locations: simple list-pattern
    if cfg.location_path:
        loc_pat = build_namen_pattern(cfg.location_path)
        if loc_pat:
            patterns["locatie"] = loc_pat

    return patterns


def build_extra_patterns(
    extra_names_path: str | None = None,
    extra_names_paths: dict[str, str] | None = None,
) -> dict[str, object]:
    """
    Convenience wrapper to preserve current call sites.
    """
    cfg = normalize_extra_lists(extra_names_path=extra_names_path, extra_names_paths=extra_names_paths)
    return build_extra_name_patterns(cfg)
