# TaskMate Duo · 一键运行脚本（PowerShell）
# 用法：
#   .\run.ps1 web    启动网页界面（默认 8520 端口）
#   .\run.ps1 cli    命令行模式（一样是队友 A 的 Agent）
#   .\run.ps1 test   跑全部自动化测试（不需要 API key）
#
param(
    [string]$Cmd = "web",
    [int]$Port = 8520
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root
$env:PYTHONIOENCODING = "utf-8"

function Get-Python {
    if (Test-Path ".venv\Scripts\python.exe") { return (Resolve-Path ".venv\Scripts\python.exe").Path }
    return "python"
}

$py = Get-Python

switch ($Cmd) {
    "web" {
        Write-Host "启动界面： http://localhost:$Port" -ForegroundColor Green
        & $py -m streamlit run ui/app.py --server.headless true --server.port $Port
    }
    "cli" {
        Write-Host "命令行模式（队友 A 的 Agent 原逻辑），输入 /quit 退出" -ForegroundColor Green
        & $py main.py
    }
    "test" {
        Write-Host "跑全部测试（离线，不需要 API key）..." -ForegroundColor Green
        & $py tests\run_all.py
        exit $LASTEXITCODE
    }
    "model" {
        Write-Host "下载语音识别模型到 models/whisper-base/" -ForegroundColor Green
        & $py scripts\fetch_asr_model.py
    }
    default {
        Write-Host "未知命令：$Cmd（可选 web / cli / test / model）" -ForegroundColor Yellow
    }
}
