import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.config.settings import get_settings
from src.routes.router import api_router
from src.middlewares.logging_middleware import logging_middleware

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
            "API para la transferencia segura y cifrada de imágenes médicas DICOM. "
            "Actúa como middleware entre sistemas PACS (Orthanc) y aplicaciones "
            "de visualización (JoyCare)."
        ),
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # === Middlewares ===

    # CORS - Permitir comunicación con JoyCare
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            f"http://localhost:3000",     # JoyCare frontend
            f"http://joycare-frontend:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
        logger.info("=" * 60)

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("ATIM se está apagando...")

    return app


app = create_app()