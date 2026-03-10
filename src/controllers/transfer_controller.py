from fastapi import APIRouter, HTTPException
from src.services.transfer_service import TransferService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transfer", tags=["Transfer"])

service = TransferService()


# ============================================
# ENDPOINTS DE TRANSFERENCIA ORTHANC → JOEYCARE
# ============================================

# ESTADO DE JOEYCARE
@router.get(
    "/joeycare/status",
    summary="Estado de JoeyCare",
    description="Verifica la conexión con JoeyCare Backend."
)
async def check_joeycare_status():
    try:
        return await service.check_joeycare_connection()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/joeycare/neonatos",
    summary="Listar neonatos de JoeyCare",
    description="Obtiene la lista de neonatos registrados en JoeyCare."
)
async def list_joeycare_neonatos():
    try:
        return await service.get_joeycare_neonatos()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/instance",
    summary="Transferir instancia DICOM",
    description=(
        "Descarga una instancia DICOM específica desde Orthanc y la sube "
        "como ecografía a JoeyCare asociada a un neonato."
    )
)
async def transfer_instance(instance_id: str, neonato_id: int):
    try:
        return await service.transfer_instance(
            instance_id=instance_id,
            neonato_id=neonato_id
        )
    except Exception as e:
        logger.error(f"Error en transferencia: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/study",
    summary="Transferir estudio completo",
    description=(
        "Descarga TODAS las instancias de un estudio desde Orthanc "
        "y las sube a JoeyCare asociadas a un neonato."
    )
)
async def transfer_study(study_id: str, neonato_id: int):
    try:
        return await service.transfer_study(
            study_id=study_id,
            neonato_id=neonato_id
        )
    except Exception as e:
        logger.error(f"Error en transferencia de estudio: {e}")
        raise HTTPException(status_code=500, detail=str(e))