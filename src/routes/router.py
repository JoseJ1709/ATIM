from fastapi import APIRouter

from src.controllers.health_controller import router as health_router
from src.controllers.studies_controller import router as studies_router
from src.controllers.transfer_controller import router as transfer_router

# Router principal que agrupa todas las rutas
api_router = APIRouter(prefix="/api/v1")

# Registrar los routers de cada módulo
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(studies_router, tags=["Studies"])
api_router.include_router(transfer_router, tags=["Transfer"])