# Build helper for Windows PowerShell
# Usage:
#   .\.venv\Scripts\activate
#   pip install -r requirements.txt
#   .\build_exe.ps1

$ErrorActionPreference = "Stop"

Write-Host ">>> Running build_exe.py"
python .\build_exe.py
Write-Host "✅ Done. Output is in .\dist\"
