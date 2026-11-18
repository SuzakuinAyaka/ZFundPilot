param(
    [string]$Python = 'python',
    [switch]$BackendOnly
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$Repo = Split-Path -Parent $PSScriptRoot

Push-Location $Repo
try {
    npm --prefix frontend ci
    npm --prefix frontend run build

    $FrontendDist = Join-Path $Repo 'frontend/dist'
    & $Python -m PyInstaller --noconfirm --onedir `
        --name zfundpilot-backend --paths src `
        --distpath desktop/build/backend --workpath desktop/build/work `
        --specpath desktop/build --add-data "${FrontendDist}:frontend/dist" `
        --collect-data akshare --collect-data tzdata --collect-all py_mini_racer `
        --hidden-import uvicorn.loops.asyncio --hidden-import uvicorn.lifespan.on `
        src/zfundpilot/desktop_backend.py

    & $Python desktop/smoke_backend.py desktop/build/backend/zfundpilot-backend/zfundpilot-backend.exe

    if (-not $BackendOnly) {
        Push-Location desktop
        try {
            npm ci
            npm exec -- tauri build --target x86_64-pc-windows-msvc -- --locked
        } finally {
            Pop-Location
        }
    }
} finally {
    Pop-Location
}
