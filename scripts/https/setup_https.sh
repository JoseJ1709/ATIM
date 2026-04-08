#!/usr/bin/env sh

set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$repo_root"

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
fi

if ! command -v mkcert >/dev/null 2>&1; then
  echo "mkcert no esta instalado. Instala mkcert y vuelve a ejecutar este script." >&2
  exit 1
fi

mkdir -p certs

mkcert -install
mkcert -cert-file certs/cert.pem -key-file certs/key.pem localhost 127.0.0.1 ::1

docker compose up -d --build --force-recreate

health_url="https://localhost:8000/api/v1/health"
max_retries=30
attempt=1

while [ "$attempt" -le "$max_retries" ]; do
  if curl --silent --fail "$health_url" >/dev/null 2>&1; then
    echo "HTTPS verificado en $health_url"
    echo "Swagger: https://localhost:8000/docs"
    exit 0
  fi

  sleep 2
  attempt=$((attempt + 1))
done

echo "No se pudo verificar HTTPS en $health_url. Revisa: docker compose logs --tail 80 atim" >&2
exit 1