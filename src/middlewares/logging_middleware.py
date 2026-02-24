import time
import logging
from fastapi import Request

logger = logging.getLogger("atim")


async def logging_middleware(request: Request, call_next):
    """Middleware que registra cada petición HTTP con su tiempo de respuesta."""
    start_time = time.time()

    # Log de la petición entrante
    logger.info(f"→ {request.method} {request.url.path}")

    response = await call_next(request)

    # Calcular tiempo de respuesta
    duration = round((time.time() - start_time) * 1000, 2)
    logger.info(
        f"← {request.method} {request.url.path} "
        f"| Status: {response.status_code} "
        f"| {duration}ms"
    )

    # Header con tiempo de respuesta
    response.headers["X-Response-Time"] = f"{duration}ms"

    return response