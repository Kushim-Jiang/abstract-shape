# 抽象构形数据管理 - 启动脚本
Write-Host "=== 抽象构形数据管理系统 ===" -ForegroundColor Cyan
Write-Host ""

# 如果 JSON 数据不存在，运行导出
if (-not (Test-Path "backend/data/characters.json")) {
    Write-Host "正在导出数据 ..." -ForegroundColor Yellow
    python backend/scripts/export_gy.py
    python backend/scripts/export_papers.py
}

Write-Host "启动后端服务 ..." -ForegroundColor Green
Write-Host "访问 http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host ""

python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
