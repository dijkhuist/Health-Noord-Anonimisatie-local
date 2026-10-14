from pathlib import Path
from deduce import Deduce

def main() -> None:
    # Store cache inside the repo so PyInstaller can bundle it deterministically.
    cache_dir = Path(__file__).resolve().parents[1] / "bundled_assets" / "deduce_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Force a rebuild to ensure cache files exist and are consistent with the installed deduce version.
    _ = Deduce(cache_path=cache_dir, build_lookup_structs=True)

    print(f"Deduce cache built at: {cache_dir}")

if __name__ == "__main__":
    main()
