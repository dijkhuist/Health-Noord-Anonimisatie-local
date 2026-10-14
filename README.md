# Health-Noord-Anonimisatie

Local desktop tool to anonymize Dutch healthcare text using Deduce (tested with 3.0.6).  
Runs fully local (no cloud).

## Features

- **Deduce-based anonymization** (entity detection + de-identification).
- **Deduce filter groups** can be enabled/disabled via checkboxes.
- **Extra .txt lists** to catch missed entities after Deduce:
  - Person names lists (patient + employee) → replaces with <PERSOON_###>
  - Location names list → replaces with <LOCATIE_###>
- **Local processing only** — input text is not uploaded.
- Writes output **and** a summary **log** file (counts include the extra list replacements).

## Run (from source, Windows)

### 1) Install

Create a virtual environment:
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

Install dependencies:
```powershell
pip install -r requirements.txt
```

> Note: `tkinter` is included with the standard Python installer on Windows (not installed via pip).

### 2) Start the GUI

```powershell
python run_gui.py
```

## GUI workflow

1. Select an input `.txt` file.
2. Select an output folder (and optionally a log folder).
3. Configure:
   - Deduce filter groups
4. (Optional) Select one or more extra `.txt` lists:
   - patient names
   - employee names
   - location names
5. Click **Anonimiseer file**.

Output is saved as: `<name>_anonymized.txt`  
Log is saved as: `<name>_log.txt`  
If no log folder is selected, the log is saved in the output folder.

## Extra lists format

Each extra list is a plain `.txt` file:

- One entry per line
- Empty lines are ignored
- Matching is case-insensitive

Example `patienten.txt`:
```text
Jan Jansen
Mevrouw De Vries
```

## Output and logging

- Output file contains the anonymized text.
- Log file contains a summary (timestamp + counts).
- Extra list replacements are included as counters in the log, e.g.:
  - `extra_patient: 3`
  - `extra_medewerker: 1`
  - `extra_locatie: 2`

## Project structure

```text
src/hn_ano_tool/
  app/       Settings + MainController (orchestration, file IO)
  engine/    anonymisatie-core: Deduce-wrapper, chunking, redactie, extra lijsten
  gui/       Tkinter interface + thema
  io/        slim tekst inlezen (encoding-detectie, streaming)
run_gui.py                       entry point
run_gui.spec                     PyInstaller build recipe (build .exe)
build_exe.py                     build pipeline (prebuild cache + PyInstaller)
scripts/build_deduce_cache.py    prebuilds the bundled Deduce cache
requirements.txt
```

## Build a Windows .exe (PyInstaller)

This project is built via `run_gui.spec`, plus a pre-step that creates a deterministic Deduce cache folder that gets bundled into the exe.

### 1) Install dependencies
```powershell
pip install -r requirements.txt
```

### 2) Build (recommended)

From the repo root

```powershell
python .\build_exe.py
```

This will:
1. Run `scripts/build_deduce_cache.py` to populate `bundled_assets/deduce_cache`
2. Run PyInstaller using `run_gui.spec`

Result:
- Output folder: `dist\`

### 3) Manual build (short work/dist paths)

Build the bundled cache:
```powershell
python .\scripts\build_deduce_cache.py
```

Then build the exe:

```powershell
pyinstaller --clean --noconfirm `
  --workpath C:\tmp\hn_build `
  --distpath C:\tmp\hn_dist `
  run_gui.spec
```

Result:
- Output folder: `C:\tmp\hn_dist\...` (exact name depends on the spec)

### 4) If you prefer building into the repo

You can omit `--workpath/--distpath`, but the short paths above are more robust on Windows.

### Troubleshooting build issues
- If you see errors writing `*.pkg` or similar in `build\...`, clean and rebuild using the short paths above.
- If the GUI icon cannot be found at runtime, ensure the spec includes `gui/favicon.png` as data and the code resolves resources via `sys._MEIPASS` (PyInstaller runtime extraction folder).

## Sanity checks (imports / packaging)

Run these from the project root:

1) Compile all modules
```powershell
python -m compileall .
```

2) Import smoke test
```powershell
python -c "from src.hn_ano_tool.app.service import MainController, Settings; from src.hn_ano_tool.engine.core import Anonymizer; print('imports ok')"
```

3) Dependency consistency check
```powershell
pip check
```

## Privacy

All processing happens locally on the machine.  
Always review the anonymized output before sharing it externally.

## Author

Jesse Snels — Hanze University of Applied Sciences (Hanzehogeschool Groningen)