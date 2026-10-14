import os
import sys
from pathlib import Path
from collections import defaultdict

from .deduce_adapter import get_deduce
from .stats import RunStats, compute_stats
from .extra_lists import build_extra_patterns

from src.hn_ano_tool.engine.utils import (
    ExtraNamesContext,
    vervang_gemiste_namen_multi_any,
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
        extra_names_paths: dict[str, str] | None = None
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
        doc = self.deduce.deidentify(
            chunk_text, enabled=self.enabled, disabled=self.disabled
        )
        out = redactor.redact(chunk_text, doc.annotations)

        if self.extra_names_patterns:
            out = vervang_gemiste_namen_multi_any(
                out,
                patterns_by_type=self.extra_names_patterns,
                ctx=extra_ctx,
                order=["persoon", "locatie"],
            )

        chunk_stats = compute_stats(doc)
        for tag, c in chunk_stats.by_type.items():
            stats.by_type[tag] = stats.by_type.get(tag, 0) + c

        return out

        