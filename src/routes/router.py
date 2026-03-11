from fastapi import APIRouter

from src.controllers.health_controller import router as health_router
from src.controllers.auth_controller import router as auth_router
from src.controllers.studies_controller import router as studies_router
from src.controllers.transfer_controller import router as transfer_router
from src.controllers.upload_controller import router as upload_router

# Router principal que agrupa todas las rutas
api_router = APIRouter(prefix="/api/v1")

# Health - sin autenticación (para healthchecks)
api_router.include_router(health_router, tags=["Health"])

# Auth - para obtener tokens
api_router.include_router(auth_router, tags=["Autenticación"])

# Endpoints protegidos con JWT
api_router.include_router(studies_router, tags=["Studies"])
api_router.include_router(transfer_router, tags=["Transfer"])
api_router.include_router(upload_router, tags=["Upload"])