import httpx
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from src.config.settings import Settings, get_settings
from src.services.transfer_service import TransferService
from src.models.schemas import (
    TransferInstanceRequest,
    TransferSeriesRequest,
    TransferResult,
    TransferSeriesResult,
    ErrorResponse,
)

router = APIRouter()


def get_transfer_service(settings: Settings = Depends(get_settings)) -> TransferService:
    """Inyección de dependencias para el servicio de transferencia."""
    return TransferService(settings)


# ============================
# ESTADO DE JOYCARE
# ============================

@router.get(
    "/joycare/status",
    summary="Estado de JoyCare",
    description="Verifica la conexión con el backend de JoyCare.",
    responses={502: {"model": ErrorResponse}}
)
async def check_joycare_status(service: TransferService = Depends(get_transfer_service)):
    try:
        return await service.check_joycare_connection()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error verificando JoyCare: {str(e)}")


@router.get(
    "/joycare/neonatos",
    summary="Listar neonatos de JoyCare",
    description="Obtiene la lista de neonatos desde JoyCare para seleccionar destino.",
    responses={502: {"model": ErrorResponse}}
)
async def list_joycare_neonatos(service: TransferService = Depends(get_transfer_service)):
    try:
        return await service.get_joycare_neonatos()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error obteniendo neonatos: {str(e)}")


# ============================
# TRANSFERENCIA
# ============================

@router.post(
    "/transfer/instance",
    response_model=TransferResult,
    summary="Transferir una imagen DICOM",
    description=(
        "Descarga una instancia DICOM desde Orthanc (PACS) y la sube "
        "como ecografía a JoyCare, asociándola a un neonato."
    ),
    responses={
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse}
    }
)
async def transfer_instance(
    request: TransferInstanceRequest,
    service: TransferService = Depends(get_transfer_service)
):
    try:
        result = await service.transfer_instance(
            instance_id=request.instance_id,
            neonato_id=request.neonato_id,
            uploader_medico_id=request.uploader_medico_id,
            sede_id=request.sede_id
        )
        return result
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(
                status_code=400,
                detail=f"Instancia o neonato no encontrado: {str(e)}"
            )
        raise HTTPException(status_code=502, detail=f"Error en la transferencia: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error en la transferencia: {str(e)}")


@router.post(
    "/transfer/series",
    response_model=TransferSeriesResult,
    summary="Transferir una serie completa",
    description=(
        "Descarga TODAS las instancias de una serie desde Orthanc (PACS) "
        "y las sube a JoyCare como ecografías del neonato seleccionado."
    ),
    responses={
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse}
    }
)
async def transfer_series(
    request: TransferSeriesRequest,
    service: TransferService = Depends(get_transfer_service)
):
    try:
        result = await service.transfer_series(
            series_id=request.series_id,
            neonato_id=request.neonato_id,
            uploader_medico_id=request.uploader_medico_id,
            sede_id=request.sede_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error en la transferencia: {str(e)}")