import shutil
import sys
import os
from pathlib import Path


def bundled_cache_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parents[1]
    return base / "bundled_assets" / "deduce_cache"


def persistent_cache_dir() -> Path:
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    p = local / "HealthNoord" / "AnonymisatieTool" / "deduce_cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_cache_seeded() -> Path:
    src = bundled_cache_dir()
    dst = persistent_cache_dir()
    marker = dst / ".seeded"

    # Al klaar? Dan direct terug.
    if marker.exists():
        return dst

    # Geen seed beschikbaar (src ontbreekt) -> laat Deduce later on-demand bouwen.
    if not src.exists():
        return dst

    # Copy atomisch-ish: eerst naar temp, dan overzetten
    tmp = dst.parent / (dst.name + "_tmp_seed")
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)

    shutil.copytree(src, tmp)

    # Maak dst leeg zodat we een consistente set krijgen
    # (dst bestaat al door persistent_cache_dir)
    for child in dst.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink()
            except FileNotFoundError:
                pass

    # Verplaats tmp -> dst (fall back naar copy als rename niet kan)
    try:
        for child in tmp.iterdir():
            shutil.move(str(child), str(dst / child.name))
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        # als move faalt: copy nog eens naar dst
        shutil.copytree(tmp, dst, dirs_exist_ok=True)
        shutil.rmtree(tmp, ignore_errors=True)

    # Marker als laatste: alleen zetten als alles ok lijkt
    marker.write_text("seeded\n", encoding="utf-8")
    return dst