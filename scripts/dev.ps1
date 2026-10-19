param([switch]$DeepSeek)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if ($DeepSeek) {
    if (-not $env:DEEPSEEK_API_KEY) { throw 'DEEPSEEK_API_KEY is not set' }
    $env:PM_API_KEY = $env:DEEPSEEK_API_KEY
    $env:PM_BASE_URL = 'https://api.deepseek.com/v1'
    $env:PM_CHAT_MODEL = 'deepseek-chat'
}
$env:PM_ENVIRONMENT = 'development'
$env:PM_TASK_EAGER = 'true'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location -LiteralPath (Join-Path $projectRoot 'backend')
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
