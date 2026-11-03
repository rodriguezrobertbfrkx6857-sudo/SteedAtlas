$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Create .venv and install requirements-dev.txt first; see docs/RUNBOOK.md.' }
$runtimeDir = Join-Path $projectRoot 'runtime'
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
& $pythonExe (Join-Path $projectRoot 'scripts\run_v2.py') init
if ($LASTEXITCODE -ne 0) { throw 'Initialization failed' }
foreach ($service in @('api','worker')) {
    $owned = Start-Process -FilePath $pythonExe -ArgumentList @('scripts/run_v2.py',$service) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir "$service.stdout.log") -RedirectStandardError (Join-Path $runtimeDir "$service.stderr.log")
    $owned.Id | Set-Content (Join-Path $runtimeDir "$service.pid")
}
$nodeExe = (Get-Command node.exe).Source
$web = Start-Process -FilePath $nodeExe -ArgumentList @('node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir 'web.stdout.log') -RedirectStandardError (Join-Path $runtimeDir 'web.stderr.log')
$web.Id | Set-Content (Join-Path $runtimeDir 'web.pid')
Write-Host 'Local website: http://127.0.0.1:5173'
Write-Host 'Local API: http://127.0.0.1:8002/docs'
