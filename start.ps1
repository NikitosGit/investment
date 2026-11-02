<#
.SYNOPSIS
    Build (when needed) and run the investment tracker on a single port.

.DESCRIPTION
    Applies Alembic migrations, builds the Angular app into dist/browser when
    it is missing or -Build is passed, then starts uvicorn from backend/.

.PARAMETER Build
    Rebuild the Angular app even when dist/browser/index.html already exists.

.PARAMETER Port
    HTTP port for uvicorn. Default: 8000.

.PARAMETER NoBrowser
    Do not open the browser after startup.

.PARAMETER NpmCi
    Force a clean npm ci before building.

.PARAMETER HealthTimeoutSeconds
    How long to wait for GET /api/health before giving up on opening the
    browser. Default: 60.
#>
param(
    [switch]$Build,
    [int]$Port = 8000,
    [switch]$NoBrowser,
    [switch]$NpmCi,
    [int]$HealthTimeoutSeconds = 60
)

$ErrorActionPreference = 'Stop'

if ($Port -lt 1 -or $Port -gt 65535) {
    throw "Некорректный порт: $Port. Укажите значение от 1 до 65535."
}
if ($HealthTimeoutSeconds -lt 1) {
    throw "Некорректный таймаут health-check: $HealthTimeoutSeconds. Укажите значение больше 0."
}

$root = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($root)) {
    $root = Split-Path -Parent $MyInvocation.MyCommand.Path
}

$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'
$distIndex = Join-Path $root 'dist\browser\index.html'
$url = "http://127.0.0.1:$Port"

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-Command([string]$Name, [string]$Hint) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Не найдена команда '$Name'. $Hint"
    }
    return $command.Source
}

function Invoke-Native([string]$FilePath, [string[]]$Arguments, [string]$ErrorMessage) {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$ErrorMessage (код выхода: $LASTEXITCODE)."
    }
}

function Wait-ForHealth(
    [string]$HealthUrl,
    [int]$TimeoutSeconds,
    [System.Diagnostics.Process]$ServerProcess
) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($ServerProcess.HasExited) {
            return $false
        }
        try {
            $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                return $true
            }
        }
        catch {
            # The server is still starting; keep polling until the deadline.
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

Write-Step 'Проверка uv'
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCommand) {
    $uvExe = $uvCommand.Source
    $uvArgs = @()
} else {
    $pythonExe = Assert-Command 'python' 'Установите uv (https://docs.astral.sh/uv/) или Python 3.12 с модулем uv.'
    $uvExe = $pythonExe
    $uvArgs = @('-m', 'uv')
    Write-Host 'uv не найден в PATH, используется python -m uv.' -ForegroundColor Yellow
}

Write-Step 'Применение миграций (alembic upgrade head)'
Push-Location $backendDir
try {
    Invoke-Native $uvExe ($uvArgs + @('run', 'alembic', 'upgrade', 'head')) 'Не удалось применить миграции'
}
finally {
    Pop-Location
}

$needBuild = $Build -or $NpmCi -or -not (Test-Path -Path $distIndex -PathType Leaf)
if ($needBuild) {
    $npmExe = Assert-Command 'npm' 'Установите Node.js 20/22/24 LTS и npm, затем повторите запуск.'
    Assert-Command 'node' 'Установите Node.js 20/22/24 LTS и npm, затем повторите запуск.' | Out-Null

    Push-Location $frontendDir
    try {
        $nodeModules = Join-Path $frontendDir 'node_modules'
        if ($NpmCi -or -not (Test-Path -Path $nodeModules -PathType Container)) {
            Write-Step 'Установка frontend-зависимостей (npm ci)'
            Invoke-Native $npmExe @('ci') 'npm ci завершился с ошибкой'
        }
        else {
            Write-Step 'frontend/node_modules уже установлены (npm ci пропущен)'
        }

        Write-Step 'Сборка Angular (npm run build)'
        Invoke-Native $npmExe @('run', 'build') 'npm run build завершился с ошибкой'
    }
    finally {
        Pop-Location
    }

    if (-not (Test-Path -Path $distIndex -PathType Leaf)) {
        throw "Сборка завершилась, но файл не найден: $distIndex"
    }
}
else {
    Write-Step "Используется существующая сборка: $distIndex"
}

Write-Step "Запуск сервера: $url"
Write-Host 'Остановить сервер: Ctrl+C.' -ForegroundColor DarkGray

$serverArgs = $uvArgs + @(
    'run', 'uvicorn', 'app.main:app',
    '--host', '127.0.0.1',
    '--port', "$Port"
)
$server = $null
try {
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $uvExe
    $startInfo.Arguments = ($serverArgs -join ' ')
    $startInfo.WorkingDirectory = $backendDir
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $false
    $server = [System.Diagnostics.Process]::Start($startInfo)

    if (-not $NoBrowser) {
        $healthUrl = "$url/api/health"
        Write-Step "Ожидание готовности: $healthUrl (до $HealthTimeoutSeconds с)"
        $healthy = Wait-ForHealth -HealthUrl $healthUrl -TimeoutSeconds $HealthTimeoutSeconds -ServerProcess $server
        if ($healthy) {
            try {
                Start-Process $url | Out-Null
                Write-Step "Браузер открыт: $url"
            }
            catch {
                Write-Warning "Не удалось открыть браузер: $($_.Exception.Message)"
            }
        }
        else {
            Write-Warning "Сервер не подтвердил готовность за $HealthTimeoutSeconds с; браузер не открыт."
        }
    }

    $server.WaitForExit()
    if ($server.ExitCode -ne 0) {
        throw "uvicorn завершился с ошибкой (код выхода: $($server.ExitCode))."
    }
}
finally {
    if ($server) {
        try {
            if (-not $server.HasExited) {
                & taskkill /PID $server.Id /T /F | Out-Null
            }
        }
        catch {
            # The process already exited or taskkill is unavailable; nothing to clean up.
        }
    }
}
