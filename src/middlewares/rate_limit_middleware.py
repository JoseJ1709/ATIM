import time
import logging
from collections import defaultdict
from fastapi import Request, HTTPException

logger = logging.getLogger("atim")


class RateLimiter:
    """
    Rate limiter en memoria basado en ventana deslizante.
    Limita requests por IP por minuto.
    """

    def __init__(self):
        # {ip: [timestamp1, timestamp2, ...]}
        self.requests: dict = defaultdict(list)
        self.upload_requests: dict = defaultdict(list)

    def _clean_old_requests(self, request_list: list, window_seconds: int = 60) -> list:
        """Eliminar requests fuera de la ventana de tiempo."""
        now = time.time()
        return [ts for ts in request_list if now - ts < window_seconds]

    def check_rate_limit(self, client_ip: str, limit: int) -> bool:
        """
        Verificar si el cliente excedió el rate limit general.

        Returns:
            True si está dentro del límite, False si lo excedió
        """
        self.requests[client_ip] = self._clean_old_requests(self.requests[client_ip])

        if len(self.requests[client_ip]) >= limit:
            logger.warning(f"Rate limit excedido para IP: {client_ip} ({len(self.requests[client_ip])}/{limit})")
            return False

        self.requests[client_ip].append(time.time())
        return True

    def check_upload_rate_limit(self, client_ip: str, limit: int) -> bool:
        """
        Verificar rate limit específico para uploads.

        Returns:
            True si está dentro del límite, False si lo excedió
        """
        self.upload_requests[client_ip] = self._clean_old_requests(self.upload_requests[client_ip])

        if len(self.upload_requests[client_ip]) >= limit:
            logger.warning(f"Upload rate limit excedido para IP: {client_ip}")
            return False

        self.upload_requests[client_ip].append(time.time())
        return True

    def get_remaining(self, client_ip: str, limit: int) -> int:
        """Obtener requests restantes para un cliente."""
        self.requests[client_ip] = self._clean_old_requests(self.requests[client_ip])
        return max(0, limit - len(self.requests[client_ip]))


# Instancia global del rate limiter
rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """
    Middleware que aplica rate limiting por IP.
    """
    from src.config.settings import get_settings
    settings = get_settings()

    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path

    # Rate limit más estricto para uploads
    if "/upload" in path:
        if not rate_limiter.check_upload_rate_limit(client_ip, settings.rate_limit_upload_per_minute):
            logger.warning(f"Upload rate limit: {client_ip} en {path}")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit excedido para uploads. Máximo {settings.rate_limit_upload_per_minute} por minuto."
            )
    else:
        # Rate limit general
        if not rate_limiter.check_rate_limit(client_ip, settings.rate_limit_per_minute):
            remaining = rate_limiter.get_remaining(client_ip, settings.rate_limit_per_minute)
            logger.warning(f"Rate limit general: {client_ip} en {path}")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit excedido. Máximo {settings.rate_limit_per_minute} requests por minuto."
            )

    response = await call_next(request)

    # Agregar headers informativos de rate limit
    remaining = rate_limiter.get_remaining(client_ip, settings.rate_limit_per_minute)
    response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_per_minute)
    response.headers["X-RateLimit-Remaining"] = str(remaining)

    return response