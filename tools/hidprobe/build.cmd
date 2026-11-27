@echo off
setlocal
rem Build the 32-bit HID diagnostic probe.  Output must land in the same
rem directory as our logging hid.dll proxy so that HID.dll resolves to it.
set "OUT=%~1"
if "%OUT%"=="" set "OUT=%~dp0out"

call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars32.bat" >nul 2>&1
if errorlevel 1 (
  echo [build] vcvars32.bat failed
  exit /b 1
)
if not exist "%OUT%" mkdir "%OUT%"

cl /nologo /O2 /W3 /Fo"%OUT%\hidprobe.obj" "%~dp0hidprobe.c" ^
   /link /OUT:"%OUT%\hidprobe.exe" setupapi.lib hid.lib

if errorlevel 1 (
  echo [build] FAILED
  exit /b 1
)
echo [build] OK -^> "%OUT%\hidprobe.exe"
exit /b 0
