import logging
from fastapi import Request, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader

from src.config.settings import get_settings

logger = logging.getLogger("atim")

# Header donde se espera la API Key
api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="API Key",
    description="API Key para comunicación ATIM <-> servicios externos",
    auto_error=False
)


async def require_api_key(
    api_key: str = Security(api_key_header)
) -> str:
    """
    Dependencia que valida la API Key en el header X-API-Key.
    Usar en endpoints que comunican con servicios externos (PACS, etc.)
    """
    settings = get_settings()

    if not api_key:
        logger.warning("Request sin API Key")
        raise HTTPException(
            status_code=401,
            detail="API Key requerida en header 'X-API-Key'"
        )

    if api_key != settings.api_key_atim:
        logger.warning(f"API Key inválida recibida: {api_key[:8]}...")
        raise HTTPException(
            status_code=403,
            detail="API Key inválida"
        )

    logger.debug("API Key validada correctamente")
    return api_key