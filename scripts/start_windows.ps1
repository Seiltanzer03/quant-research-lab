$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (!(Test-Path '.venv/Scripts/python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 from python.org' }
    & .venv/Scripts/python.exe -m pip install -r requirements.lock
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }
    & .venv/Scripts/python.exe -m pip install --no-deps -e .
}
if (!(Test-Path 'frontend/node_modules')) {
    npm --prefix frontend ci
    if ($LASTEXITCODE -ne 0) { throw 'Node dependency installation failed' }
}
& .venv/Scripts/python.exe -m backend.app.cli build --auto-demo
if ($LASTEXITCODE -ne 0) { throw 'Research build failed' }
$LabApiProcess = Start-Process -FilePath '.venv/Scripts/python.exe' -ArgumentList '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8000' -PassThru -NoNewWindow
try {
    Start-Process 'http://127.0.0.1:5173'
    npm --prefix frontend run dev -- --port 5173
} finally {
    Stop-Process -Id $LabApiProcess.Id -ErrorAction SilentlyContinue
}
