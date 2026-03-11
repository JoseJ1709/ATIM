from fastapi import APIRouter, HTTPException, Depends
from src.services.transfer_service import TransferService
from src.services.auth_service import require_jwt
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transfer", tags=["Transfer"])

service = TransferService()


@router.get(
    "/joeycare/status",
    summary="Estado de JoeyCare",
    description="Verifica la conexión con JoeyCare Backend. Requiere JWT."
)
async def check_joeycare_status(payload: dict = Depends(require_jwt)):
    try:
        return await service.check_joeycare_connection()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/joeycare/neonatos",
    summary="Listar neonatos de JoeyCare",
    description="Obtiene la lista de neonatos registrados en JoeyCare. Requiere JWT."
)
async def list_joeycare_neonatos(payload: dict = Depends(require_jwt)):
    try:
        return await service.get_joeycare_neonatos()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/instance",
    summary="Transferir instancia DICOM",
    description=(
        "Descarga una instancia DICOM desde Orthanc y la sube a JoeyCare. Requiere JWT."
    )
)
async def transfer_instance(
    instance_id: str,
    neonato_id: int,
    payload: dict = Depends(require_jwt)
):
    try:
        logger.info(f"Transferencia solicitada por: {payload.get('sub', 'unknown')}")
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
        "y las sube a JoeyCare. Requiere JWT."
    )
)
async def transfer_study(
    study_id: str,
    neonato_id: int,
    payload: dict = Depends(require_jwt)
):
    try:
        logger.info(f"Transferencia estudio por: {payload.get('sub', 'unknown')}")
        return await service.transfer_study(
            study_id=study_id,
            neonato_id=neonato_id
        )
    except Exception as e:
        logger.error(f"Error en transferencia de estudio: {e}")
        raise HTTPException(status_code=500, detail=str(e))