@echo off
setlocal enabledelayedexpansion

rem ============================================================
rem  Abstract Shape Data Management - startup script
rem  Single process: FastAPI serves both the API and the
rem  static frontend (frontend/), so there is no separate
rem  frontend dev server to start.
rem
rem  NOTE: do NOT put "chcp 65001" in this file. Switching the
rem  console codepage mid-script makes cmd drop all subsequent
rem  output (the script appears to do nothing). Python/uvicorn
rem  write UTF-8 on their own, so no codepage change is needed.
rem ============================================================

rem Always run from the repo root (this .bat lives there).
cd /d "%~dp0"

echo === Abstract Shape Data Management System ===
echo.

rem --- locate an interpreter -------------------------------------------
set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%~dp0venv\Scripts\python.exe" set "PY=%~dp0venv\Scripts\python.exe"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [ERROR] Python not found. Install Python or create .venv first.
    pause
    exit /b 1
)

rem --- export derived data only when the artifacts are missing ---------
if not exist "backend\data\guangyun.json" goto :do_export
if not exist "backend\data\papers.json"   goto :do_export
echo Export data already exists, skipping export.
goto :kill_previous

:do_export
echo Exporting data ...
"%PY%" backend\scripts\export_gy.py
if errorlevel 1 goto :export_failed
"%PY%" backend\scripts\export_papers.py
if errorlevel 1 goto :export_failed
goto :kill_previous

:export_failed
echo [ERROR] Data export failed.
pause
exit /b 1

rem --- stop any previous instance of this server -----------------------
rem Kill whatever is LISTENING on a port in our range (8000-8100).
rem Ports are checked one by one so the PID column is always token 5
rem of the matching line; a non-zero taskkill result just means the
rem PID had already exited on its own.
:kill_previous
echo Stopping previous instance ...
for /l %%N in (8000,1,8100) do (
    for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%%N .*LISTENING"') do (
        taskkill /f /pid %%P >nul 2>&1
        if !errorlevel! equ 0 (echo   stopped PID %%P on port %%N) else (echo   port %%N: PID %%P already gone)
    )
)
echo.

rem --- pick a free port automatically (8000 may be taken) --------------
:pick_port
set "PORT=8000"
:port_loop
rem ":PORT " with a trailing space avoids matching ":80001".
netstat -ano | findstr /r /c:":!PORT! .*LISTENING" >nul 2>&1
if errorlevel 1 goto :port_found
set /a PORT+=1
if !PORT! gtr 8100 goto :no_port
goto :port_loop

:no_port
echo [ERROR] No free port found in range 8000-8100.
pause
exit /b 1

:port_found
set "URL=http://127.0.0.1:!PORT!"
echo.
echo Starting backend server ...
echo Open !URL!
echo Press Ctrl+C to stop the server.
echo.

rem Open the browser in a detached window after a short delay, so it
rem fires once uvicorn has had time to bind the port.
start "abstract-shape" /min cmd /c "timeout /t 3 /nobreak >nul & start %URL%"

"%PY%" -m uvicorn backend.main:app --host 127.0.0.1 --port !PORT! --reload

echo.
echo Server stopped.
pause
