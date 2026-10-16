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
    lines = (clean_list_line(line) for line in text.splitlines())
    return [line for line in lines if line]


# Invisible characters that often end up in lists copied from Word, Excel or e-mail:
# zero-width (non-)joiners/spaces, word joiner, soft hyphen, BOM, direction marks.
_INVISIBLE_CHARS = dict.fromkeys(
    map(ord, "​‌‍⁠­﻿‎‏‪‫‬‭‮"),
    None,
)


def clean_list_line(line: str) -> str:
    """
    Drop invisible characters, turn non-breaking and other special spaces into
    normal spaces and strip the line, so "talko\\u00a0" in a list still matches "Talko".
    """
    line = line.translate(_INVISIBLE_CHARS)
    line = "".join(" " if char.isspace() or not char.isprintable() else char for char in line)
    return " ".join(line.split())


# Separators (spaces, line breaks, hyphens) and apostrophe variants are treated as
# equal, so "Den Haag" also matches "DEN  HAAG", "Sint Oedenrode" "sint-oedenrode"
# and "'s-Hertogenbosch" "’S HERTOGENBOSCH".
_SEPARATORS = r"[\s\-‐‑–]+"
_APOSTROPHES = "'’‘`´"


def term_key(term: str) -> str:
    """Case-, separator- and apostrophe-insensitive key for a list term or a match."""
    for apostrophe in _APOSTROPHES[1:]:
        term = term.replace(apostrophe, "'")
    return re.sub(_SEPARATORS, " ", term).strip().casefold()


def flexible_term_regex(term: str) -> str:
    """Regex for a list term that tolerates any separator / apostrophe variant."""
    apostrophe_class = "[" + re.escape(_APOSTROPHES) + "]"
    parts = []
    for part in term_key(term).split(" "):
        parts.append(apostrophe_class.join(re.escape(piece) for piece in part.split("'")))
    return _SEPARATORS.join(parts)


# Not inside a word. Quotes and a possessive "'s" around a term do not block a match.
_TERM_START = r"(?<!\w)"
_TERM_END = r"(?!\w)"

# =============================================================================
# Simple list-pattern (legacy / locations)
# =============================================================================

def build_namen_pattern(pad: Optional[Union[str, Path]]) -> Optional[re.Pattern]:
    """
    Legacy builder: maakt 1 regex pattern uit een tekstbestand (1 term per regel).
    Goed voor locaties/instellingen/etc.

    Let op: dit is *niet* alias-aware (geen mapping voor consistente pseudoniemen).
    """
    namen = {term_key(name): name for name in _read_lines_smart(pad)}
    namen.pop("", None)
    if not namen:
        return None

    # Longest first, so "Den Haag" wins over "Haag". A street also takes the house
    # number after it ("Hendrik de Vosweg 258-K"), which Deduce no longer sees once the
    # street itself is replaced.
    alternatives = [
        flexible_term_regex(key) + (_HOUSE_NUMBER if _is_street(key) else "")
        for key in sorted(namen, key=len, reverse=True)
    ]
    pattern = re.compile(
        _TERM_START + "(" + "|".join(alternatives) + ")" + _TERM_END,
        flags=re.IGNORECASE,
    )
    return pattern


_STREET_SUFFIXES = (
    "straat", "str", "str.", "weg", "laan", "singel", "plein", "kade", "gracht", "dijk",
    "pad", "hof", "dreef", "steeg", "park", "wal", "markt", "baan", "plantsoen", "allee",
    "boulevard", "promenade",
)  # not "dam", "veld", ...: "Amsterdam 2024" is a place and a year, not an address

# "12", "12a", "12 A", "12-2", "258-K", "12/3" after a street name.
_HOUSE_NUMBER = r"(?:\s+\d{1,5}(?:(?-i:[a-zA-Z]{1,2})\b|\s(?-i:[A-Z])\b|\s?[-/]\s?[A-Za-z0-9]{1,4})?)?"
_HOUSE_NUMBER_TAIL = re.compile(r"\s+\d[\w\s\-/]*$")


def _is_street(key: str) -> bool:
    return key.split(" ")[-1].endswith(_STREET_SUFFIXES)


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
        key = term_key(original)

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
    # "Broek - Zoon" is one double surname, not "Broek -" plus "Zoon".
    s = re.sub(r"\s*[-‐‑–]\s*", "-", s)
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
    ambiguous_aliases: aliassen die NIET uniek waren; die worden wel vervangen, maar met
        een eigen pseudoniem omdat niet vaststaat welke persoon bedoeld is
    capitalized_only: losse voor-/achternamen en namen van één woord (tussenvoegsels
        niet meegeteld); die tellen alleen als een woord buiten de tussenvoegsels met een
        hoofdletter in de tekst staat, zodat "Arts" of "de Goede" niet ook het gewone
        "arts" of "de goede" vervangt
    common_words: achternamen en namen van één woord die ook een gewoon woord zijn
        ("Anders", "Linker"); die tellen niet aan het begin van een zin, waar elk woord
        een hoofdletter heeft (zie set_common_words)
    first_names: voornamen uit een volledige naam ("Wil" uit "Wil Bakker"); die worden
        ook aan het begin van een zin vervangen, want zorgnotities beginnen vaak zo
    """
    pattern: Pattern[str]
    alias_to_canonical: dict[str, str]
    ambiguous_aliases: set[str] = field(default_factory=set)
    capitalized_only: set[str] = field(default_factory=set)
    common_words: set[str] = field(default_factory=set)
    first_names: set[str] = field(default_factory=set)

    def set_common_words(self, is_common_word) -> None:
        """
        Mark one-word names that are everyday words: those in COMMON_WORDS, and other
        names (not first names) for which `is_common_word(key)` is true. So "Wil" from
        "Wil Bakker" stays a name at a sentence start, "Nieuwe" or "Linker" does not.
        """
        self.common_words = {
            alias
            for alias in self.capitalized_only
            if " " not in alias
            and (alias in COMMON_WORDS or (alias not in self.first_names and is_common_word(alias)))
        }


# Everyday words that Deduce's common-word list lacks (mostly inflected forms) but that
# also occur as surnames and often start a sentence in care notes.
COMMON_WORDS = {
    "linker", "rechter", "nieuw", "nieuwe", "oude", "grote", "kleine", "goede", "andere",
    "eerste", "laatste", "volgende", "vorige", "beide", "lange", "korte", "hoge", "lage",
    "witte", "zwarte", "rode", "bruine", "groene", "verder", "daarna", "vervolgens",
    "vandaag", "gisteren", "morgen", "vanmorgen", "vanmiddag", "vanavond", "vannacht",
    "klein", "groot", "boven", "beneden", "binnen", "buiten", "voor", "achter", "midden",
}


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
    full_keys: set[str] = set()
    first_name_keys: set[str] = set()

    for raw in names:
        canonical, first_part, last_part = split_dutch_full_name(str(raw))
        if not canonical:
            continue
        full_keys.add(term_key(canonical))
        if first_part and last_part:  # a real first name, not a one-word entry
            first_name_keys.add(term_key(first_part))

        if include_full and len(canonical) >= min_alias_len:
            alias_to_canonicals[term_key(canonical)].add(canonical)

        if include_first and first_part and len(first_part) >= min_alias_len:
            alias_to_canonicals[term_key(first_part)].add(canonical)

        if include_last and last_part and len(last_part) >= min_alias_len:
            alias_to_canonicals[term_key(last_part)].add(canonical)

    if not alias_to_canonicals:
        return None

    alias_to_canonical: dict[str, str] = {}
    ambiguous: set[str] = set()

    for alias_cf, cset in alias_to_canonicals.items():
        # "Jan de Vries" and "JAN DE VRIES" in the lists are one and the same person.
        cset = {min(group) for group in _group_by_key(cset).values()}
        if unique_only and len(cset) != 1:
            # Shared by several people ("Wil" for Wil Bakker and Wil de Jong): still
            # anonymize it, with its own pseudonym, rather than leave the name standing.
            ambiguous.add(alias_cf)
            alias_to_canonical[alias_cf] = alias_cf
            continue
        alias_to_canonical[alias_cf] = sorted(cset)[0]

    if not alias_to_canonical:
        return None

    # langste eerst zodat "Jan Jansen" vóór "Jan" matcht
    aliases = sorted(alias_to_canonical.keys(), key=len, reverse=True)

    # boundary: niet matchen binnen woorden
    alts = "|".join(flexible_term_regex(a) for a in aliases)
    pat = re.compile(rf"{_TERM_START}(?:{alts}){_TERM_END}", flags=re.IGNORECASE)

    return NameAliasPattern(
        pattern=pat,
        alias_to_canonical=alias_to_canonical,
        ambiguous_aliases=ambiguous,
        capitalized_only={
            alias
            for alias in alias_to_canonical
            if alias not in full_keys or len(_core_words(alias)) <= 1
        },
        first_names=first_name_keys & set(alias_to_canonical),
    )


def _core_words(name: str) -> list[str]:
    """The words of a name without tussenvoegsels ("van den Broek-Zoon" -> Broek, Zoon)."""
    return [
        word
        for word in re.split(_SEPARATORS, name.strip())
        if word and word.casefold() not in TUSSENVOEGSELS_CF
    ]


def _has_capitalized_core(raw: str) -> bool:
    return any(word[:1].isupper() for word in _core_words(raw))


def _group_by_key(values: Iterable[str]) -> dict[str, set[str]]:
    groups: dict[str, set[str]] = defaultdict(set)
    for value in values:
        groups[term_key(value)].add(value)
    return groups


def vervang_gemiste_namen_typed_with_aliases(
    text,
    namepat: Optional[NameAliasPattern],
    entity_type: str,
    ctx: ExtraNamesContext,
    at_text_start: bool = True,
):
    """
    Vervangt matches door <TYPE_###>, maar normaliseert aliassen terug naar 1 canonical
    zodat dezelfde persoon hetzelfde pseudoniem krijgt (voor zover alias uniek is).

    at_text_start: of het begin van `text` ook het begin van een zin/regel is (False
    voor tekst direct na een code als "[DATUM-1]").
    """
    if namepat is None or is_na(text):
        return text

    out = str(text)
    t_norm = ctx.normalize_type(entity_type)

    def repl(m: re.Match[str]) -> str:
        canonical = _alias_canonical(namepat, out, m, at_text_start)
        if canonical is None:
            return m.group(0)
        ctx.occurrences[t_norm] += 1
        return ctx.pseudonym_for(t_norm, canonical)

    return namepat.pattern.sub(repl, out)


def _alias_canonical(
    namepat: NameAliasPattern, text: str, m: re.Match[str], at_text_start: bool
) -> Optional[str]:
    """The canonical name for match `m`, or None when it is a normal word, not the name."""
    raw = m.group(0)
    key = term_key(raw)
    if key in namepat.capitalized_only and not _has_capitalized_core(raw):
        return None  # "arts", "de goede", "De heer": normal words, not the listed name
    if key in namepat.common_words and _at_sentence_start(text, m.start(), at_text_start):
        return None  # "Anders ging het goed.": the capital comes from the sentence start
    return namepat.alias_to_canonical.get(key, raw)


def _at_sentence_start(text: str, position: int, at_text_start: bool) -> bool:
    """True when only quotes, brackets or bullets stand between `position` and the
    start of the text, a line or field break, or a sentence-ending punctuation mark."""
    before = text[:position].rstrip(" \"'(‘“*•-–")
    if not before:
        return at_text_start
    if before[-1] == ".":
        # "mevr. Anders", "dhr. Linker", "J. Anders": a title or initial, not a sentence end.
        previous_word = re.split(r"\s", before)[-1].casefold()
        if previous_word in TITLE_WORDS_CF or re.fullmatch(r"(?:\w\.)+", previous_word):
            return False
    return before[-1] in ".!?:;\n\r\t"


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
            key = term_key(canonical)
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

    All lists are matched in one pass and the longest match wins, so the street
    "Harmen Systrasingel" from the location list beats the first name "Harmen" from a
    name list. On equal length the type earlier in `order` wins. Existing codes are
    never touched.
    """
    if is_na(text):
        return text

    out = str(text)
    types = order if order is not None else list(patterns_by_type.keys())
    code_spans = [m.span() for m in _CODE_PATTERN.finditer(out)]

    candidates = []
    for rank, t in enumerate(types):
        pat = patterns_by_type.get(t)
        if pat is None:
            continue
        regex = pat.pattern if isinstance(pat, NameAliasPattern) else pat
        for m in regex.finditer(out):
            start, end = m.span()
            if any(a < end and start < b for a, b in code_spans):
                continue
            if isinstance(pat, NameAliasPattern):
                canonical = _alias_canonical(pat, out, m, True)
                if canonical is None:
                    continue
            else:
                canonical = _HOUSE_NUMBER_TAIL.sub("", m.group(0))  # one street, one code
            candidates.append((start, start - end, rank, end, t, canonical))

    pieces, position = [], 0
    for start, _negative_length, _rank, end, t, canonical in sorted(candidates):
        if start < position:
            continue  # overlaps a longer (or earlier) match
        t_norm = ctx.normalize_type(t)
        ctx.occurrences[t_norm] += 1
        pieces.append(out[position:start])
        pieces.append(ctx.pseudonym_for(t_norm, canonical))
        position = end
    pieces.append(out[position:])
    return "".join(pieces)


# Codes already in the text: Deduce's "[PERSOON-1]" and the extra lists' "<PERSOON_001>".
_CODE_PATTERN = re.compile(r"\[[A-Z_]+-\d+\]|<[A-Z_]+_\d{3,}>")
