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
            )
            protected_text, listed_codes = protect_whitelist_terms(protected_text, _PSEUDONYM_PATTERN)

        doc = self.deduce.deidentify(
            protected_text, enabled=self.enabled, disabled=self.disabled
        )
        out = redactor.redact(protected_text, doc.annotations)

        out = restore_whitelist_terms(out, listed_codes)
        out = restore_whitelist_terms(out, protected_terms)

        chunk_stats = compute_stats(doc)
        for tag, c in chunk_stats.by_type.items():
            stats.by_type[tag] = stats.by_type.get(tag, 0) + c

        return out

        