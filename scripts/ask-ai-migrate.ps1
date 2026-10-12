#Requires -Version 5.1
<#
.SYNOPSIS
  Ask AI migration helper: schema patches + optional re-index.

.EXAMPLE
  .\scripts\ask-ai-migrate.ps1 -List
  .\scripts\ask-ai-migrate.ps1 -SchemaOnly
  .\scripts\ask-ai-migrate.ps1 -WorkspaceId 86d08790-e3cd-4348-9f38-da149cfc1cb3
  .\scripts\ask-ai-migrate.ps1 -All
#>
param(
  [switch]$List,
  [switch]$SchemaOnly,
  [switch]$All,
  [string]$SourceId,
  [string]$WorkspaceId
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $Root "apps\api"
$EmbedDir = Join-Path $Root "apps\embedding-service"

function Test-EmbeddingService {
  try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:8081/health" -TimeoutSec 2
    return $r.status -eq "ok"
  } catch {
    return $false
  }
}

if (-not (Test-EmbeddingService)) {
  Write-Host "Starting embedding stub on http://127.0.0.1:8081 ..."
  Start-Process -WindowStyle Hidden -WorkingDirectory $EmbedDir -FilePath "uv" -ArgumentList @(
    "run", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8081"
  ) | Out-Null
  Start-Sleep -Seconds 2
  if (-not (Test-EmbeddingService)) {
    Write-Warning "Embedding service not reachable. Re-index will still run but vector search may use zero vectors."
  }
}

$argsList = @()
if ($List) { $argsList += "--list" }
if ($SchemaOnly) { $argsList += "--schema-only" }
if ($All) { $argsList += "--all" }
if ($SourceId) { $argsList += @("--source-id", $SourceId) }
if ($WorkspaceId) { $argsList += @("--workspace-id", $WorkspaceId) }

if ($argsList.Count -eq 0) {
  $argsList = @("--list")
}

Push-Location $ApiDir
try {
  uv run python -m app.scripts.ask_ai_migrate @argsList
} finally {
  Pop-Location
}
