import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.config.settings import Settings, get_settings
from src.services.auth_service import AuthService, get_auth_service, require_jwt

logger = logging.getLogger("atim")
router = APIRouter(prefix="/auth", tags=["Autenticación"])


# ============================
# SCHEMAS DE AUTH
# ============================

class LoginRequest(BaseModel):
    """Credenciales para obtener un token JWT."""
    client_id: str
    client_secret: str


class TokenResponse(BaseModel):
    """Respuesta con el token JWT."""
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    client_id: str
    role: str


class TokenVerifyResponse(BaseModel):
    """Respuesta de verificación de token."""
    valid: bool
    client_id: str
    role: str
    issued_at: str
    expires_at: str


# ============================
# CLIENTES AUTORIZADOS
# Estos son los sistemas que pueden autenticarse contra ATIM
# En producción se guardarían en base de datos
# ============================

AUTHORIZED_CLIENTS = {
    "joeycare-frontend": {
        "secret": "joeycare-frontend-secret-2026",
        "role": "frontend",
        "description": "JoeyCare Frontend (React/Vite)"
    },
    "joeycare-backend": {
        "secret": "joeycare-backend-secret-2026",
        "role": "backend",
        "description": "JoeyCare Backend (Node.js)"
    },
    "admin": {
        "secret": "admin-secret-2026-cambiar",
        "role": "admin",
        "description": "Administrador del sistema"
    }
}


# ============================
# ENDPOINTS
# ============================

@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Obtener token JWT",
    description=(
        "Autentica un cliente (JoeyCare Frontend/Backend) y retorna un token JWT. "
        "El token debe enviarse en el header Authorization: Bearer <token>"
    )
)
async def login(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Autenticar un cliente y generar un token JWT."""

    client = AUTHORIZED_CLIENTS.get(request.client_id)

    if not client or client["secret"] != request.client_secret:
        logger.warning(f"Intento de login fallido: client_id={request.client_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Crear token
    token = auth_service.create_access_token(
        data={
            "sub": request.client_id,
            "role": client["role"],
            "description": client["description"]
        }
    )

    settings = get_settings()
    logger.info(f"Login exitoso: {request.client_id} (role={client['role']})")

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_minutes=settings.access_token_expire_minutes,
        client_id=request.client_id,
        role=client["role"]
    )


@router.get(
    "/verify",
    response_model=TokenVerifyResponse,
    summary="Verificar token JWT",
    description="Verifica si un token JWT es válido y retorna la información del cliente."
)
async def verify_token(payload: dict = Depends(require_jwt)):
    """Verificar si un token JWT es válido."""
    from datetime import datetime, timezone

    return TokenVerifyResponse(
        valid=True,
        client_id=payload.get("sub", ""),
        role=payload.get("role", ""),
        issued_at=datetime.fromtimestamp(payload.get("iat", 0), tz=timezone.utc).isoformat(),
        expires_at=datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc).isoformat()
    )