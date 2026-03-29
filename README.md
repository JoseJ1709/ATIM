# ATIM
Api para la transferencia de imagenes medicas

## Ejecucion desde cero en localhost con HTTPS (Windows)

Requisitos:
- Docker Desktop abierto
- PowerShell en la carpeta del proyecto

Comandos (ejecutar en este orden):

Linea 1:
```powershell
Copy-Item .env.example .env -ErrorAction SilentlyContinue
```

Linea 2:
```powershell
docker compose up -d --build --force-recreate
```

Linea 3:
```powershell
docker compose ps
```

Linea 4:
```powershell
docker compose logs --tail 40 atim
```

Linea 5:
```powershell
Start-Sleep -Seconds 5
```

Linea 6:
```powershell
curl.exe -k https://localhost:8000/api/v1/health
```

Linea 7:
```powershell
Start-Process https://localhost:8000/docs
```

Resultado esperado:
- En logs de atim debe aparecer: Uvicorn running on https://0.0.0.0:8000
- El health endpoint debe devolver un JSON con status healthy

## Confiar certificado en Windows (opcional, recomendado)

Si el navegador muestra "No es seguro", ejecuta estas lineas:

Linea 1:
```powershell
New-Item -ItemType Directory -Path .\certs -Force | Out-Null
```

Linea 2:
```powershell
docker compose cp atim:/app/certs/cert.pem .\certs\cert.pem
```

Linea 3:
```powershell
Import-Certificate -FilePath .\certs\cert.pem -CertStoreLocation Cert:\CurrentUser\Root
```

Linea 4:
```powershell
Stop-Process -Name msedge -Force -ErrorAction SilentlyContinue
```

Linea 5:
```powershell
Start-Process https://localhost:8000/docs
```

Verificacion HTTPS sin omitir validacion TLS:

```powershell
curl.exe https://localhost:8000/api/v1/health
```

Si ese comando responde JSON, la confianza del certificado quedo correcta.

## Estructura HTTPS

- Scripts: scripts/https

Apagar servicios:

```powershell
docker compose down
```
