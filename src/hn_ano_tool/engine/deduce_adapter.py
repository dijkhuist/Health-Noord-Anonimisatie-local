from __future__ import annotations

from functools import lru_cache
from .cache import ensure_cache_seeded


@lru_cache(maxsize=1)
def get_deduce():
    from deduce import Deduce
    cache_dir = ensure_cache_seeded()
    return Deduce(build_lookup_structs=False, cache_path=str(cache_dir))


@lru_cache(maxsize=1)
def warmup_deducefy() -> None:
    """
    Warm-up: 1x deducefy op een klein, representatief tekstje
    zodat Deduce interne caches/structs kan initialiseren.
    """
    d = get_deduce()

    dummy = (
        "Op 1 januari 2020 had Jan Jansen een afspraak in Groningen. "
        "Bel 0612345678 of mail jan.jansen@example.com. BSN 123456782."
    )

    doc = d.deidentify(dummy, disabled=set())
    _ = doc.deidentified_text
