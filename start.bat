@echo off
REM Start AetherShield VMS (backend + frontend)
cd /d "%~dp0"

start "AetherShield API" cmd /k "set PYTHONPATH=%cd%\backend && %cd%\backend\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 3 >nul
start "AetherShield UI" cmd /k "cd /d %cd%\frontend && npx vite --host 127.0.0.1 --port 5173"

echo.
echo Backend:  http://127.0.0.1:8000/docs
echo Frontend: http://127.0.0.1:5173
echo Login:    admin@aethershield.io / admin123
echo.
