import logging
from typing import List

from src.config.settings import Settings
from src.repositories.orthanc_repository import OrthancRepository

logger = logging.getLogger("atim")


class UploadService:
    """Servicio para subir archivos DICOM a Orthanc (flujo JoeyCare -> ATIM -> Orthanc)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.orthanc_repo = OrthancRepository(settings)

    async def upload_single_dicom(self, file_content: bytes, filename: str) -> dict:
        """Subir un archivo DICOM a Orthanc."""
        logger.info(f"Subiendo archivo DICOM a Orthanc: {filename} ({len(file_content)} bytes)")

        if len(file_content) < 132:
            raise ValueError("El archivo es demasiado pequeno para ser un DICOM valido")

        # Los archivos DICOM tienen "DICM" en el offset 128
        if file_content[128:132] != b"DICM":
            logger.warning(f"El archivo {filename} no tiene el header DICM estandar")

        # Subir a Orthanc
        result = await self.orthanc_repo.upload_dicom(file_content)

        orthanc_id = result.get("ID", "")
        status = result.get("Status", "")

        # Obtener tags de la instancia
        instance_info = {}
        if orthanc_id:
            try:
                instance_info = await self.orthanc_repo.get_instance_tags(orthanc_id)
            except Exception as e:
                logger.warning(f"No se pudieron obtener tags de la instancia: {e}")

        response = {
            "status": "success" if status in ("Success", "AlreadyStored") else status,
            "message": "Imagen DICOM almacenada en Orthanc" if status == "Success"
                       else "Imagen ya existia en Orthanc" if status == "AlreadyStored"
                       else f"Estado: {status}",
            "orthanc_id": orthanc_id,
            "parent_patient": result.get("ParentPatient", ""),
            "parent_study": result.get("ParentStudy", ""),
            "parent_series": result.get("ParentSeries", ""),
            "file_size_bytes": len(file_content),
            "filename": filename,
            "patient_name": instance_info.get("PatientName", ""),
            "study_description": instance_info.get("StudyDescription", ""),
            "modality": instance_info.get("Modality", ""),
        }

        logger.info(f"DICOM subido: orthanc_id={orthanc_id}, status={status}")
        return response

    async def upload_multiple_dicoms(self, files: List[tuple]) -> dict:
        """Subir multiples archivos DICOM a Orthanc."""
        logger.info(f"Subiendo {len(files)} archivos DICOM a Orthanc")

        results = []
        errors = []

        for filename, file_content in files:
            try:
                result = await self.upload_single_dicom(file_content, filename)
                results.append(result)
            except Exception as e:
                logger.error(f"Error subiendo {filename}: {e}")
                errors.append({"filename": filename, "error": str(e)})

        return {
            "status": "completed",
            "total_files": len(files),
            "uploaded": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors
        }