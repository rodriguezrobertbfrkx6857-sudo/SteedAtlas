Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-PortAvailable {
    param(
        [int]$Port,
        [string]$BindAddress = "127.0.0.1"
    )

    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse($BindAddress), $Port)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) {
            $listener.Stop()
        }
    }
}

function Get-FreePort {
    param(
        [int]$PreferredPort,
        [string]$BindAddress = "127.0.0.1"
    )

    for ($candidate = $PreferredPort; $candidate -lt ($PreferredPort + 50); $candidate++) {
        if (Test-PortAvailable -Port $candidate -BindAddress $BindAddress) {
            return $candidate
        }
    }

    throw "Could not find an available port near $PreferredPort on $BindAddress."
}

function Test-BaiqipuBackend {
    param(
        [string]$BaseUrl
    )

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/health" -TimeoutSec 2
        if ($response.StatusCode -ne 200) {
            return $false
        }

        $payload = $response.Content | ConvertFrom-Json
        if ($null -eq $payload) {
            return $false
        }

        $propertyNames = @($payload.PSObject.Properties.Name)
        return $payload.status -eq "ok" -and -not ($propertyNames -contains "success")
    } catch {
        return $false
    }
}

function Test-BackendImport {
    param(
        [string]$BackendPath
    )

    Push-Location $BackendPath
    try {
        python -c "import app.main" *> $null
        return $LASTEXITCODE -eq 0
    } finally {
        Pop-Location
    }
}

function Wait-ForHttpReady {
    param(
        [string]$Url,
        [int]$Attempts = 30,
        [int]$DelaySeconds = 1
    )

    for ($i = 0; $i -lt $Attempts; $i++) {
        Start-Sleep -Seconds $DelaySeconds
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                return $true
            }
        } catch {
        }
    }

    return $false
}

$Root = $PSScriptRoot
$FrontendDir = Join-Path $Root "baiqipu.com-source-20260424-194149"
$ProxyScript = Join-Path $Root "local_proxy.py"
$HostAddress = "127.0.0.1"
$PreferredBackendPort = 8000
$PreferredProxyPort = 8080

if (-not (Test-Path -LiteralPath (Join-Path $FrontendDir "index.html"))) {
    throw "Frontend index.html was not found at: $FrontendDir"
}

$BackendMarker = Get-ChildItem -LiteralPath $Root -Recurse -Force -Filter "requirements.txt" |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.DirectoryName "app\main.py") } |
    Select-Object -First 1

if (-not $BackendMarker) {
    throw "Backend requirements.txt with app\main.py was not found under: $Root"
}

$BackendDir = $BackendMarker.DirectoryName
if (-not (Test-Path -LiteralPath (Join-Path $BackendDir "baiqipu.db"))) {
    Write-Host "Warning: baiqipu.db was not found in $BackendDir. The backend may start with an empty or missing database."
}

Write-Host "Frontend: $FrontendDir"
Write-Host "Backend:  $BackendDir"

if (-not (Test-BackendImport -BackendPath $BackendDir)) {
    Write-Host "Python backend dependencies are missing or incomplete."
    $InstallDeps = Read-Host "Install dependencies from requirements.txt now? Type y to continue"
    if ($InstallDeps -ne "y") {
        throw "Backend dependencies are required."
    }
    Push-Location $BackendDir
    try {
        python -m pip install -r (Join-Path $BackendDir "requirements.txt")
    } finally {
        Pop-Location
    }

    if (-not (Test-BackendImport -BackendPath $BackendDir)) {
        throw "Backend dependencies still could not be imported after installation. Check the pip output above for details."
    }
}

$ExistingBackendUrl = "http://$HostAddress`:$PreferredBackendPort"
$BackendPort = $PreferredBackendPort
$BackendUrl = $ExistingBackendUrl
$StartBackend = $true

if (Test-BaiqipuBackend -BaseUrl $ExistingBackendUrl) {
    $StartBackend = $false
    Write-Host "Detected an existing Baiqipu backend at $ExistingBackendUrl . Reusing it."
} else {
    $BackendPort = Get-FreePort -PreferredPort $PreferredBackendPort -BindAddress $HostAddress
    $BackendUrl = "http://$HostAddress`:$BackendPort"
    if ($BackendPort -ne $PreferredBackendPort) {
        Write-Host "Port $PreferredBackendPort is already in use by another program. Baiqipu backend will use $BackendPort instead."
    }
}

if ($StartBackend) {
    $BackendCommand = "python -m uvicorn app.main:app --host $HostAddress --port $BackendPort"
    Write-Host "Starting backend at $BackendUrl ..."
    Start-Process powershell -WorkingDirectory $BackendDir -ArgumentList @("-NoExit", "-Command", $BackendCommand)
}

Write-Host "Waiting for Baiqipu backend health check ..."
$BackendReady = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if (Test-BaiqipuBackend -BaseUrl $BackendUrl) {
        $BackendReady = $true
        break
    }
}

if (-not $BackendReady) {
    throw "Baiqipu backend did not become ready at $BackendUrl . Check the backend window for errors."
}

$ProxyPort = Get-FreePort -PreferredPort $PreferredProxyPort -BindAddress $HostAddress
$Url = "http://$HostAddress`:$ProxyPort"

if ($ProxyPort -ne $PreferredProxyPort) {
    Write-Host "Port $PreferredProxyPort is already in use by another program. The local website proxy will use $ProxyPort instead."
}

$ProxyCommand = "python `"$ProxyScript`" --frontend `"$FrontendDir`" --backend `"$BackendUrl`" --host `"$HostAddress`" --port $ProxyPort"
Write-Host "Starting local website proxy at $Url ..."
Start-Process powershell -WorkingDirectory $Root -ArgumentList @("-NoExit", "-Command", $ProxyCommand)

Write-Host "Waiting for local website proxy ..."
if (-not (Wait-ForHttpReady -Url $Url -Attempts 20 -DelaySeconds 1)) {
    throw "The local website proxy did not become ready at $Url . Check the proxy window for errors."
}

Write-Host "Opening website at $Url ..."
try {
    Start-Process $Url
} catch {
    Write-Host "Could not open the browser automatically. Open this URL manually: $Url"
}
