# ATIM
Api para la transferencia de imagenes medicas

## Guia de ejecución:

### 1) Abrir PowerShell en la carpeta del proyecto

### 2) Instalar mkcert una sola vez

```powershell
winget install FiloSottile.mkcert
```

### 3) Cerrar esa terminal y abrir una nueva

Esto refresca el PATH para que Windows reconozca `mkcert`.

### 4) Ejecutar el setup HTTPS

```powershell
.\scripts\https\setup_https.ps1
```

Que hace el script automaticamente:
- Crea `.env` desde `.env.example` si no existe
- Detecta `mkcert` aunque el PATH no se haya refrescado
- Instala la CA local de `mkcert` en Windows
- Genera `certs\cert.pem` y `certs\key.pem`
- Levanta Docker con HTTPS
- Verifica `https://localhost:8000/api/v1/health`

### 5) Abrir Swagger

```text
https://localhost:8000/docs
```

### 6) Verificacion manual opcional

```powershell
curl.exe https://localhost:8000/api/v1/health
```

## Troubleshooting rapido

Si `mkcert` no se reconoce:
- Cierra y abre una nueva terminal.
- Ejecuta `where mkcert`.

Si Windows muestra la advertencia para instalar la CA de `mkcert`:
- Pulsa `Sí`.

Si Docker falla por daemon:
- Abre Docker Desktop y espera que diga `Engine running`.

## Apagar servicios

```powershell
docker compose down
```