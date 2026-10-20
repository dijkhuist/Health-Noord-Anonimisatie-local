import os
import re
import sys
from pathlib import Path
from collections import defaultdict

from .deduce_adapter import get_deduce
from .stats import RunStats, compute_stats
from .extra_lists import (
    build_extra_patterns,
    build_whitelist_pattern,
    extra_list_terms,
    normalize_extra_lists,
    protect_whitelist_terms,
    restore_whitelist_terms,
)

from src.hn_ano_tool.engine.utils import (
    COMMON_WORDS,
    ExtraNamesContext,
    NameAliasPattern,
    is_street,
    vervang_gemiste_namen_multi_any,
)


def _deduce_common_word_check(deduce):
    """
    Membership test for Deduce's own whitelist (common Dutch words, stop words and
    medical terms). Falls back to "nothing is common" if the structure is missing.
    """
    try:
        words = deduce.lookup_structs["whitelist"]
        return lambda word: word in words
    except (AttributeError, KeyError, TypeError):
        return lambda word: False


# Pseudonyms the extra lists insert, e.g. "<PERSOON_001>".
_PSEUDONYM_PATTERN = re.compile(r"<[A-Z_]+_\d{3,}>")

# Dutch postcode with the letters "MG" in capitals; Deduce leaves these out.
_MG_POSTCODE = re.compile(r"(?<![\w-])[1-9]\d{3} ?MG(?!\w)")

# A day and month without a year ("9 mei", "27 okt."); Deduce only finds dates with a year.
_DATE_WITHOUT_YEAR = re.compile(
    r"(?<![\w-])(?:[1-9]|[12]\d|3[01])\s+"
    r"(?:januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december"
    r"|jan|feb|mrt|apr|jun|jul|aug|sep|sept|okt|nov|dec)(?:\.|(?!\w))",
    re.IGNORECASE,
)


def runtime_resource_path(relative_path: str) -> str:
    base_path = getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])
    return os.path.join(base_path, relative_path)


class DeduceRedactor:
    """
    Turns Deduce annotations into [TAG-n] codes, giving the SAME code to the
    same (tag, text) every time (including across as many chunks as we feed it.)
    """

    def __init__(self):
        self.counters = defaultdict(int)    # tag -> how many distinct values seen
        self.mapping = {}

    def code_for(self, tag, text):
        key = (tag, text)
        if key in self.mapping:
            return self.mapping[key]        # seen before -> reuse its code
        self.counters[tag] += 1
        code = f"[{tag.upper()}-{self.counters[tag]}]"
        self.mapping[key] = code
        return code
    
    def redact(self, text, annotations):
        # 1) assign numbers in document order (so [PERSOON-1] is the first one)
        anns = sorted(annotations, key=lambda a: a.start_char)
        codes = [self.code_for(a.tag, a.text) for a in anns]
        # 2) splice replacements in from the END, so earlier offsets stay valid
        for a, code in sorted(zip(anns, codes), key=lambda p: p[0].start_char, reverse=True):
            text = text[:a.start_char] + code + text[a.end_char:]
        return text

class Anonymizer:
    def __init__(
        self,
        enabled: set[str] = None,
        disabled: set[str] = None,
        extra_names_path: str | None = None,
        extra_names_paths: dict[str, str] | None = None,
        whitelist_path: str | None = None,
    ):
        self.enabled = enabled
        self.disabled = disabled
        self.deduce = get_deduce()

        # Patterns:
        #  - "persoon" => NameAliasPattern (alias-aware)
        #  - "locatie" => re.Pattern (simple list)
        self.extra_names_patterns = build_extra_patterns(
            extra_names_path=extra_names_path,
            extra_names_paths=extra_names_paths,
        )
        is_common_word = _deduce_common_word_check(self.deduce)
        persons = self.extra_names_patterns.get("persoon")
        if isinstance(persons, NameAliasPattern):
            persons.set_common_words(is_common_word)
        # A term that is in an extra list is anonymized even if whitelisted, except a
        # one-word term that is also an everyday word ("Kamer", "Zondag"): there the
        # whitelist wins, so such words can be kept by whitelisting them.
        listed_terms = {
            term
            for term in extra_list_terms(
                normalize_extra_lists(extra_names_path=extra_names_path, extra_names_paths=extra_names_paths)
            )
            if " " in term or not (term in COMMON_WORDS or is_common_word(term))
        }
        self.whitelist_pattern = build_whitelist_pattern(whitelist_path, exclude=listed_terms)



    def anonymize(self, text: str) -> tuple[str, RunStats]:
        """
        Whole-string convenience wrapper: collect the streamed output into one string.
        """
        stats = RunStats()
        out = "".join(self.anonymize_stream(text.splitlines(keepends=True), stats))
        return out, stats
    
    def anonymize_stream(self, lines, stats: RunStats):
        """
        Stream anonymization: take an iterable of input LINES, yield anonymized output
        chunks one at a time and accumulate tag counts into `stats`. One shared redactor
        and context span the whole stream, so codes stay consistent across every chunk.
        """
        redactor = DeduceRedactor()
        extra_ctx = ExtraNamesContext()

        for chunk in self._iter_chunks_from_lines(lines):
            yield self._process_chunk(chunk, redactor, extra_ctx, stats)

        for t, count in extra_ctx.occurrences.items():
            stats.by_type[f"extra {t}"] = stats.by_type.get(f"extra {t}", 0) + int(count)

    def _iter_chunks(self, text: str, max_chars: int = 50_000):
        """
        Whole-string convenience wrapper around _iter_chunks_from_lines.
        """
        yield from self._iter_chunks_from_lines(text.splitlines(keepends=True), max_chars)

    def _iter_chunks_from_lines(self, lines, max_chars: int = 50_000):
        """
        Group an iterable of LINES into piece of ~max_chars, never splitting a line.
        Taking a line *iterator* (not a whole string) is what lets us stream.

        50_000 is a measured sweet spot: Deduce's cost grows faster than linearly with
        chunk length, so smaller chunks run much faster (but below ~50k the per-chunk
        overhead eats the gains). ~9x faster than 1_000_000 on dense text.
        """
        buf, size = [], 0
        for line in lines:
            buf.append(line)
            size += len(line)
            if size >= max_chars:
                yield "".join(buf)
                buf, size = [], 0
        if buf:
            yield "".join(buf)

    def _street_spans(self, text) -> list[tuple[int, int]]:
        """
        Spans of streets from Deduce's street list (BAG) that end in a street suffix,
        such as "Prins Willem-Alexanderstraat". A street that is just a name
        ("Jan Steen") is left out, so it never shields a listed person.
        Skipped when locations are not anonymized, or if Deduce lacks the structures.
        """
        if "locations" in (self.disabled or set()):
            return []
        try:
            streets = self.deduce.lookup_structs["street"]
            tokens = list(self.deduce.tokenizers["default"].tokenize(text))
        except (AttributeError, KeyError, TypeError):
            return []

        words = [token.text for token in tokens]
        spans = []
        for i in range(len(tokens)):
            match = streets.longest_matching_prefix(words[i:])
            if match:
                start, end = tokens[i].start_char, tokens[i + len(match) - 1].end_char
                if is_street(text[start:end]):
                    spans.append((start, end))
        return spans

    def _redact_mg_postcodes(self, text, redactor, stats) -> str:
        """
        Deduce skips postcodes ending in "MG" (it reads them as milligrams). Treat four
        digits plus a capital "MG" ("9257MG", "9257 MG") as a postcode; a lowercase
        "1000 mg" stays a dose.
        """
        if "locations" in (self.disabled or set()):
            return text

        def replace(match):
            stats.by_type["locatie"] = stats.by_type.get("locatie", 0) + 1
            return redactor.code_for("locatie", match.group(0))

        return _MG_POSTCODE.sub(replace, text)

    def _redact_dates_without_year(self, text, redactor, stats) -> str:
        """Replace "9 mei" / "27 okt." with a date code; Deduce needs a year to see a date."""
        if "dates" in (self.disabled or set()):
            return text

        def replace(match):
            stats.by_type["datum"] = stats.by_type.get("datum", 0) + 1
            return redactor.code_for("datum", match.group(0))

        return _DATE_WITHOUT_YEAR.sub(replace, text)

    def _process_chunk(self, chunk_text, redactor, extra_ctx, stats) -> str:
        protected_text, protected_terms = protect_whitelist_terms(
            chunk_text, self.whitelist_pattern
        )

        # Extra lists first, on the original text: a listed name is found whole
        # ("Jan van der Berg-Smit") before Deduce could split it into "[PERSOON-1]" plus
        # leftovers such as "van der" or "-Smit" that the list no longer recognizes.
        # The pseudonyms are then hidden from Deduce and put back afterwards.
        listed_codes: dict[str, str] = {}
        if self.extra_names_patterns:
            protected_text = vervang_gemiste_namen_multi_any(
                protected_text,
                patterns_by_type=self.extra_names_patterns,
                ctx=extra_ctx,
                order=["persoon", "locatie"],
                street_spans=self._street_spans(protected_text),
            )
            protected_text, listed_codes = protect_whitelist_terms(protected_text, _PSEUDONYM_PATTERN)

        doc = self.deduce.deidentify(
            protected_text, enabled=self.enabled, disabled=self.disabled
        )
        out = redactor.redact(protected_text, doc.annotations)
        out = self._redact_mg_postcodes(out, redactor, stats)
        out = self._redact_dates_without_year(out, redactor, stats)

        out = restore_whitelist_terms(out, listed_codes)
        out = restore_whitelist_terms(out, protected_terms)

        chunk_stats = compute_stats(doc)
        for tag, c in chunk_stats.by_type.items():
            stats.by_type[tag] = stats.by_type.get(tag, 0) + c

        return out

        