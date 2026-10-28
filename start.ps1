<#
.SYNOPSIS
  Starts the whole Reality AI site on this machine: database, backend + AI, frontend.

.DESCRIPTION
  1. Starts the PostgreSQL/PostGIS/pgvector container (docker compose).
  2. Applies the backend's database migrations.
  3. On the first run (no listings yet), seeds demo data and embeds it.
  4. Opens two windows: the backend (FastAPI + the AI on the GPU) on :8000
     and the frontend (Next.js) on :3000.

  Run from the repo root:   .\start.ps1
  Fresh demo data:          .\start.ps1 -Reseed
  Frontend dev mode:        .\start.ps1 -Dev       (hot reload, slower pages)

  Stop: close the two windows, then `docker compose stop`.
#>
param(
    [switch]$Reseed,
    [switch]$Dev
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

# ── Checks ───────────────────────────────────────────────────────────────
if (-not (Test-Path $python)) {
    throw "No Python environment at .venv. Create it and install ai\requirements.txt and backend\requirements.txt (see README)."
}
if (-not (Test-Path (Join-Path $root ".env"))) {
    throw "No .env at the repo root. Copy .env.example to .env and set SECRET_KEY (see README)."
}
if (-not (Select-String -Path (Join-Path $root ".env") -Pattern '^SECRET_KEY=.{32,}' -Quiet)) {
    throw "SECRET_KEY in .env is missing or shorter than 32 characters."
}
if (-not (Test-Path (Join-Path $root "frontend\.env.local"))) {
    Copy-Item (Join-Path $root "frontend\.env.example") (Join-Path $root "frontend\.env.local")
    Write-Host "Created frontend\.env.local from the example (add a Google Maps key there for the map)."
}

# ── Stop servers left over from an earlier run ───────────────────────────
# An old backend still holding port 8000 keeps answering with old code while
# the new one fails to start, so clear our own leftovers first.  Anything
# else on these ports is reported, never killed.
foreach ($port in 8000, 3000) {
    $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($procId in ($listeners.OwningProcess | Sort-Object -Unique)) {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$procId").CommandLine
        $ours = $cmd -and ($cmd -match "app\.main:app" -or ($cmd -match "next" -and $cmd -match [regex]::Escape($root)))
        if ($ours) {
            Write-Host "Stopping the previous Reality AI server on port $port (PID $procId)."
            Stop-Process -Id $procId -Force
        } else {
            throw "Port $port is used by another program (PID $procId): $cmd. Close it and run again."
        }
    }
}

# ── Database ─────────────────────────────────────────────────────────────
Step "Starting the database"
docker compose -f (Join-Path $root "docker-compose.yml") up -d --wait
if ($LASTEXITCODE -ne 0) { throw "docker compose failed. Is Docker Desktop running?" }

Step "Applying database migrations"
Push-Location (Join-Path $root "backend")
try {
    & $python setup_local.py
    if ($LASTEXITCODE -ne 0) { throw "Migrations failed." }

    $count = & $python -c "from sqlalchemy import text; from app.core.database import engine; print(engine.connect().execute(text('SELECT count(*) FROM listing')).scalar())"
    if ($Reseed -or [int]$count -eq 0) {
        Step "Seeding demo data"
        & $python -m app.db.seed_synthetic_data --reset
        if ($LASTEXITCODE -ne 0) { throw "Seeding failed." }
        & $python seed_demo_user.py
        if ($LASTEXITCODE -ne 0) { throw "Demo users failed." }
    }
} finally {
    Pop-Location
}

Step "Embedding listings that need it"
Push-Location $root
try {
    & $python -m ai.embeddings.embed_listings
    if ($LASTEXITCODE -ne 0) { throw "Embedding failed." }
} finally {
    Pop-Location
}

# ── Backend + frontend in their own windows ──────────────────────────────
Step "Starting the backend on http://localhost:8000 (the AI model takes ~30 s to load)"
# One worker only: each worker would load its own copy of the model onto the GPU.
Start-Process powershell -WorkingDirectory $root -ArgumentList @(
    "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'Reality AI backend'; & '$python' -m uvicorn --app-dir backend app.main:app --host 127.0.0.1 --port 8000"
)

Step "Starting the frontend on http://localhost:3000"
$frontend = Join-Path $root "frontend"
$run = if ($Dev) { "npx pnpm dev" } else { "npx pnpm build; if (`$?) { npx pnpm start }" }
Start-Process powershell -WorkingDirectory $frontend -ArgumentList @(
    "-NoExit", "-Command",
    "`$Host.UI.RawUI.WindowTitle = 'Reality AI frontend'; if (-not (Test-Path node_modules)) { npx -y pnpm install --frozen-lockfile }; $run"
)

Write-Host ""
Write-Host "Open http://localhost:3000 once both windows say they are ready." -ForegroundColor Green
Write-Host "Demo logins:  customer@reality.ai / customerpassword123"
Write-Host "              admin@reality.ai    / adminpassword123   (broker)"
