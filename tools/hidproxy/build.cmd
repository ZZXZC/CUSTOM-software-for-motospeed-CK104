@echo off
setlocal enabledelayedexpansion
rem ---------------------------------------------------------------------------
rem  Build the 32-bit logging HID.dll proxy (OemDrv.exe is a 32-bit process,
rem  so the proxy must be 32-bit too and forward to SysWOW64\HID.dll).
rem
rem  Usage:  build.cmd [output-dir]
rem ---------------------------------------------------------------------------
set "OUT=%~1"
if "%OUT%"=="" set "OUT=%~dp0out"

call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars32.bat" >nul 2>&1
if errorlevel 1 (
  echo [build] vcvars32.bat failed - Visual Studio not found
  exit /b 1
)

if not exist "%OUT%" mkdir "%OUT%"

rem The .def controls the export table: 4 intercepted functions + 40 forwarders.
cl /nologo /LD /O2 /W3 /D_CRT_SECURE_NO_WARNINGS ^
   /Fo"%OUT%\hidproxy.obj" ^
   "%~dp0hidproxy.c" ^
   /link /DEF:"%~dp0hidproxy.def" /OUT:"%OUT%\hid.dll" ^
   kernel32.lib user32.lib

if errorlevel 1 (
  echo [build] FAILED
  exit /b 1
)

echo [build] OK -^> "%OUT%\hid.dll"
exit /b 0
