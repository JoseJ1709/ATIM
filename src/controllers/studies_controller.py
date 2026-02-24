from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from typing import List

from src.config.settings import Settings, get_settings
from src.services.studies_service import StudiesService
from src.models.schemas import (
    PatientSummary,
    StudySummary,
    StudyDetail,
    InstanceSummary,
    ErrorResponse,
)

router = APIRouter()


def get_studies_service(settings: Settings = Depends(get_settings)) -> StudiesService:
    """Inyección de dependencias para el servicio de estudios."""
    return StudiesService(settings)


# ============================
# PACIENTES
# ============================

@router.get(
    "/patients",
    response_model=List[PatientSummary],
    summary="Listar pacientes",
    description="Obtiene todos los pacientes almacenados en Orthanc.",
    responses={502: {"model": ErrorResponse}}
)
async def list_patients(service: StudiesService = Depends(get_studies_service)):
    try:
        return await service.get_all_patients()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al conectar con Orthanc: {str(e)}")


# ============================
# ESTUDIOS
# ============================

@router.get(
    "/studies",
    response_model=List[StudySummary],
    summary="Listar estudios",
    description="Obtiene todos los estudios DICOM almacenados en Orthanc.",
    responses={502: {"model": ErrorResponse}}
)
async def list_studies(service: StudiesService = Depends(get_studies_service)):
    try:
        return await service.get_all_studies()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al conectar con Orthanc: {str(e)}")


@router.get(
    "/studies/{study_id}",
    response_model=StudyDetail,
    summary="Detalle de un estudio",
    description="Obtiene el detalle completo de un estudio con todas sus series.",
    responses={404: {"model": ErrorResponse}, 502: {"model": ErrorResponse}}
)
async def get_study(study_id: str, service: StudiesService = Depends(get_studies_service)):
    try:
        return await service.get_study_detail(study_id)
    except Exception as e:
        if "404" in str(e):
            raise HTTPException(status_code=404, detail=f"Estudio {study_id} no encontrado")
        raise HTTPException(status_code=502, detail=f"Error al conectar con Orthanc: {str(e)}")


# ============================
# SERIES → INSTANCIAS
# ============================

@router.get(
    "/series/{series_id}/instances",
    response_model=List[InstanceSummary],
    summary="Listar instancias de una serie",
    description="Obtiene todas las instancias (imágenes DICOM) de una serie.",
    responses={502: {"model": ErrorResponse}}
)
async def list_series_instances(
    series_id: str,
    service: StudiesService = Depends(get_studies_service)
):
    try:
        return await service.get_series_instances(series_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al conectar con Orthanc: {str(e)}")


# ============================
# INSTANCIAS (Descarga)
# ============================

@router.get(
    "/instances/{instance_id}/file",
    summary="Descargar archivo DICOM",
    description="Descarga el archivo DICOM original de una instancia.",
    responses={502: {"model": ErrorResponse}}
)
async def download_instance_file(
    instance_id: str,
    service: StudiesService = Depends(get_studies_service)
):
    try:
        file_bytes = await service.get_instance_file(instance_id)
        return Response(
            content=file_bytes,
            media_type="application/dicom",
            headers={
                "Content-Disposition": f"attachment; filename={instance_id}.dcm"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al descargar: {str(e)}")


@router.get(
    "/instances/{instance_id}/preview",
    summary="Vista previa de imagen",
    description="Obtiene una vista previa PNG de la instancia DICOM.",
    responses={502: {"model": ErrorResponse}}
)
async def get_instance_preview(
    instance_id: str,
    service: StudiesService = Depends(get_studies_service)
):
    try:
        preview_bytes = await service.get_instance_preview(instance_id)
        return Response(
            content=preview_bytes,
            media_type="image/png"
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al obtener preview: {str(e)}")


@router.get(
    "/instances/{instance_id}/tags",
    summary="Tags DICOM de una instancia",
    description="Obtiene todos los tags DICOM simplificados de una instancia.",
    responses={502: {"model": ErrorResponse}}
)
async def get_instance_tags(
    instance_id: str,
    service: StudiesService = Depends(get_studies_service)
):
    try:
        return await service.get_instance_tags(instance_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al obtener tags: {str(e)}")