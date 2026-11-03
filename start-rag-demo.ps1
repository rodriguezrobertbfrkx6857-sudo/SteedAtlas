$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
foreach ($port in @(8003,5175)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is already running. Open http://127.0.0.1:5175 or stop the project-owned demo first."
    }
}
$pointer = Join-Path $projectRoot 'runtime\rag-demo-path.txt'
if (-not (Test-Path -LiteralPath $pointer)) {
    & $pythonExe (Join-Path $projectRoot 'scripts\rag_copy_verify.py')
    if ($LASTEXITCODE -ne 0) { throw 'Copy verification failed' }
}
$demoDatabase = (Get-Content -LiteralPath $pointer -Raw).Trim()
if ($demoDatabase -notmatch '^runtime[\\/][a-zA-Z0-9_-]+\.db$') { throw 'Invalid project-owned demo database path' }
foreach ($service in @('api','worker')) {
    $arguments = @('scripts/run_v2.py',$service,'--database',$demoDatabase)
    if ($service -eq 'api') { $arguments += @('--port','8003') }
    $process = Start-Process -FilePath $pythonExe -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectRoot "runtime/rag-$service-launch.log") -RedirectStandardError (Join-Path $projectRoot "runtime/rag-$service-launch.err")
    $process.Id | Set-Content (Join-Path $projectRoot "runtime/rag-$service-launch.pid")
}
Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList @('node_modules/vite/bin/vite.js','--host','127.0.0.1','--mode','rag-qa') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot 'runtime/rag-web-launch.log') -RedirectStandardError (Join-Path $projectRoot 'runtime/rag-web-launch.err')
Write-Host 'Original black-gold demo: http://127.0.0.1:5175 ; API http://127.0.0.1:8003/docs'
