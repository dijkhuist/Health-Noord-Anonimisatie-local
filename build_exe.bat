@echo off
setlocal

echo >>> Running build_exe.py
python .\build_exe.py

if errorlevel 1 (
  echo ERROR: build failed
  exit /b 1
)

echo ✅ Done. Output is in .\dist\
endlocal
