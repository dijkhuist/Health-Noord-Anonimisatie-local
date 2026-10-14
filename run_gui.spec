# run_gui.spec — PyInstaller build recipe for Health Noord Anonymizer
#
# Onefile GUI build. Bundles the NLP libraries' data (Deduce/docdeid/rapidfuzz),
# our seeded Deduce cache, and the app icon — so the resulting .exe runs standalone.
#
# Build via:  python build_exe.py     (rebuilds the cache, then runs PyInstaller here)

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# Pull in each NLP library's package data, submodules and native libraries.
# collect_all handles the data files Deduce needs to initialise (config + lookups).
for _pkg in ("deduce", "docdeid", "rapidfuzz"):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

# Our own runtime resources. The destination paths MUST match how the code resolves
# them from sys._MEIPASS at runtime:
#   gui/__init__.resource_path      -> _MEIPASS/assets/...
#   engine/cache.py bundled_cache_dir -> _MEIPASS/bundled_assets/deduce_cache
datas += [
    ("assets", "assets"),
    ("bundled_assets/deduce_cache", "bundled_assets/deduce_cache"),
]

a = Analysis(
    ["run_gui.py"],
    pathex=["."],              # so `import src.hn_ano_tool...` resolves
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="HealthNoordAnonymizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,             # GUI app: no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/health_noord.ico",
)
