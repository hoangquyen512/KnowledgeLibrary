#Requires -Version 5.1
<#
.SYNOPSIS
  Start local dev stack (API + Web) without Docker.

.EXAMPLE
  .\start.cmd
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $Root "apps\api"
$WebDir = Join-Path $Root "apps\web"
$EnvTemplate = Join-Path $Root ".env.example"
$DataDir = Join-Path $ApiDir "data"

if (-not (Test-Path $EnvTemplate)) {
  throw ".env.example not found at $EnvTemplate"
}

$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

function Read-EnvMap([string]$Path) {
  $map = [ordered]@{}
  if (-not (Test-Path $Path)) { return $map }
  Get-Content $Path | ForEach-Object {
    $line = $_
    if ($line -match '^\s*#' -or $line -match '^\s*$') { return }
    $parts = $line.Split("=", 2)
    if ($parts.Length -eq 2) {
      $map[$parts[0].Trim()] = $parts[1]
    }
  }
  return $map
}

function Merge-EnvTemplate([string]$TemplatePath, [string]$TargetPath) {
  <#
    Seed target from template once. Never overwrite keys that already exist in target
    (preserves GOOGLE_CLIENT_ID / SECRET the user pasted).
    Only appends missing keys from the template.
  #>
  if (-not (Test-Path $TargetPath)) {
    Copy-Item $TemplatePath $TargetPath
    Write-Host "Created $TargetPath from template."
    return
  }

  $existing = Read-EnvMap $TargetPath
  $template = Read-EnvMap $TemplatePath
  $toAppend = @()
  foreach ($key in $template.Keys) {
    if (-not $existing.Contains($key)) {
      $toAppend += "$key=$($template[$key])"
    }
  }
  if ($toAppend.Count -gt 0) {
    Add-Content -Path $TargetPath -Value ""
    Add-Content -Path $TargetPath -Value "# --- added from .env.example (missing keys) ---"
    Add-Content -Path $TargetPath -Value $toAppend
    Write-Host "Merged $($toAppend.Count) missing key(s) into $TargetPath (existing values kept)."
  } else {
    Write-Host "Keeping existing $TargetPath (not overwritten)."
  }
}

$ApiEnv = Join-Path $ApiDir ".env"
$WebEnv = Join-Path $WebDir ".env.local"
Merge-EnvTemplate $EnvTemplate $ApiEnv
Merge-EnvTemplate $EnvTemplate $WebEnv

# Load process env from apps/api/.env — skip blank values so they cannot
# override the file later (pydantic prefers non-empty env vars).
$map = Read-EnvMap $ApiEnv
foreach ($key in $map.Keys) {
  $val = [string]$map[$key]
  if ([string]::IsNullOrWhiteSpace($val)) { continue }
  [System.Environment]::SetEnvironmentVariable([string]$key, $val.Trim().Trim('"').Trim("'"), "Process")
}
$googleReady = -not [string]::IsNullOrWhiteSpace($map["GOOGLE_CLIENT_ID"]) -and -not [string]::IsNullOrWhiteSpace($map["GOOGLE_CLIENT_SECRET"])
Write-Host "Google OAuth in apps/api/.env: $(if ($googleReady) { 'configured' } else { 'NOT configured' })"

if (-not (Test-Path (Join-Path $ApiDir ".venv\Scripts\python.exe"))) {
  Push-Location $ApiDir
  uv venv .venv
  Pop-Location
}

Push-Location $ApiDir
uv pip install -r requirements.txt | Out-Host
Pop-Location

if (-not (Test-Path (Join-Path $WebDir "node_modules"))) {
  Push-Location $WebDir
  npm install
  Pop-Location
}

function Test-PortListening([int]$Port) {
  try {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
      Select-Object -First 1
    return $null -ne $c
  } catch {
    return $false
  }
}

function Stop-UvicornOnPort([int]$Port) {
  try {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
      Where-Object {
        ($_.CommandLine -match "uvicorn" -and $_.CommandLine -match "--port\s+$Port") -or
        ($_.CommandLine -match "multiprocessing\.spawn" -and $_.CommandLine -match "spawn_main") -or
        ($_.CommandLine -match "app\.scripts\.ask_ai_migrate")
      } |
      ForEach-Object {
        cmd.exe /c "taskkill /PID $($_.ProcessId) /T /F >nul 2>&1" | Out-Null
      }
  } catch { }
}

function Stop-PortListeners([int]$Port) {
  # Native taskkill stderr must not abort the script ($ErrorActionPreference=Stop).
  Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object {
      $pidToKill = $_.OwningProcess
      if (-not $pidToKill) { return }
      cmd.exe /c "taskkill /PID $pidToKill /T /F >nul 2>&1" | Out-Null
    }
  Start-Sleep -Milliseconds 400
}

function Test-HttpOk([string]$Url, [int]$TimeoutSec = 2) {
  try {
    $resp = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec $TimeoutSec
    return $resp.StatusCode -eq 200
  } catch {
    return $false
  }
}

function Start-HiddenProcess {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(Mandatory = $true)][string[]]$ArgumentList,
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][string]$LogFile
  )
  $dir = Split-Path -Parent $LogFile
  if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  # CreateNoWindow = true → no console popup for API/Web children
  $argString = ($ArgumentList | ForEach-Object {
    if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ }
  }) -join ' '

  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $FilePath
  $psi.Arguments = $argString
  $psi.WorkingDirectory = $WorkingDirectory
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true

  $proc = New-Object System.Diagnostics.Process
  $proc.StartInfo = $psi
  $proc.EnableRaisingEvents = $false

  $logWriter = [System.IO.StreamWriter]::new($LogFile, $true)
  $logWriter.AutoFlush = $true
  $handler = {
    if (-not [string]::IsNullOrEmpty($EventArgs.Data)) {
      $Event.MessageData.WriteLine($EventArgs.Data)
    }
  }
  $outToken = Register-ObjectEvent -InputObject $proc -EventName OutputDataReceived -Action $handler -MessageData $logWriter
  $errToken = Register-ObjectEvent -InputObject $proc -EventName ErrorDataReceived -Action $handler -MessageData $logWriter

  [void]$proc.Start()
  $proc.BeginOutputReadLine()
  $proc.BeginErrorReadLine()

  return [pscustomobject]@{
    Process   = $proc
    LogFile   = $LogFile
    OutToken  = $outToken
    ErrToken  = $errToken
    LogWriter = $logWriter
  }
}

function Stop-ManagedProcess($Managed) {
  if (-not $Managed) { return }
  try {
    if ($Managed.Process -and -not $Managed.Process.HasExited) {
      $pidToKill = $Managed.Process.Id
      cmd.exe /c "taskkill /PID $pidToKill /T /F >nul 2>&1" | Out-Null
    }
  } catch { }
  try {
    if ($Managed.OutToken) { Unregister-Event -SourceIdentifier $Managed.OutToken.Name -ErrorAction SilentlyContinue }
    if ($Managed.ErrToken) { Unregister-Event -SourceIdentifier $Managed.ErrToken.Name -ErrorAction SilentlyContinue }
  } catch { }
  try { if ($Managed.LogWriter) { $Managed.LogWriter.Dispose() } } catch { }
}

$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# Kill hung previous instances so we start clean
Write-Host "Resetting ports 8000 / 3000 if occupied..."
Stop-UvicornOnPort 8000
Stop-PortListeners 8000
Stop-PortListeners 3000
Start-Sleep -Seconds 1

# OneDrive Files On-Demand can cloud-placeholder apps/web/.next and lock
# types/app/page.ts (EBUSY) → HTTP 500. Keep a real local folder and pin it.
$nextCache = Join-Path $WebDir ".next"
try {
  $reparse = fsutil reparsepoint query $nextCache 2>$null
  if ($reparse -match '0xa0000003' -or $reparse -match 'Mount Point') {
    cmd.exe /c "rmdir `"$nextCache`"" | Out-Null
  }
} catch { }
if (Test-Path -LiteralPath $nextCache) {
  Write-Host "Clearing apps/web/.next (avoid stale OneDrive cache)..."
  try {
    Remove-Item -LiteralPath $nextCache -Recurse -Force -ErrorAction Stop
  } catch {
    Write-Warning "Could not fully clear .next: $($_.Exception.Message)"
    cmd.exe /c "rmdir /s /q `"$nextCache`"" | Out-Null
  }
}
New-Item -ItemType Directory -Force -Path $nextCache | Out-Null
cmd.exe /c "attrib +P -U `"$nextCache`"" | Out-Null

Write-Host ""
Write-Host "Local dev starting (background, no extra windows)..."
Write-Host "  Web:   http://localhost:3000"
Write-Host "  API:   http://localhost:8000/health"
Write-Host "  Login: http://localhost:3000/login  (Google sign-in required)"
if (-not $googleReady) {
  Write-Host "  WARN: Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in apps/api/.env"
}
Write-Host "  Logs:  $LogDir\api.log , $LogDir\web.log"
Write-Host ""

$managed = @()

Write-Host "Clearing apps/api Python cache..."
Get-ChildItem -Path $ApiDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
  ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
  }

$apiPy = Join-Path $ApiDir ".venv\Scripts\python.exe"
$apiManaged = Start-HiddenProcess -FilePath $apiPy -ArgumentList @(
  "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"
) -WorkingDirectory $ApiDir -LogFile (Join-Path $LogDir "api.log")
$managed += $apiManaged
Write-Host "API PID=$($apiManaged.Process.Id) (hidden)"

$npmCmd = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $npmCmd) { $npmCmd = "npm.cmd" }
# .cmd cannot start with UseShellExecute=false — run via cmd.exe with CreateNoWindow
$webManaged = Start-HiddenProcess -FilePath "$env:ComSpec" -ArgumentList @(
  "/d", "/c", "npm.cmd run dev"
) -WorkingDirectory $WebDir -LogFile (Join-Path $LogDir "web.log")
$managed += $webManaged
Write-Host "WEB PID=$($webManaged.Process.Id) (hidden)"

Write-Host "Waiting for services..."
$deadline = (Get-Date).AddSeconds(120)
$apiOk = $false
$webOk = $false
do {
  Start-Sleep -Seconds 2
  $apiOk = (Test-PortListening 8000) -and (Test-HttpOk "http://127.0.0.1:8000/health" 2)
  $webOk = (Test-PortListening 3000) -or (Test-HttpOk "http://127.0.0.1:3000/" 3)
  if ($apiOk -and $webOk) { break }
  Write-Host "  ... api=$apiOk web=$webOk"
} while ((Get-Date) -lt $deadline)

if (-not ($apiOk -and $webOk)) {
  foreach ($m in $managed) { Stop-ManagedProcess $m }
  throw "Local dev failed to become healthy (api=$apiOk web=$webOk). See logs in $LogDir"
}

$null = Test-HttpOk "http://127.0.0.1:3000/" 10

Write-Host ""
Write-Host "Local dev is ready (API/Web running hidden)."
Write-Host "  Open http://localhost:3000/login"
Write-Host "Press Ctrl+C in this window to stop."

$failStreak = 0
try {
  while ($true) {
    Start-Sleep -Seconds 10
    $apiUp = (Test-PortListening 8000) -or (Test-HttpOk "http://127.0.0.1:8000/health" 2)
    $webUp = (Test-PortListening 3000) -or (Test-HttpOk "http://127.0.0.1:3000/" 3)
    if ($apiUp -and $webUp) {
      $failStreak = 0
      continue
    }
    $failStreak++
    Write-Warning "Port check failed (api=$apiUp web=$webUp) attempt $failStreak"
    if ($failStreak -ge 3) {
      throw "Local dev services stopped responding on ports 8000/3000. See logs in $LogDir"
    }
  }
}
finally {
  foreach ($m in $managed) { Stop-ManagedProcess $m }
  Stop-PortListeners 8000
  Stop-PortListeners 3000
}
