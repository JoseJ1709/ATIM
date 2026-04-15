import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.config.settings import get_settings
from src.routes.router import api_router
from src.middlewares.logging_middleware import logging_middleware
from src.middlewares.rate_limit_middleware import rate_limit_middleware

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("atim")


def create_app() -> FastAPI:
    """Factory para crear la aplicación FastAPI."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "API intermediaria entre Orthanc (PACS) y JoeyCare.\n\n"
            "## Seguridad\n"
            "- **JWT Tokens**: Todos los endpoints (excepto /health y /auth) requieren un token JWT\n"
            "- **Cifrado AES-256**: Los archivos DICOM pueden transmitirse cifrados\n"
            "- **Rate Limiting**: Máximo 60 req/min general, 20 req/min para uploads\n"
            "- **API Keys**: Para comunicación entre servicios\n\n"
            "## Flujo de autenticación\n"
            "1. POST /api/v1/auth/token con client_id y client_secret\n"
            "2. Usar el token en header: Authorization: Bearer <token>\n"
        ),
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # === Middlewares (orden importa: se ejecutan de abajo hacia arriba) ===

    # CORS - Permitir comunicación con JoeyCare Frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",    # JoeyCare Frontend (Vite)
            "http://localhost:4000",     # JoeyCare Backend
            "http://localhost:8042",     # Orthanc Explorer
            "http://localhost:3000",     # Orthanc DICOMweb
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Response-Time",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-Encryption",
            "X-Original-Size"
        ],
    )

    # Rate Limiting
    app.add_middleware(BaseHTTPMiddleware, dispatch=rate_limit_middleware)

    # Logging
    app.add_middleware(BaseHTTPMiddleware, dispatch=logging_middleware)

    # === Rutas ===
    app.include_router(api_router)

    # === Eventos ===
    @app.on_event("startup")
    async def startup_event():
        logger.info("=" * 60)
        logger.info(f"  {settings.app_name} v{settings.app_version}")
        logger.info(f"  Entorno: {settings.app_env}")
        logger.info(f"  PACS configurado: {settings.orthanc_url}")
        logger.info(f"  DICOMweb: {'Habilitado' if settings.orthanc_use_dicomweb else 'Deshabilitado'}")
        logger.info(f"  Seguridad:")
        logger.info(f"    JWT: Habilitado (expira en {settings.access_token_expire_minutes} min)")
        logger.info(f"    AES-256: Habilitado (cifrado de payload)")
        logger.info(f"    Rate Limit: {settings.rate_limit_per_minute} req/min general, {settings.rate_limit_upload_per_minute} req/min uploads")
        logger.info("=" * 60)

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("ATIM se está apagando...")

    return app


app = create_app()