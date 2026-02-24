from datetime import datetime, timezone

from src.config.settings import Settings
from src.repositories.orthanc_repository import OrthancRepository
from src.models.schemas import HealthResponse, PacsStatusResponse


class HealthService:
    """Servicio para verificar el estado del sistema y sus conexiones."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.orthanc_repo = OrthancRepository(settings)

    def get_health(self) -> HealthResponse:
        """Obtener el estado de salud de la API."""
        return HealthResponse(
            status="healthy",
            app_name=self.settings.app_name,
            version=self.settings.app_version,
            environment=self.settings.app_env,
            timestamp=datetime.now(timezone.utc)
        )

    async def get_pacs_status(self) -> PacsStatusResponse:
        """Verificar el estado de conexión con Orthanc."""
        connection = await self.orthanc_repo.check_connection()
        dicomweb = False

        if connection["reachable"]:
            dicomweb = await self.orthanc_repo.check_dicomweb()

        return PacsStatusResponse(
            pacs_name="Orthanc",
            host=self.settings.orthanc_host,
            port=self.settings.orthanc_http_port,
            reachable=connection["reachable"],
            dicomweb_available=dicomweb,
            message=connection["message"],
            timestamp=datetime.now(timezone.utc)
        )