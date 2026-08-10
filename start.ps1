# Abstract Shape Data Management - Startup Script
Write-Host "=== Abstract Shape Data Management System ===" -ForegroundColor Cyan
Write-Host ""

# Run export only if the export artifacts are missing (guangyun.json / papers.json)
if (-not (Test-Path "backend/data/guangyun.json") -or -not (Test-Path "backend/data/papers.json")) {
    Write-Host "Exporting data ..." -ForegroundColor Yellow
    python backend/scripts/export_gy.py
    python backend/scripts/export_papers.py
} else {
    Write-Host "Export data already exists, skipping export." -ForegroundColor DarkGray
}

# Pick a free port automatically (8000 may be occupied by a system service)
$PORT = 8000
while (Get-NetTCPConnection -LocalPort $PORT -State Listen -ErrorAction SilentlyContinue) {
    $PORT++
}

Write-Host "Starting backend server ..." -ForegroundColor Green
Write-Host "Open http://127.0.0.1:$PORT" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python -m uvicorn backend.main:app --host 127.0.0.1 --port $PORT --reload
