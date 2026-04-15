import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.config.settings import Settings, get_settings

logger = logging.getLogger("atim")

# Esquema de seguridad Bearer para Swagger
security_scheme = HTTPBearer(
    scheme_name="JWT Bearer",
    description="Token JWT obtenido desde /api/v1/auth/token"
)


class AuthService:
    """Servicio de autenticación y autorización con JWT."""

    def __init__(self, settings: Settings):
        self.secret_key = settings.secret_key
        self.algorithm = settings.algorithm
        self.expire_minutes = settings.access_token_expire_minutes

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Crear un JWT token.

        Args:
            data: Payload del token (sub, role, etc.)
            expires_delta: Tiempo de expiración personalizado

        Returns:
            Token JWT firmado
        """
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=self.expire_minutes))

        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "iss": "ATIM"
        })

        token = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        logger.info(f"Token JWT creado para: {data.get('sub', 'unknown')}")
        return token

    def verify_token(self, token: str) -> dict:
        """
        Verificar y decodificar un JWT token.

        Args:
            token: Token JWT a verificar

        Returns:
            Payload decodificado

        Raises:
            HTTPException si el token es inválido
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            subject = payload.get("sub")
            if subject is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token inválido: falta 'sub'",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            return payload
        except JWTError as e:
            logger.warning(f"Token JWT inválido: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token inválido o expirado: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"}
            )


def get_auth_service(settings: Settings = Depends(get_settings)) -> AuthService:
    """Inyección de dependencias para AuthService."""
    return AuthService(settings)


async def require_jwt(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    settings: Settings = Depends(get_settings)
) -> dict:
    """
    Dependencia de FastAPI que exige un JWT válido.
    Usar en cualquier endpoint que requiera autenticación.

    Returns:
        Payload del token decodificado
    """
    auth_service = AuthService(settings)
    return auth_service.verify_token(credentials.credentials)


async def require_role(required_role: str):
    """
    Factory para crear dependencias que exigen un rol específico.

    Uso:
        @router.get("/admin", dependencies=[Depends(require_role("admin"))])
    """
    async def role_checker(
        payload: dict = Depends(require_jwt)
    ) -> dict:
        user_role = payload.get("role", "")
        if user_role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Se requiere rol '{required_role}', tienes '{user_role}'"
            )
        return payload
    return role_checker