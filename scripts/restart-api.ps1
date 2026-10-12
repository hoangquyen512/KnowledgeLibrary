#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $Root "apps\api"
$LogDir = Join-Path $Root "logs"
$ApiPy = Join-Path $ApiDir ".venv\Scripts\python.exe"
$Port = 8000

function Stop-UvicornOnPort([int]$TargetPort) {
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object {
      ($_.CommandLine -match "uvicorn" -and $_.CommandLine -match "--port\s+$TargetPort") -or
      ($_.CommandLine -match "multiprocessing\.spawn" -and $_.CommandLine -match "spawn_main")
    } |
    ForEach-Object {
      Write-Host "Stopping python PID $($_.ProcessId)"
      cmd.exe /c "taskkill /PID $($_.ProcessId) /T /F >nul 2>&1" | Out-Null
    }
  Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object {
      Write-Host "Stopping listener PID $($_.OwningProcess) on port $TargetPort"
      cmd.exe /c "taskkill /PID $($_.OwningProcess) /T /F >nul 2>&1" | Out-Null
    }
  Start-Sleep -Seconds 2
}

function Test-ApiFresh() {
  try {
    $openapi = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/openapi.json" -TimeoutSec 5
    $props = $openapi.components.schemas.AiCredentialIn.properties
    return ($null -ne $props.test_only) -and ($null -ne $props.verified_model)
  } catch {
    return $false
  }
}

if (-not (Test-Path $ApiPy)) {
  throw "API venv not found. Run .\start.cmd first."
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Stop-UvicornOnPort $Port

Get-ChildItem -Path $ApiDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
  ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

$logOut = Join-Path $LogDir "api.out.log"
$logErr = Join-Path $LogDir "api.err.log"
$argList = "-m uvicorn app.main:app --host 127.0.0.1 --port $Port"
Write-Host "Starting API on port $Port ..."
$proc = Start-Process -FilePath $ApiPy -ArgumentList $argList.Split(" ") `
  -WorkingDirectory $ApiDir -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput $logOut -RedirectStandardError $logErr

$deadline = (Get-Date).AddSeconds(30)
do {
  Start-Sleep -Seconds 1
  if ($proc.HasExited) { throw "API process exited early. See $logOut and $logErr" }
  if (Test-ApiFresh) {
    Write-Host "API ready (PID=$($proc.Id)) with updated Gemini handlers."
    exit 0
  }
} while ((Get-Date) -lt $deadline)

throw "API started but still serving old schema. Close all terminals running start.cmd, then run .\start.cmd again."
