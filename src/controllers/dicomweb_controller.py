"""
Controlador DICOMweb: endpoints para consultar estudios usando el estándar DICOMweb.

Este controlador es la versión "estándar DICOM" del studies_controller.
- studies_controller: Usa API REST propietaria de Orthanc (IDs internos)
- dicomweb_controller: Usa DICOMweb estándar (UIDs DICOM universales)

Ventaja: Los endpoints aquí funcionan con cualquier PACS compatible con DICOMweb,
no solo Orthanc. Los UIDs son universales e interoperables.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from typing import List, Optional

from src.config.settings import Settings, get_settings
from src.services.dicomweb_service import DICOMwebService
from src.models.schemas import (
    StudySummary,
    StudyDetail,
    InstanceSummary,
    ErrorResponse,
)

router = APIRouter()


def get_dicomweb_service(settings: Settings = Depends(get_settings)) -> DICOMwebService:
    """Inyección de dependencias para el servicio DICOMweb."""
    return DICOMwebService(settings)


# ============================
# ESTUDIOS (DICOMweb)
# ============================

@router.get(
    "/dicomweb/studies",
    response_model=List[StudySummary],
    summary="Listar estudios (DICOMweb)",
    description=(
        "Obtiene todos los estudios DICOM usando el estándar DICOMweb (QIDO-RS).\n\n"
        "**Diferencia con /studies:**\n"
        "- Usa UIDs estándar DICOM (universales, interoperables)\n"
        "- Funciona con cualquier PACS compatible con DICOMweb\n"
        "- No depende de IDs internos de Orthanc\n\n"
        "**UIDs devueltos:** StudyInstanceUID (ej: 1.3.12.2.1107...)"
    ),
    responses={502: {"model": ErrorResponse}}
)
async def list_dicomweb_studies(service: DICOMwebService = Depends(get_dicomweb_service)):
    """
    Listar todos los estudios via DICOMweb (QIDO-RS).
    
    Los IDs retornados son StudyInstanceUID estándar DICOM, no IDs de Orthanc.
    """
    try:
        return await service.get_all_studies()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al conectar con DICOMweb: {str(e)}")

@router.get(
    "/dicomweb/studies/search",
    response_model=List[StudySummary],
    summary="Buscar ecografías (DICOMweb)",
    responses={502: {"model": ErrorResponse}}
)
async def search_dicomweb_ecographs(
    patient_id: Optional[str] = None,
    patient_name: Optional[str] = None,
    study_date_from: Optional[str] = None,
    study_date_to: Optional[str] = None,
    service: DICOMwebService = Depends(get_dicomweb_service)
):


    """
    Buscar ecografías (US) con filtros via DICOMweb.
    
    Parámetros query (todos opcionales):
        - patient_id: ID exacto del paciente
        - patient_name: Nombre del paciente (ej: "Maria*" para wildcards)
        - study_date_from: Desde (YYYYMMDD)
        - study_date_to: Hasta (YYYYMMDD)
    """
    try:
        return await service.search_ecograph_studies(
            patient_id=patient_id,
            patient_name=patient_name,
            study_date_from=study_date_from,
            study_date_to=study_date_to
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error en búsqueda: {str(e)}")


@router.get(
    "/dicomweb/studies/{study_uid}",
    response_model=StudyDetail,
    summary="Detalle de un estudio (DICOMweb)",
    responses={404: {"model": ErrorResponse}, 502: {"model": ErrorResponse}}
)
async def get_dicomweb_study(study_uid: str, service: DICOMwebService = Depends(get_dicomweb_service)):
    """
    Obtener detalle de un estudio via DICOMweb (QIDO-RS).
    
    Args:
        study_uid: StudyInstanceUID en formato DICOM
        
    Ejemplo:
        GET /api/v1/dicomweb/studies/1.3.12.2.1107.5.4.3.123456789...
    """
    try:
        return await service.get_study_detail(study_uid)
    except Exception as e:
        if "404" in str(e):
            raise HTTPException(
                status_code=404,
                detail=f"Estudio {study_uid} no encontrado en DICOMweb"
            )
        raise HTTPException(status_code=502, detail=f"Error al conectar con DICOMweb: {str(e)}")


# ============================
# SERIES (DICOMweb)
# ============================

@router.get(
    "/dicomweb/studies/{study_uid}/series/{series_uid}/instances",
    response_model=List[InstanceSummary],
    summary="Listar instancias de una serie (DICOMweb)",
    responses={502: {"model": ErrorResponse}}
)
async def list_dicomweb_series_instances(study_uid: str, series_uid: str, service: DICOMwebService = Depends(get_dicomweb_service)):

    """
    Listar instancias de una serie via DICOMweb (QIDO-RS).
    
    Args:
        study_uid: StudyInstanceUID
        series_uid: SeriesInstanceUID
        
    Ejemplo:
        GET /api/v1/dicomweb/studies/1.3.12.2.1107.../series/1.3.46.670589.11.../instances
    """
    try:
        return await service.get_series_instances(study_uid, series_uid)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al obtener instancias: {str(e)}")


# ============================
# INSTANCIAS (Descarga - DICOMweb)
# ============================

@router.get(
    "/dicomweb/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/file",
    summary="Descargar archivo DICOM (DICOMweb)",
    responses={502: {"model": ErrorResponse}}
)
async def download_dicomweb_instance_file(
    study_uid: str,
    series_uid: str,
    instance_uid: str,
    service: DICOMwebService = Depends(get_dicomweb_service),
):
    """
    Descargar archivo DICOM via DICOMweb (WADO-RS).
    """
    try:
        file_bytes = await service.get_instance_file(study_uid, series_uid, instance_uid)
        return Response(
            content=file_bytes,
            media_type="application/dicom",
            headers={"Content-Disposition": f"attachment; filename={instance_uid}.dcm"},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al descargar: {str(e)}")

@router.get(
    "/dicomweb/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/tags",
    summary="Tags DICOM de una instancia (DICOMweb)",
    responses={502: {"model": ErrorResponse}}
)
async def get_dicomweb_instance_tags(study_uid: str, series_uid: str, instance_uid: str, service: DICOMwebService = Depends(get_dicomweb_service)):

    """
    Obtener tags DICOM de una instancia via DICOMweb.
    
    Retorna: Diccionario con tags parseados
    """
    try:
        return await service.get_instance_tags(study_uid, series_uid, instance_uid)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al obtener tags: {str(e)}")


# ============================
# BÚSQUEDA AVANZADA
# ============================

# ============================
# VALIDACIÓN DE SERIES
# ============================

@router.get(
    "/dicomweb/studies/{study_uid}/series/{series_uid}/is-ultrasound",
    summary="Verificar si es ultrasound",
)
async def check_dicomweb_ultrasound(study_uid: str, series_uid: str, service: DICOMwebService = Depends(get_dicomweb_service)):

    """
    Verificar si una serie es ultrasound (US).
    
    Retorna:
        {
          "is_ultrasound": True,
          "modality": "US"
        }
    """
    try:
        is_us = await service.is_ultrasound_series(study_uid, series_uid)
        return {
            "is_ultrasound": is_us,
            "modality": "US" if is_us else "OTHER"
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al verificar modalidad: {str(e)}")


@router.get(
    "/dicomweb/studies/{study_uid}/series/{series_uid}/is-etf",
    summary="Verificar si es ETF (Ecografía Transfontanelar)",
)
async def check_dicomweb_etf(study_uid: str, series_uid: str, service: DICOMwebService = Depends(get_dicomweb_service)):

    """
    Verificar si una serie es potencialmente ETF.
    
    Verifica:
    1. Que sea ultrasound (US)
    2. Que la descripción contenga keywords típicos de ETF
    
    Retorna:
        {
          "is_etf": True,
          "is_ultrasound": True,
          "keywords_found": ["transfontanelar", "fontanelle"]
        }
    """
    try:
        is_us = await service.is_ultrasound_series(study_uid, series_uid)
        
        if not is_us:
            return {
                "is_etf": False,
                "is_ultrasound": False,
                "reason": "No es ultrasound (US)"
            }
        
        is_etf = await service.is_transfontanelar_echography(
            study_uid, series_uid
        )
        
        return {
            "is_etf": is_etf,
            "is_ultrasound": True,
            "note": "Analisis basado en descripción de la serie"
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al verificar ETF: {str(e)}")