"""
Make a synthetic test set that mimics the format of an EPD export of care notes,
without any real data.

Output (default: testdata/synthetisch/):
  epd_synthetisch.txt        UTF-16 LE with BOM, CRLF, "objectId<TAB>comment",
                             multi-line notes in double quotes, ~46% empty notes
  patienten.txt, medewerkers.txt, locaties.txt, whitelist.txt   (UTF-8)
  sleutel.json               per record: the sensitive strings and the trap words
                             that must stay (used by scripts/evaluate_testset.py)

All people, numbers and e-mail addresses are made up. Street and place names are
public names (streets come from Deduce's BAG list when available).

Usage:  python scripts/make_synthetic_testset.py [output_dir] [--records 1000] [--seed 7]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FIRST_NAMES_F = [
    "Anna", "Fenna", "Marieke", "Lotte", "Ilse", "Roos", "Jet", "Hendrika", "Johanna", "Wietske",
    "Baukje", "Sietske", "Femke", "Rianne", "Truus", "Bep", "Joke", "Ria", "Mieke", "Esther",
    "Ingrid", "Grietje", "Aaltje", "Anneke", "Tineke", "Geesje", "Trijntje", "Janna", "Hinke", "Wil",
]
FIRST_NAMES_M = [
    "Jan", "Piet", "Klaas", "Sjoerd", "Tjeerd", "Mark", "Bart", "Kees", "Hans", "Bram",
    "Evert", "Gerrit", "Hylke", "Durk", "Jelle", "Henk", "Sander", "Joost", "Willem", "Harm",
    "Geert", "Douwe", "Marten", "Rinse", "Jouke", "Wiebe", "Sybren", "Lammert", "Hendrik", "Harmen",
]
TUSSENVOEGSELS = ["", "", "", "", "de ", "van ", "van der ", "van den ", "ter ", "van de "]
SURNAMES = [
    "Vries", "Berg", "Jong", "Bakker", "Visser", "Smit", "Meer", "Boer", "Mulder", "Dijkstra",
    "Hoekstra", "Postma", "Kramer", "Wal", "Veen", "Haan", "Brink", "Graaf", "Wiersma", "Bosma",
    "Zwart", "Groot", "Koster", "Brouwer", "Hoek", "Linden", "Heuvel", "Boom", "Velde", "Kuipers",
    "Sikkema", "Kingma", "Terpstra", "Hofstra", "Jansma", "Bouma", "Faber", "Steen", "Dam", "Laverman",
    "Ketellapper", "Vallinga", "Heinstra", "Dantuma", "Kooistra", "Boerema", "Barkema", "Henstra", "Donker", "Arts",
]
PLACES = [
    "Drachten", "Heerenveen", "Leeuwarden", "Sneek", "Joure", "Gorredijk", "Burgum", "Dokkum",
    "Surhuisterveen", "Buitenpost", "Akkrum", "Wolvega", "Franeker", "Harlingen", "Grou", "Oosterwolde",
]
FALLBACK_STREETS = [
    "Hendrik de Vosweg", "Prins Willem-Alexanderstraat", "Harmen Sytstrasingel", "Stationsweg",
    "Kerkstraat", "Burgemeester Wuiteweg", "Noordkade", "Zuiderdwarsvaart", "Lavendelweg", "Moleneind",
]
INSTITUTIONS = ["Zorgcentrum De Linde", "Woonzorgcentrum Het Anker", "Hospice De Lindenhof", "Revalidatiecentrum Het Baken"]
DOCTORS_ROLE = ["HA", "SOG", "FT", "EVV", "PA", "POH", "VPK"]
WHITELIST = ["Gabriele-de Vries syndroom", "ziekte van Parkinson", "ziekte van Alzheimer"]

# Everyday words that look like names; they must stay in the output.
TRAPS = [
    ("Linker been is gezwollen, verband vernieuwd.", "Linker"),
    ("Anders gaat het goed met mw.", "Anders"),
    ("Meer pijn dan gisteren, paracetamol 1000 mg gegeven.", "Meer pijn"),
    ("Bij de wondzorg geen bijzonderheden.", "Bij de wondzorg"),
    ("Nieuwe pleister geplakt op de stuit.", "Nieuwe pleister"),
    ("De bakker heeft brood gebracht.", "bakker"),
    ("Mw. wil graag naar buiten vandaag.", "wil graag"),
    ("Zondag is er weer koffie in de huiskamer.", "Zondag is"),
]


def bsn(rng: random.Random) -> str:
    while True:
        digits = [rng.randint(0, 9) for _ in range(8)]
        if digits[0] == 0:
            continue
        rest = sum(d * w for d, w in zip(digits, range(9, 1, -1))) % 11
        if rest < 10:
            return "".join(map(str, digits)) + str(rest)


def load_streets(rng: random.Random, count: int) -> list[str]:
    """Real public street names from Deduce's BAG list (suffix streets only)."""
    try:
        import deduce

        path = Path(deduce.__file__).parent / "data/lookup/src/locations/lst_street/items.txt"
        streets = [
            s for s in path.read_text(encoding="utf-8").splitlines()
            if s.endswith(("straat", "weg", "laan", "singel", "plein", "kade")) and " " in s and len(s) < 32
        ]
        return FALLBACK_STREETS[:3] + rng.sample(streets, count - 3)
    except Exception:
        return FALLBACK_STREETS


def make_people(rng: random.Random, count: int, tag: str) -> list[dict]:
    people, seen = [], set()
    while len(people) < count:
        female = rng.random() < 0.6
        first = rng.choice(FIRST_NAMES_F if female else FIRST_NAMES_M)
        last = rng.choice(SURNAMES)
        # Frisian surnames ("Hoekstra", "Bouma", "Vallinga") take no tussenvoegsel.
        tussen = "" if last.endswith(("stra", "ma", "inga", "ema", "tra")) else rng.choice(TUSSENVOEGSELS)
        if rng.random() < 0.1:
            last = f"{last}-{rng.choice(SURNAMES)}"
        full = f"{first} {tussen}{last}"
        if full in seen:
            continue
        seen.add(full)
        people.append({"first": first, "tussen": tussen.strip(), "last": last, "full": full,
                       "female": female, "group": tag})
    return people


def surname(p: dict, capital_tussen: bool = False) -> str:
    t = p["tussen"]
    if t and capital_tussen:
        t = t[0].upper() + t[1:]
    return f"{t} {p['last']}".strip()


def title(p: dict, rng: random.Random) -> str:
    return rng.choice(["Mw.", "Mevr.", "mw", "Mw"]) if p["female"] else rng.choice(["Dhr.", "dhr", "Dhr"])


class Note:
    """Builds one note and records which strings are sensitive."""

    def __init__(self):
        self.parts: list[str] = []
        self.sensitive: list[dict] = []
        self.traps: list[str] = []

    def add(self, text: str, *entities: tuple[str, str, bool]):
        self.parts.append(text)
        for value, kind, in_list in entities:
            self.sensitive.append({"tekst": value, "soort": kind, "in_lijst": in_list})

    def person(self, p: dict, in_list: bool = True):
        for value in {p["first"], *p["last"].split("-")}:
            self.sensitive.append({"tekst": value, "soort": "naam", "in_lijst": in_list})
        if p["tussen"]:
            self.sensitive.append({"tekst": p["tussen"] + " " + p["last"].split("-")[0],
                                   "soort": "naam (tussenvoegsel)", "in_lijst": in_list})


def note_for(rng, patient, staff, relatives, streets, all_dates) -> Note:
    n = Note()
    p = patient
    s = rng.choice(staff)
    rel = rng.choice(relatives)
    day = rng.choice(all_dates)
    t = f"{rng.randint(7, 21):02d}:{rng.choice(['00', '15', '30', '45'])}"
    sentences = []
    choices = [
        lambda: (f"{title(p, rng)} {surname(p)} kreeg vanmorgen bezoek van {'haar' if p['female'] else 'zijn'} {'dochter' if rel['female'] else 'zoon'} {rel['first']}.",
                 [("p", p), ("r", rel)]),
        lambda: (f"{p['first']} heeft goed geslapen en goed gegeten.", [("p", p)]),
        lambda: (f"{p['full']} gaf aan pijn te hebben in de rug.", [("p", p)]),
        lambda: (f"Overleg gehad met {rng.choice(DOCTORS_ROLE)} {s['full']} over de medicatie.", [("s", s)]),
        lambda: (f"{surname(p, capital_tussen=True)} wil vanmiddag pannenkoeken voor de WM.", [("p", p)]),
        lambda: (f"Afspraak bij de huisarts op {day} om {t}.", [("datum", day)]),
        lambda: (f"{'Dochter' if rel['female'] else 'Zoon'} {rel['full']} belt terug op 06-{rng.randint(10000000, 99999999)}.", [("r", rel), ("telefoon",)]),
        lambda: (f"Mail gestuurd naar {rel['first'].lower()}.{rel['last'].split('-')[0].lower()}@voorbeeld.nl.", [("r_mail", rel)]),
        lambda: (f"Contactpersoon: {rel['full']}, {rng.choice(['dochter', 'buurvrouw'] if rel['female'] else ['zoon', 'schoonzoon'])}.", [("r", rel)]),
        lambda: (f"{p['first'][0]}. {surname(p)} is {rng.randint(70, 99)} jaar.", [("p", p), ("leeftijd",)]),
        lambda: (f"Opname in {rng.choice(INSTITUTIONS)} gepland.", []),
        lambda: (f"Medisch dossier van {title(p, rng)} {surname(p)} hangt in kamer K{rng.randint(100, 499)}.", [("p", p)]),
        lambda: (f"Diagnose {rng.choice(WHITELIST)} is bekend.", [("whitelist",)]),
        lambda: (f"EVV'er {s['first']} heeft de zorgplanning besproken met {p['first']}.", [("s_first", s), ("p_first", p)]),
        lambda: (f"BSN {bsn(rng)} gecontroleerd bij opname.", [("bsn",)]),
    ]
    for builder in rng.sample(choices, rng.randint(1, 4)):
        sentences.append(builder())

    if rng.random() < 0.18:
        street = rng.choice(streets)
        number = rng.choice([str(rng.randint(1, 180)), f"{rng.randint(1, 180)}a", f"{rng.randint(1, 180)}-K"])
        pc = f"{rng.randint(8400, 9299)}{rng.choice(['', ' '])}{rng.choice(['AB', 'CD', 'EK', 'MG', 'RT', 'MG'])}"
        place = rng.choice(PLACES)
        sentences.append((f"Nieuw adres: {street} {number}, {pc} {place}.", [("straat", street), ("huisnr", number), ("postcode", pc), ("plaats", place)]))
    if rng.random() < 0.15:
        trap = rng.choice(TRAPS)
        sentences.append((trap[0], [("trap", trap[1])]))

    texts = []
    for text, entities in sentences:
        texts.append(text)
        for e in entities:
            kind = e[0]
            if kind in ("p", "s"):
                n.person(e[1], in_list=True)
            elif kind == "r":
                n.person(e[1], in_list=False)
            elif kind in ("p_first", "s_first"):
                n.sensitive.append({"tekst": e[1]["first"], "soort": "naam", "in_lijst": True})
            elif kind == "r_mail":
                n.sensitive.append({"tekst": text.split("naar ")[1].rstrip("."), "soort": "e-mail", "in_lijst": False})
            elif kind == "datum":
                n.sensitive.append({"tekst": e[1], "soort": "datum", "in_lijst": False})
            elif kind == "telefoon":
                n.sensitive.append({"tekst": text.split("op ")[1].rstrip("."), "soort": "telefoon", "in_lijst": False})
            elif kind == "bsn":
                n.sensitive.append({"tekst": text.split()[1], "soort": "bsn", "in_lijst": False})
            elif kind == "straat":
                n.sensitive.append({"tekst": e[1], "soort": "straat", "in_lijst": e[1] in LOCATION_LIST_STREETS})
            elif kind == "huisnr":
                n.sensitive.append({"tekst": e[1], "soort": "huisnummer", "in_lijst": False})
            elif kind == "postcode":
                n.sensitive.append({"tekst": e[1], "soort": "postcode", "in_lijst": False})
            elif kind == "plaats":
                n.sensitive.append({"tekst": e[1], "soort": "plaats", "in_lijst": False})
            elif kind == "trap":
                n.traps.append(e[1])

    if len(texts) > 1 and rng.random() < 0.45:
        n.parts = ["\n".join(texts)]  # multi-line note (quoted in the export)
    else:
        n.parts = [" ".join(texts)]
    return n


LOCATION_LIST_STREETS: set[str] = set()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output_dir", nargs="?", default=str(ROOT / "testdata" / "synthetisch"))
    parser.add_argument("--records", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    patients = make_people(rng, 150, "patient")
    staff = make_people(rng, 40, "medewerker")
    relatives = [r for r in make_people(rng, 80, "familie") if r["full"] not in {p["full"] for p in patients + staff}]
    streets = load_streets(rng, 40)
    # Half of the streets go into the location list (with a misspelled variant for one).
    LOCATION_LIST_STREETS.update(streets[::2])
    dates = [f"{rng.randint(1, 28)}-{rng.randint(1, 12)}-2026" for _ in range(60)] + \
            [f"{rng.randint(1, 28)} {rng.choice(['januari', 'maart', 'mei', 'juli', 'oktober'])}" for _ in range(30)]

    rows, key = [], []
    for i in range(args.records):
        object_id = str(rng.randint(10_000_000, 11_999_999))
        if rng.random() < 0.46:
            rows.append((object_id, ""))
            key.append({"objectId": object_id, "gevoelig": [], "valkuilen": []})
            continue
        note = note_for(rng, rng.choice(patients), staff, relatives, streets, dates)
        text = note.parts[0]
        rows.append((object_id, text))
        key.append({"objectId": object_id, "gevoelig": note.sensitive, "valkuilen": note.traps})

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["objectId", "comment"])
    for row in rows:
        writer.writerow(row)
    # Inside a quoted multi-line note, the export uses CRLF too.
    data = buffer.getvalue().replace("\r\n", "\n").replace("\n", "\r\n")
    (out / "epd_synthetisch.txt").write_bytes("﻿".encode("utf-16-le") + data.encode("utf-16-le"))

    (out / "patienten.txt").write_text("\n".join(p["full"] for p in patients) + "\n", encoding="utf-8")
    (out / "medewerkers.txt").write_text("\n".join(p["full"] for p in staff) + "\n", encoding="utf-8")
    (out / "locaties.txt").write_text("\n".join(sorted(LOCATION_LIST_STREETS)) + "\n", encoding="utf-8")
    (out / "whitelist.txt").write_text("\n".join(WHITELIST) + "\n", encoding="utf-8")
    (out / "sleutel.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")

    filled = sum(1 for _, text in rows if text)
    print(f"{out}: {len(rows)} records ({filled} met tekst), {len(patients)} patiënten, "
          f"{len(staff)} medewerkers, {len(LOCATION_LIST_STREETS)} straten in de locatielijst")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
