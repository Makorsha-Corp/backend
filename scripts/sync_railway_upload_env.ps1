# Push Cloudinary + CORS env from backend/.env to linked Railway service.
# Prereq: railway login; railway link (backend service selected)
#
# Usage (from backend/):
#   powershell -ExecutionPolicy Bypass -File scripts/sync_railway_upload_env.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".env")) {
    Write-Error "backend/.env not found"
}

if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    Write-Error "railway CLI not installed (npm i -g @railway/cli)"
}

$statusOutput = railway status 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
    Write-Error "No linked Railway project. Run: railway login; railway link -p <project> -s <backend-service>"
}

$expectedHost = if ($env:EXPECTED_RAILWAY_HOST) { $env:EXPECTED_RAILWAY_HOST } else { "backend-production-847f" }
if ($statusOutput -notmatch [regex]::Escape($expectedHost)) {
    Write-Error @"
Linked Railway service does not look like the Makorsha ERP backend (expected URL containing '$expectedHost').
Current status:
$statusOutput
Run: railway link -p <project> -s <backend-service>
Or set EXPECTED_RAILWAY_HOST if your Railway URL differs.
"@
}

$envMap = @{}
Get-Content ".env" | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        $envMap[$Matches[1]] = $Matches[2].Trim('"')
    }
}

foreach ($key in @("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")) {
    if (-not $envMap.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($envMap[$key])) {
        Write-Error "Missing $key in .env"
    }
}

$vercelOrigin = if ($env:VERCEL_ORIGIN) { $env:VERCEL_ORIGIN } else { "https://frontend-theta-dusky-91.vercel.app" }
$cors = $envMap["BACKEND_CORS_ORIGINS"]
if ($cors -notlike "*$vercelOrigin*") {
    if ($cors) {
        $cors = "$cors,$vercelOrigin"
    } else {
        $cors = "$vercelOrigin,http://localhost:5173"
    }
}

Write-Host "Setting Railway variables (values hidden)..."
railway variables set `
    "CLOUDINARY_CLOUD_NAME=$($envMap['CLOUDINARY_CLOUD_NAME'])" `
    "CLOUDINARY_API_KEY=$($envMap['CLOUDINARY_API_KEY'])" `
    "CLOUDINARY_API_SECRET=$($envMap['CLOUDINARY_API_SECRET'])" `
    "CLOUDINARY_UPLOAD_ENV=production" `
    "ENVIRONMENT=production" `
    "BACKEND_CORS_ORIGINS=$cors"

if ($LASTEXITCODE -ne 0) {
    Write-Error "railway variables set failed"
}

Write-Host "OK: Cloudinary + CORS synced to Railway."
Write-Host "Next: redeploy backend service, then test phone QR upload on hosted site."
