from fastapi import APIRouter, Depends

from src.config.settings import Settings, get_settings
from src.services.health_service import HealthService
from src.models.schemas import HealthResponse, PacsStatusResponse

router = APIRouter()


def get_health_service(settings: Settings = Depends(get_settings)) -> HealthService:
    """Inyección de dependencias para el servicio de health."""
    return HealthService(settings)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Verifica que la API ATIM esté funcionando correctamente."
)
def health_check(service: HealthService = Depends(get_health_service)):
    return service.get_health()


@router.get(
    "/health/pacs",
    response_model=PacsStatusResponse,
    summary="PACS Connection Status",
    description="Verifica la conexión con Orthanc (PACS) y la disponibilidad de DICOMweb."
)
async def pacs_status(service: HealthService = Depends(get_health_service)):
    return await service.get_pacs_status()