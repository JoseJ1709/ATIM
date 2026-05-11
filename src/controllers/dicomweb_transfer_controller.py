"""
Controlador DICOMweb Transfer: endpoints para transferir imágenes desde DICOMweb a JoyCare.

Este controlador es la versión "estándar DICOM" del transfer_controller.
- transfer_controller: Usa API REST propietaria de Orthanc (IDs internos)
- dicomweb_transfer_controller: Usa DICOMweb estándar (UIDs DICOM universales)

Ventaja: Los endpoints aquí funcionan con cualquier PACS compatible con DICOMweb,
permitiendo transferencias interoperables entre sistemas.
"""

import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel, Field

from src.config.settings import Settings, get_settings
from src.services.dicomweb_transfer_service import DICOMwebTransferService
from src.services.auth_service import require_jwt
from src.models.schemas import ErrorResponse

logger = logging.getLogger("atim")

router = APIRouter()


def get_dicomweb_transfer_service(
    settings: Settings = Depends(get_settings)
) -> DICOMwebTransferService:
    """Inyección de dependencias para el servicio de transferencia DICOMweb."""
    return DICOMwebTransferService(settings)


# ============================
# SCHEMAS DE REQUEST/RESPONSE
# ============================

class TransferDICOMwebInstanceRequest(BaseModel):
    """Request para transferir una instancia via DICOMweb."""
    
    study_uid: str
    series_uid: str
    instance_uid: str
    neonato_id: int = Field(gt=0)
    uploader_medico_id: int = Field(gt=0)
    sede_id: Optional[int] = Field(default=None, gt=0)
    
    class Config:
        json_schema_extra = {
            "example": {
                "study_uid": "1.3.12.2.1107.5.4.3.123456789012345.19950922.121803.6",
                "series_uid": "1.3.46.670589.11.0.1.1996.4.96.1.20041013.161753.873",
                "instance_uid": "1.2.840.10008.5.1.4.1.1.7.4",
                "neonato_id": 1,
                "uploader_medico_id": 1,
                "sede_id": 1
            }
        }


class TransferDICOMwebSeriesRequest(BaseModel):
    """Request para transferir una serie completa via DICOMweb."""
    
    study_uid: str
    series_uid: str
    neonato_id: int = Field(gt=0)
    uploader_medico_id: int = Field(gt=0)
    sede_id: Optional[int] = Field(default=None, gt=0)
    only_etf: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "study_uid": "1.3.12.2.1107.5.4.3.123456789012345.19950922.121803.6",
                "series_uid": "1.3.46.670589.11.0.1.1996.4.96.1.20041013.161753.873",
                "neonato_id": 1,
                "uploader_medico_id": 1,
                "sede_id": 1,
                "only_etf": False
            }
        }


class TransferDICOMwebStudyRequest(BaseModel):
    """Request para transferir un estudio completo via DICOMweb."""
    
    study_uid: str
    neonato_id: int = Field(gt=0)
    uploader_medico_id: int = Field(gt=0)
    sede_id: Optional[int] = Field(default=None, gt=0)
    only_etf: bool = False
    only_ultrasound: bool = True
    
    class Config:
        json_schema_extra = {
            "example": {
                "study_uid": "1.3.12.2.1107.5.4.3.123456789012345.19950922.121803.6",
                "neonato_id": 1,
                "uploader_medico_id": 1,
                "sede_id": 1,
                "only_etf": False,
                "only_ultrasound": True
            }
        }


# ============================
# ESTADO DE JOYCARE
# ============================

@router.get(
    "/dicomweb/joycare/status",
    summary="Estado de JoyCare (DICOMweb)",
    description=(
        "Verifica la conexión con el backend de JoyCare.\n\n"
        "Útil para validar que JoyCare está disponible antes de transferir imágenes. "
        "Requiere JWT."
    ),
    responses={502: {"model": ErrorResponse}}
)
async def check_joycare_status(
    payload: dict = Depends(require_jwt),
    service: DICOMwebTransferService = Depends(get_dicomweb_transfer_service)
):
    """
    Verificar conexión con JoyCare.
    
    Retorna información del estado de JoyCare.
    """
    try:
        logger.info("🔍 Verificando estado de JoyCare...")
        result = await service.check_joeycare_connection()
        logger.info("✅ JoyCare disponible")
        return result
    except Exception as e:
        logger.error(f"❌ Error verificando JoyCare: {str(e)}")
        raise HTTPException(
            status_code=502,
            detail=f"Error verificando JoyCare: {str(e)}"
        )


@router.get(
    "/dicomweb/joycare/neonatos",
    summary="Listar neonatos de JoyCare (DICOMweb)",
    description=(
        "Obtiene la lista de todos los neonatos disponibles en JoyCare.\n\n"
        "Use los neonato_id de esta lista para especificar el destino de la transferencia. "
        "Requiere JWT."
    ),
    responses={502: {"model": ErrorResponse}}
)
async def list_joycare_neonatos(
    payload: dict = Depends(require_jwt),
    service: DICOMwebTransferService = Depends(get_dicomweb_transfer_service)
):
    """
    Obtener lista de neonatos desde JoyCare.
    
    Retorna:
        [
          {
            "id": 1,
            "nombre": "María García",
            "edad_gestacional": 28,
            "sede_id": 1
          },
          ...
        ]
    """
    try:
        logger.info("📋 Obteniendo lista de neonatos...")
        neonatos = await service.get_joeycare_neonatos()
        logger.info(f"✅ {len(neonatos)} neonatos disponibles")
        return neonatos
    except Exception as e:
        logger.error(f"❌ Error obteniendo neonatos: {str(e)}")
        raise HTTPException(
            status_code=502,
            detail=f"Error obteniendo neonatos: {str(e)}"
        )


# ============================
# TRANSFERENCIA: INSTANCIA ÚNICA (DICOMweb)
# ============================

@router.post(
    "/dicomweb/transfer/instance",
    summary="Transferir una imagen DICOM (DICOMweb)",
    description=(
        "Descarga una instancia DICOM desde DICOMweb (PACS) y la sube "
        "como ecografía a JoyCare, asociándola a un neonato.\n\n"
        "**Ventaja sobre /transfer/instance:**\n"
        "- Usa UIDs estándar DICOM (interoperables)\n"
        "- Funciona con cualquier PACS compatible con DICOMweb\n"
        "- No depende de IDs internos de Orthanc\n\n"
        "**Parámetros:**\n"
        "- study_uid: StudyInstanceUID (ej: 1.3.12.2.1107...)\n"
        "- series_uid: SeriesInstanceUID (ej: 1.3.46.670589.11...)\n"
        "- instance_uid: SOPInstanceUID (ej: 1.2.840.10008...)\n"
        "- neonato_id: ID del neonato destino\n"
        "- uploader_medico_id: ID del médico que realiza la transferencia\n\n"
        "Requiere JWT."
    ),
    responses={
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse}
    }
)
async def transfer_dicomweb_instance(
    request: TransferDICOMwebInstanceRequest,
    payload: dict = Depends(require_jwt),
    service: DICOMwebTransferService = Depends(get_dicomweb_transfer_service)
):
    """
    Transferir una instancia DICOM via DICOMweb a JoyCare.
    
    Flujo:
    1. Obtiene tags DICOM de la instancia
    2. Valida que sea compatible (modalidad US, idealmente ETF)
    3. Descarga archivo DICOM desde DICOMweb
    4. Sube a JoyCare como ecografía
    5. Retorna resultado con pista de auditoría
    
    Retorna:
        {
          "status": "success",
          "message": "Imagen transferida exitosamente",
          "study_uid": "1.3.12.2.1107...",
          "series_uid": "1.3.46.670589.11...",
          "instance_uid": "1.2.840.10008...",
          "filename": "Maria_Garcia_US_1.dcm",
          "file_size_bytes": 2048000,
          "modality": "US",
          "is_etf": True,
          "patient_name": "Maria García",
          "joycare_response": {...},
          "timestamp": "2024-04-09T14:30:45.123Z"
        }
    """
    try:
        logger.info(
            f"📥 Iniciando transferencia de instancia DICOMweb: "
            f"{request.instance_uid} → neonato {request.neonato_id}"
        )
        
        result = await service.transfer_instance(
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            instance_uid=request.instance_uid,
            neonato_id=request.neonato_id,
            uploader_medico_id=request.uploader_medico_id,
            sede_id=request.sede_id
        )
        
        logger.info(f"✅ Transferencia exitosa: {result.get('filename')}")
        return result
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.error(f"❌ Instancia o neonato no encontrado")
            raise HTTPException(
                status_code=400,
                detail=f"Instancia o neonato no encontrado: {str(e)}"
            )
        logger.error(f"❌ Error HTTP en transferencia: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Error en la transferencia: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error en transferencia de instancia: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Error en la transferencia: {str(e)}")


# ============================
# TRANSFERENCIA: SERIE COMPLETA (DICOMweb)
# ============================

@router.post(
    "/dicomweb/transfer/series",
    summary="Transferir una serie completa (DICOMweb)",
    description=(
        "Descarga TODAS las instancias de una serie desde DICOMweb (PACS) "
        "y las sube a JoyCare como ecografías del neonato seleccionado.\n\n"
        "Útil cuando una serie tiene múltiples imágenes/frames que forman un conjunto.\n\n"
        "**Parámetros:**\n"
        "- study_uid: StudyInstanceUID\n"
        "- series_uid: SeriesInstanceUID\n"
        "- neonato_id: ID del neonato destino\n"
        "- uploader_medico_id: ID del médico\n"
        "- only_etf: Si es True, solo transfiere si se confirma ETF (default: False)\n\n"
        "Requiere JWT."
    ),
    responses={
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse}
    }
)
async def transfer_dicomweb_series(
    request: TransferDICOMwebSeriesRequest,
    payload: dict = Depends(require_jwt),
    service: DICOMwebTransferService = Depends(get_dicomweb_transfer_service)
):
    """
    Transferir una serie completa via DICOMweb a JoyCare.
    
    Flujo:
    1. Obtiene lista de instancias en la serie
    2. Para cada instancia:
       - Valida modalidad (US)
       - Descarga desde DICOMweb
       - Sube a JoyCare
    3. Reporta éxitos y errores
    
    Retorna:
        {
          "status": "completed",
          "series_uid": "1.3.46.670589.11...",
          "study_uid": "1.3.12.2.1107...",
          "total_instances": 5,
          "transferred": 5,
          "failed": 0,
          "success_rate": "100.0%",
          "results": [...],  # Detalles de cada transferencia
          "errors": [...],   # Errores si los hubo
          "timestamp": "2024-04-09T14:30:45.123Z"
        }
    """
    try:
        logger.info(
            f"📥 Iniciando transferencia de serie DICOMweb: "
            f"{request.series_uid} → neonato {request.neonato_id}"
        )
        
        result = await service.transfer_series(
            study_uid=request.study_uid,
            series_uid=request.series_uid,
            neonato_id=request.neonato_id,
            uploader_medico_id=request.uploader_medico_id,
            sede_id=request.sede_id,
            only_etf=request.only_etf
        )
        
        logger.info(
            f"✅ Transferencia de serie completada: "
            f"{result.get('transferred')}/{result.get('total_instances')} imágenes"
        )
        return result
        
    except Exception as e:
        logger.error(f"❌ Error en transferencia de serie: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Error en la transferencia: {str(e)}")


# ============================
# TRANSFERENCIA: ESTUDIO COMPLETO (DICOMweb)
# ============================

@router.post(
    "/dicomweb/transfer/study",
    summary="Transferir un estudio completo (DICOMweb)",
    description=(
        "Descarga TODAS las series de un estudio desde DICOMweb (PACS) "
        "y las sube a JoyCare como ecografías del neonato seleccionado.\n\n"
        "Útil para eco completa con múltiples series (ventana anterior, posterior, etc.).\n\n"
        "**Parámetros:**\n"
        "- study_uid: StudyInstanceUID\n"
        "- neonato_id: ID del neonato destino\n"
        "- uploader_medico_id: ID del médico\n"
        "- only_etf: Si es True, solo transfiere series que sean ETF (default: False)\n"
        "- only_ultrasound: Si es True, solo transfiere series US (default: True)\n\n"
        "Requiere JWT."
    ),
    responses={
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse}
    }
)
async def transfer_dicomweb_study(
    request: TransferDICOMwebStudyRequest,
    payload: dict = Depends(require_jwt),
    service: DICOMwebTransferService = Depends(get_dicomweb_transfer_service)
):
    """
    Transferir un estudio completo via DICOMweb a JoyCare.
    
    Flujo:
    1. Obtiene todas las series del estudio
    2. Reporta series US vs otras modalidades
    3. Para cada serie:
       - Obtiene instancias
       - Descarga desde DICOMweb
       - Sube a JoyCare
    4. Retorna resumen completo
    
    Retorna:
        {
          "status": "completed",
          "study_uid": "1.3.12.2.1107...",
          "series_count": 3,
          "total_instances_transferred": 25,
          "total_errors": 0,
          "series_results": [...],  # Resultados de cada serie
          "series_errors": [...],   # Errores si los hubo
          "timestamp": "2024-04-09T14:30:45.123Z"
        }
    """
    try:
        logger.info(
            f"📥 Iniciando transferencia de estudio DICOMweb: "
            f"{request.study_uid} → neonato {request.neonato_id}"
        )
        
        result = await service.transfer_study(
            study_uid=request.study_uid,
            neonato_id=request.neonato_id,
            uploader_medico_id=request.uploader_medico_id,
            sede_id=request.sede_id,
            only_etf=request.only_etf,
            only_ultrasound=request.only_ultrasound
        )
        
        logger.info(
            f"✅ Transferencia de estudio completada: "
            f"{result.get('total_instances_transferred')} imágenes transferidas"
        )
        return result
        
    except Exception as e:
        logger.error(f"❌ Error en transferencia de estudio: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Error en la transferencia: {str(e)}")


# ============================
# INFORMACIÓN Y VALIDACIÓN
# ============================

@router.get(
    "/dicomweb/transfer/info",
    summary="Información de transferencia DICOMweb",
    description="Retorna información sobre los endpoints de transferencia disponibles. Requiere JWT."
)
async def get_dicomweb_transfer_info(
    payload: dict = Depends(require_jwt)
):
    """
    Obtener información sobre los endpoints de transferencia DICOMweb.
    
    Útil para documentar y descubrir los endpoints disponibles.
    """
    return {
        "version": "1.0.0",
        "protocol": "DICOMweb",
        "endpoints": {
            "status": "GET /api/v1/dicomweb/joycare/status",
            "neonatos": "GET /api/v1/dicomweb/joycare/neonatos",
            "transfer_instance": "POST /api/v1/dicomweb/transfer/instance",
            "transfer_series": "POST /api/v1/dicomweb/transfer/series",
            "transfer_study": "POST /api/v1/dicomweb/transfer/study"
        },
        "features": [
            "✅ Transferencia de instancias individuales",
            "✅ Transferencia de series completas",
            "✅ Transferencia de estudios completos",
            "✅ Validación de modalidad (US/ultrasound)",
            "✅ Detección de ETF (Ecografía Transfontanelar)",
            "✅ Integración con JoyCare",
            "✅ Auditoría y trazabilidad"
        ],
        "nota": (
            "Este controlador usa el estándar DICOMweb (QIDO-RS, WADO-RS) "
            "que funciona con cualquier PACS compatible, no solo Orthanc."
        )
    }