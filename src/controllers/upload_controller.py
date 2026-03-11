from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Body
from typing import List, Optional
import logging

from src.config.settings import Settings, get_settings
from src.services.upload_service import UploadService
from src.services.encryption_service import EncryptionService
from src.services.auth_service import require_jwt
from src.models.schemas import UploadDicomResponse, UploadMultipleDicomResponse

logger = logging.getLogger("atim")
router = APIRouter(prefix="/upload", tags=["Upload - JoeyCare a Orthanc"])


def get_upload_service(settings: Settings = Depends(get_settings)) -> UploadService:
    return UploadService(settings)


@router.post(
    "/dicom",
    response_model=UploadDicomResponse,
    summary="Subir imagen DICOM a Orthanc",
    description=(
        "Recibe un archivo DICOM desde JoeyCare y lo almacena en Orthanc PACS. "
        "Requiere autenticación JWT."
    )
)
async def upload_dicom(
    file: UploadFile = File(..., description="Archivo DICOM (.dcm)"),
    payload: dict = Depends(require_jwt),
    service: UploadService = Depends(get_upload_service)
):
    logger.info(f"Upload DICOM por: {payload.get('sub', 'unknown')}")

    try:
        file_content = await file.read()

        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="El archivo esta vacio")

        result = await service.upload_single_dicom(file_content, file.filename or "unknown.dcm")

        return UploadDicomResponse(
            status=result["status"],
            message=result["message"],
            orthanc_id=result["orthanc_id"],
            parent_patient=result.get("parent_patient"),
            parent_study=result.get("parent_study"),
            parent_series=result.get("parent_series"),
            file_size_bytes=result["file_size_bytes"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error subiendo DICOM: {e}")
        raise HTTPException(status_code=502, detail=f"Error al subir a Orthanc: {str(e)}")


@router.post(
    "/dicom/multiple",
    response_model=UploadMultipleDicomResponse,
    summary="Subir multiples imagenes DICOM",
    description="Recibe multiples archivos DICOM y los almacena en Orthanc. Requiere JWT."
)
async def upload_multiple_dicoms(
    files: List[UploadFile] = File(..., description="Archivos DICOM (.dcm)"),
    payload: dict = Depends(require_jwt),
    service: UploadService = Depends(get_upload_service)
):
    logger.info(f"Upload múltiple por: {payload.get('sub', 'unknown')} ({len(files)} archivos)")

    if len(files) == 0:
        raise HTTPException(status_code=400, detail="No se enviaron archivos")

    if len(files) > 500:
        raise HTTPException(status_code=400, detail="Maximo 500 archivos por request")

    try:
        file_tuples = []
        for f in files:
            content = await f.read()
            if len(content) > 0:
                file_tuples.append((f.filename or "unknown.dcm", content))

        if len(file_tuples) == 0:
            raise HTTPException(status_code=400, detail="Todos los archivos estan vacios")

        result = await service.upload_multiple_dicoms(file_tuples)

        return UploadMultipleDicomResponse(
            status=result["status"],
            total_files=result["total_files"],
            uploaded=result["uploaded"],
            failed=result["failed"],
            results=result["results"],
            errors=result["errors"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error subiendo multiples DICOM: {e}")
        raise HTTPException(status_code=502, detail=f"Error al subir a Orthanc: {str(e)}")


# ============================
# ENDPOINTS CON CIFRADO AES-256
# ============================

@router.post(
    "/dicom/encrypted",
    response_model=UploadDicomResponse,
    summary="Subir imagen DICOM cifrada con AES-256",
    description=(
        "Recibe un archivo DICOM cifrado con AES-256-CBC, lo descifra y lo almacena en Orthanc. "
        "El archivo debe estar cifrado con la clave compartida entre JoeyCare y ATIM. "
        "Formato: IV (16 bytes) + ciphertext. Requiere JWT."
    )
)
async def upload_encrypted_dicom(
    file: UploadFile = File(..., description="Archivo DICOM cifrado con AES-256"),
    payload: dict = Depends(require_jwt),
    service: UploadService = Depends(get_upload_service)
):
    logger.info(f"Upload DICOM cifrado por: {payload.get('sub', 'unknown')}")

    try:
        encrypted_content = await file.read()

        if len(encrypted_content) == 0:
            raise HTTPException(status_code=400, detail="El archivo esta vacio")

        if len(encrypted_content) < 32:
            raise HTTPException(status_code=400, detail="Archivo cifrado demasiado corto")

        # Descifrar
        encryption_service = EncryptionService()
        try:
            decrypted_content = encryption_service.decrypt(encrypted_content)
        except Exception as e:
            logger.error(f"Error descifrando archivo: {e}")
            raise HTTPException(
                status_code=400,
                detail="No se pudo descifrar el archivo. Verifique la clave de cifrado."
            )

        logger.info(
            f"Archivo descifrado: {len(encrypted_content)} bytes -> {len(decrypted_content)} bytes"
        )

        # Subir a Orthanc
        original_filename = (file.filename or "unknown.dcm").replace(".enc", "")
        result = await service.upload_single_dicom(decrypted_content, original_filename)

        return UploadDicomResponse(
            status=result["status"],
            message=result["message"] + " (recibido cifrado con AES-256)",
            orthanc_id=result["orthanc_id"],
            parent_patient=result.get("parent_patient"),
            parent_study=result.get("parent_study"),
            parent_series=result.get("parent_series"),
            file_size_bytes=result["file_size_bytes"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando DICOM cifrado: {e}")
        raise HTTPException(status_code=502, detail=f"Error: {str(e)}")