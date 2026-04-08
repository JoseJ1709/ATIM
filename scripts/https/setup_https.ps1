param()

$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $repoRoot

if (-not (Test-Path .\.env) -and (Test-Path .\.env.example)) {
    Copy-Item .\.env.example .\.env
}

$mkcert = $null

$command = Get-Command mkcert -ErrorAction SilentlyContinue
if ($command) {
    $mkcert = $command.Source
}

if (-not $mkcert) {
    $candidatePaths = @(
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links\mkcert.exe'),
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\FiloSottile.mkcert_Microsoft.Winget.Source_8wekyb3d8bbwe\mkcert.exe'),
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\FiloSottile.mkcert_*\mkcert.exe'),
        (Join-Path $env:USERPROFILE 'scoop\apps\mkcert\current\mkcert.exe'),
        'C:\ProgramData\chocolatey\bin\mkcert.exe'
    )

    foreach ($candidate in $candidatePaths) {
        if ($candidate.Contains('*')) {
            $found = Get-ChildItem $candidate -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($found) {
                $mkcert = $found.FullName
                break
            }

            continue
        }

        if (Test-Path $candidate) {
            $mkcert = (Resolve-Path $candidate).Path
            break
        }
    }
}

if (-not $mkcert) {
    throw "mkcert no esta instalado o no se encontro en PATH. Instala mkcert con winget y vuelve a ejecutar este script."
}

Write-Host "Usando mkcert en: $mkcert"

New-Item -ItemType Directory -Path .\certs -Force | Out-Null

Start-Process -FilePath $mkcert -ArgumentList @('-install') -NoNewWindow -Wait
Start-Process -FilePath $mkcert -ArgumentList @('-cert-file', '.\certs\cert.pem', '-key-file', '.\certs\key.pem', 'localhost', '127.0.0.1', '::1') -NoNewWindow -Wait

docker compose up -d --build --force-recreate

$healthUrl = 'https://localhost:8000/api/v1/health'
$maxRetries = 30
$isHealthy = $false

for ($i = 1; $i -le $maxRetries; $i++) {
    try {
        Invoke-RestMethod -Uri $healthUrl -Method Get | Out-Null
        $isHealthy = $true
        break
    }
    catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $isHealthy) {
    throw "No se pudo verificar HTTPS en $healthUrl. Revisa: docker compose logs --tail 80 atim"
}

Write-Host "HTTPS verificado en $healthUrl"
Write-Host "Swagger: https://localhost:8000/docs"