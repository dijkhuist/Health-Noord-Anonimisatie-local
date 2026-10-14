from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SPEC_FILE = ROOT / "run_gui.spec"

# In jouw repo staat deze volgens tree.txt in scripts/
CACHE_BUILDER = ROOT / "scripts" / "build_deduce_cache.py"

# Fallback (als jij hem toch in de root hebt staan)
CACHE_BUILDER_FALLBACK = ROOT / "build_deduce_cache.py"

BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"


def run(cmd: list[str]) -> None:
    print("\n>>>", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(ROOT))


def clean_dir(path: Path) -> None:
    if path.exists():
        print(f">>> Removing {path}")
        shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    if not SPEC_FILE.exists():
        print(f"ERROR: Spec file not found: {SPEC_FILE}")
        return 2

    # 1) Build deduce cache (must exist for bundling)
    cache_builder = CACHE_BUILDER if CACHE_BUILDER.exists() else CACHE_BUILDER_FALLBACK
    if not cache_builder.exists():
        print("ERROR: Could not find build_deduce_cache.py")
        print(f"Looked for: {CACHE_BUILDER} and {CACHE_BUILDER_FALLBACK}")
        return 3

    run([sys.executable, str(cache_builder)])

    # 2) Clean old build artifacts for deterministic builds
    clean_dir(BUILD_DIR)
    clean_dir(DIST_DIR)

    # 3) Run PyInstaller with the spec
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(SPEC_FILE)])

    print("\n✅ Build complete. Check:", DIST_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
