
from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter



@dataclass
class RunStats:
    by_type: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.by_type.values())

def compute_stats(doc) -> RunStats:
    # Deduce 3.0.6 uses ann.tag (e.g., 'persoon', 'bsn', 'locatie', 'leeftijd', …)
    tags = [getattr(a, "tag", None) for a in getattr(doc, "annotations", []) if getattr(a, "tag", None)]
    return RunStats(by_type=dict(Counter(tags)))

