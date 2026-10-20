"""
Run the anonymizer on the synthetic test set and report what leaks.

For every record the answer key (sleutel.json) lists the sensitive strings and the
trap words (everyday words that look like names and must stay). A sensitive string
"leaks" when it still appears as a whole word in that record of the output; a trap
"is over-anonymized" when it is gone.

Usage:  python scripts/evaluate_testset.py [testset_dir] [--no-lists] [--examples 5]
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.hn_ano_tool.app.service import MainController, Settings  # noqa: E402


def read_rows(path: Path, encoding: str) -> list[list[str]]:
    text = path.read_text(encoding=encoding)
    return list(csv.reader(io.StringIO(text), delimiter="\t"))[1:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("testset_dir", nargs="?", default=str(ROOT / "testdata" / "synthetisch"))
    parser.add_argument("--no-lists", action="store_true", help="run without the extra lists and whitelist")
    parser.add_argument("--examples", type=int, default=5, help="examples to show per category")
    args = parser.parse_args()

    d = Path(args.testset_dir)
    key = json.loads((d / "sleutel.json").read_text(encoding="utf-8"))
    whitelist = [t for t in (d / "whitelist.txt").read_text(encoding="utf-8").splitlines() if t.strip()]
    lists = {} if args.no_lists else {
        "patient": str(d / "patienten.txt"),
        "medewerker": str(d / "medewerkers.txt"),
        "locatie": str(d / "locaties.txt"),
    }
    settings = Settings(
        input_file=str(d / "epd_synthetisch.txt"),
        output_dir=str(d / "uitvoer"),
        log_dir=None,
        extra_names_paths=lists,
        whitelist_path=None if args.no_lists else str(d / "whitelist.txt"),
    )
    _, out_path, log_path, _ = MainController(settings).run()
    output = read_rows(Path(out_path), "utf-8")
    if len(output) != len(key):
        print(f"Let op: {len(output)} uitvoerregels tegen {len(key)} records; vergelijking per positie.")

    total = collections.Counter()
    leaked = collections.Counter()
    examples = collections.defaultdict(list)
    traps_total = traps_lost = 0
    trap_examples = []

    for record, row in zip(key, output):
        out_text = row[1] if len(row) > 1 else ""
        checked = out_text
        for term in whitelist:  # whitelisted terms stay on purpose
            checked = re.sub(re.escape(term), " ", checked, flags=re.IGNORECASE)
        for item in record["gevoelig"]:
            category = item["soort"] + (" (in lijst)" if item["in_lijst"] else " (niet in lijst)")
            total[category] += 1
            if re.search(rf"(?<!\w){re.escape(item['tekst'])}(?!\w)", checked):
                leaked[category] += 1
                if len(examples[category]) < args.examples:
                    examples[category].append(f"{item['tekst']!r} in: {out_text[:160]!r}")
        for trap in record["valkuilen"]:
            traps_total += 1
            if trap not in out_text:
                traps_lost += 1
                if len(trap_examples) < args.examples:
                    trap_examples.append(f"{trap!r} weg in: {out_text[:160]!r}")

    mode = "zonder lijsten" if args.no_lists else "met lijsten en whitelist"
    filled = sum(1 for r in key if r["gevoelig"] or r["valkuilen"])
    print(f"\nResultaat {mode} ({filled} notities met tekst)")
    print(f"{'categorie':38} {'aantal':>7} {'gelekt':>7} {'%':>6}")
    for category in sorted(total):
        n, k = total[category], leaked[category]
        print(f"{category:38} {n:7} {k:7} {100 * k / n:5.1f}%")
    all_n, all_k = sum(total.values()), sum(leaked.values())
    print(f"{'TOTAAL':38} {all_n:7} {all_k:7} {100 * all_k / max(all_n, 1):5.1f}%")
    print(f"Valkuilen onterecht vervangen: {traps_lost} van {traps_total}")

    for category, lines in sorted(examples.items()):
        print(f"\n{category}:")
        for line in lines:
            print("  ", line)
    if trap_examples:
        print("\nonterecht vervangen:")
        for line in trap_examples:
            print("  ", line)
    print(f"\nUitvoer: {out_path}\nLog:     {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
