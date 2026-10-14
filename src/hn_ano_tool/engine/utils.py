# anonymizer/utils.py
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import (
    Union,
    Optional,
    Pattern,
    Iterable,
)
from dataclasses import dataclass, field
from collections import defaultdict

import math

from src.hn_ano_tool.io.text_io import read_text_smart


# =============================================================================
# Basic helpers
# =============================================================================

def is_na(value) -> bool:
    # None
    if value is None:
        return True
    # NaN (float)
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def open_json(path: Union[str, Path]):
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def make_range(age: int, step: int = 10) -> str:
    low = (age // step) * step
    high = low + step
    return f"{low}-{high}"


def _read_lines_smart(pad: Optional[Union[str, Path]]) -> list[str]:
    """
    Read non-empty, stripped lines from a .txt list, tolerating BOM / UTF-16 / cp1252
    (reuses read_text_smart so extra-list files aren't limited to strict UTF-8).
    """
    if not pad:
        return []
    p = Path(pad)
    if not p.exists():
        return []
    text = read_text_smart(str(p))
    return [line.strip() for line in text.splitlines() if line.strip()]

# =============================================================================
# Simple list-pattern (legacy / locations)
# =============================================================================

def build_namen_pattern(pad: Optional[Union[str, Path]]) -> Optional[re.Pattern]:
    """
    Legacy builder: maakt 1 regex pattern uit een tekstbestand (1 term per regel).
    Goed voor locaties/instellingen/etc.

    Let op: dit is *niet* alias-aware (geen mapping voor consistente pseudoniemen).
    """
    namen = _read_lines_smart(pad)
    if not namen:
        return None

    pattern = re.compile(
        r"\b(" + "|".join(re.escape(name) for name in namen) + r")\b",
        flags=re.IGNORECASE,
    )
    return pattern


def vervang_gemiste_namen(text, pattern: Optional[re.Pattern] = None, label: str = "[PERSOON]"):
    """
    Vervang matches door een vaste label.
    (Meestal niet wat je wil voor personen als je consistente pseudoniemen wil.)
    """
    if pattern is None or is_na(text):
        return text
    text = str(text)
    return pattern.sub(label, text)


# =============================================================================
# Pseudonym context (consistent within one run)
# =============================================================================

@dataclass
class ExtraNamesContext:
    """
    Houdt mapping bij zodat dezelfde naam binnen een run steeds hetzelfde pseudoniem krijgt.

    Voorbeeld:
      "Jan Jansen" -> <PERSOON_001> (blijft dat overal in de tekst)
    """
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    mapping: dict[str, dict[str, str]] = field(default_factory=lambda: defaultdict(dict))
    occurrences: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def normalize_type(self, entity_type: str) -> str:
        t = (entity_type or "persoon").strip().casefold()

        # Alles wat "persoon-achtig" is → persoon
        if t in {"patient", "patiënt", "medewerker", "employee", "persoon", "persons"}:
            return "persoon"

        # Alles wat "locatie-achtig" is → locatie
        if t in {"locatie", "locaties", "location", "locations"}:
            return "locatie"

        # fallback: laat onbekende types bestaan, of kies hier ook "persoon" als je strikter wil zijn
        return t


    def pseudonym_for(self, entity_type: str, original: str) -> str:
        t = self.normalize_type(entity_type)
        key = original.strip().casefold()

        if key in self.mapping[t]:
            return self.mapping[t][key]

        self.counters[t] += 1
        pseudo = f"<{t.upper()}_{self.counters[t]:03d}>"
        self.mapping[t][key] = pseudo
        return pseudo


def vervang_gemiste_namen_typed(
    text,
    pattern: Optional[Pattern[str]],
    entity_type: str,
    ctx: ExtraNamesContext,
):
    """
    Vervangt matches door <TYPE_###> op basis van entity_type.
    Werkt met een plain re.Pattern.
    """
    if pattern is None or is_na(text):
        return text

    out = str(text)
    t_norm = ctx.normalize_type(entity_type)

    def repl(m: re.Match[str]) -> str:
        ctx.occurrences[t_norm] += 1
        return ctx.pseudonym_for(t_norm, m.group(0))

    return pattern.sub(repl, out)


def vervang_gemiste_namen_multi(
    text,
    patterns_by_type: dict[str, Pattern[str]],
    ctx: ExtraNamesContext,
    order: Optional[list[str]] = None,
):
    """
    Multi replace (legacy): verwacht dict[type] -> re.Pattern.
    """
    if is_na(text):
        return text

    out = str(text)
    types = order if order is not None else list(patterns_by_type.keys())

    for t in types:
        pat = patterns_by_type.get(t)
        if pat is not None:
            out = vervang_gemiste_namen_typed(out, pat, t, ctx)

    return out


# =============================================================================
# Alias-aware persons (full name + (unique) first/last)
# =============================================================================

TITLE_WORDS = {
    "dhr", "dhr.", "deheer",
    "mevr", "mevr.", "mw", "mw.",
    "dr", "dr.", "ir", "ir.", "ing", "ing.",
    "mr", "mr.", "prof", "prof.",
}
TITLE_WORDS_CF = {t.casefold() for t in TITLE_WORDS}

# Veelvoorkomende NL tussenvoegsels
TUSSENVOEGSELS = {
    "van", "de", "der", "den", "ten", "ter",
    "van de", "van der", "van den", "van het", "in 't", "'t", "’t",
    "op", "aan", "bij", "onder", "over", "voor", "uit",
}
TUSSENVOEGSELS_CF = {tv.casefold() for tv in TUSSENVOEGSELS}


def _normalize_spaces(s: str) -> str:
    s = s.replace("’", "'")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _maybe_swap_comma_name(s: str) -> str:
    # "Jansen, Jan" -> "Jan Jansen"
    if "," in s:
        left, right = [p.strip() for p in s.split(",", 1)]
        if right and left:
            return f"{right} {left}".strip()
    return s


def split_dutch_full_name(raw: str) -> tuple[str, str, str]:
    """
    Returns: (canonical_full, first_part, last_part)

    - ondersteunt "Achternaam, Voornaam"
    - verwijdert veelvoorkomende titels aan begin
    - achternaam = laatste token + eventuele tussenvoegsels vlak ervoor
    """
    s = _normalize_spaces(raw)
    s = _maybe_swap_comma_name(s)
    s = _normalize_spaces(s)

    if not s:
        return ("", "", "")

    tokens = s.split(" ")

    # strip titles at start
    while tokens and tokens[0].casefold() in TITLE_WORDS_CF:
        tokens = tokens[1:]

    if len(tokens) == 0:
        return ("", "", "")

    if len(tokens) == 1:
        only = tokens[0]
        return (only, only, "")

    # last name tokens (incl tussenvoegsels)
    i = len(tokens) - 1
    last_tokens = [tokens[i]]
    i -= 1

    while i >= 0:
        cand1 = tokens[i].casefold()
        cand2 = f"{tokens[i].casefold()} {last_tokens[0].casefold()}"

        if cand2 in TUSSENVOEGSELS_CF:
            last_tokens.insert(0, tokens[i])
            i -= 1
            continue
        if cand1 in TUSSENVOEGSELS_CF:
            last_tokens.insert(0, tokens[i])
            i -= 1
            continue
        break

    first_tokens = tokens[: i + 1]
    first_part = " ".join(first_tokens).strip()
    last_part = " ".join(last_tokens).strip()
    canonical = _normalize_spaces(f"{first_part} {last_part}".strip())
    return (canonical, first_part, last_part)


@dataclass
class NameAliasPattern:
    """
    pattern: regex die aliassen matcht (full name + eventueel unieke voornaam/achternaam)
    alias_to_canonical: alias -> canonical full name
    ambiguous_aliases: aliassen die NIET uniek waren en daarom niet gebruikt zijn
    """
    pattern: Pattern[str]
    alias_to_canonical: dict[str, str]
    ambiguous_aliases: set[str] = field(default_factory=set)


def build_name_alias_pattern(
    pad: Optional[Union[str, Path]],
    include_first: bool = True,
    include_last: bool = True,
    include_full: bool = True,
    unique_only: bool = True,
    min_alias_len: int = 3,
) -> Optional[NameAliasPattern]:
    """
    Leest een namenbestand met full names (1 per regel) en bouwt:
      - een regex pattern dat full names én (optioneel) unieke voornamen/achternamen matcht
      - alias->canonical mapping
    """
    lines = _read_lines_smart(pad)
    if not lines:
        return None

    return build_name_alias_pattern_from_names(
        lines,
        include_first=include_first,
        include_last=include_last,
        include_full=include_full,
        unique_only=unique_only,
        min_alias_len=min_alias_len,
    )


def build_name_alias_pattern_from_names(
    names: Iterable[str],
    include_first: bool = True,
    include_last: bool = True,
    include_full: bool = True,
    unique_only: bool = True,
    min_alias_len: int = 3,
) -> Optional[NameAliasPattern]:
    """
    Zelfde als build_name_alias_pattern(), maar input is een iterable van (raw) full names
    i.p.v. een pad.
    """
    names = [n for n in names if n and str(n).strip()]
    if not names:
        return None

    alias_to_canonicals: dict[str, set[str]] = defaultdict(set)

    for raw in names:
        canonical, first_part, last_part = split_dutch_full_name(str(raw))
        if not canonical:
            continue

        if include_full and len(canonical) >= min_alias_len:
            alias_to_canonicals[canonical.casefold()].add(canonical)

        if include_first and first_part and len(first_part) >= min_alias_len:
            alias_to_canonicals[first_part.casefold()].add(canonical)

        if include_last and last_part and len(last_part) >= min_alias_len:
            alias_to_canonicals[last_part.casefold()].add(canonical)

    if not alias_to_canonicals:
        return None

    alias_to_canonical: dict[str, str] = {}
    ambiguous: set[str] = set()

    for alias_cf, cset in alias_to_canonicals.items():
        if unique_only and len(cset) != 1:
            ambiguous.add(alias_cf)
            continue
        alias_to_canonical[alias_cf] = sorted(cset)[0]

    if not alias_to_canonical:
        return None

    # langste eerst zodat "Jan Jansen" vóór "Jan" matcht
    aliases = sorted(alias_to_canonical.keys(), key=len, reverse=True)

    # boundary: niet matchen binnen woorden
    namechar = r"[\w'’]"
    alts = "|".join(re.escape(a) for a in aliases)
    pat = re.compile(rf"(?<!{namechar})(?:{alts})(?!{namechar})", flags=re.IGNORECASE)

    return NameAliasPattern(pattern=pat, alias_to_canonical=alias_to_canonical, ambiguous_aliases=ambiguous)


def vervang_gemiste_namen_typed_with_aliases(
    text,
    namepat: Optional[NameAliasPattern],
    entity_type: str,
    ctx: ExtraNamesContext,
):
    """
    Vervangt matches door <TYPE_###>, maar normaliseert aliassen terug naar 1 canonical
    zodat dezelfde persoon hetzelfde pseudoniem krijgt (voor zover alias uniek is).
    """
    if namepat is None or is_na(text):
        return text

    out = str(text)
    t_norm = ctx.normalize_type(entity_type)

    def repl(m: re.Match[str]) -> str:
        raw = m.group(0)
        canonical = namepat.alias_to_canonical.get(raw.casefold(), raw)
        ctx.occurrences[t_norm] += 1
        return ctx.pseudonym_for(t_norm, canonical)

    return namepat.pattern.sub(repl, out)


# =============================================================================
# Merge multiple person lists (patients + employees) into one in-memory list
# =============================================================================

def _read_names_file_canonical(path: Union[str, Path]) -> list[str]:
    """
    Leest 1 namenbestand (1 per regel) en normaliseert naar canonical full name.
    Ondersteunt ook 'Achternaam, Voornaam'.
    """
    out: list[str] = []
    for raw in _read_lines_smart(path):
        canonical, _, _ = split_dutch_full_name(raw)
        if canonical:
            out.append(canonical)
    return out


def merge_name_lists(*paths: Optional[Union[str, Path]]) -> list[str]:
    """
    Merge meerdere namenlijsten tot 1 lijst (deduped, stabiele volgorde).
    Dedup gebeurt op canonical.casefold().
    """
    merged: list[str] = []
    seen: set[str] = set()

    for p in paths:
        if not p:
            continue
        for canonical in _read_names_file_canonical(p):
            key = canonical.casefold()
            if key in seen:
                continue
            seen.add(key)
            merged.append(canonical)

    return merged


# =============================================================================
# Multi replace that supports both Pattern and NameAliasPattern
# =============================================================================

ExtraPattern = Union[Pattern[str], NameAliasPattern]


def vervang_gemiste_namen_multi_any(
    text,
    patterns_by_type: dict[str, ExtraPattern],
    ctx: ExtraNamesContext,
    order: Optional[list[str]] = None,
):
    """
    Multi replace die zowel:
      - re.Pattern (legacy, bv locaties)
      - NameAliasPattern (alias-aware, bv personen)
    ondersteunt.
    """
    if is_na(text):
        return text

    out = str(text)
    types = order if order is not None else list(patterns_by_type.keys())

    for t in types:
        pat = patterns_by_type.get(t)
        if pat is None:
            continue

        if isinstance(pat, NameAliasPattern):
            out = vervang_gemiste_namen_typed_with_aliases(out, pat, t, ctx)
        else:
            out = vervang_gemiste_namen_typed(out, pat, t, ctx)

    return out
