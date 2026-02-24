import logging
from typing import List, Optional

from src.config.settings import Settings
from src.repositories.orthanc_repository import OrthancRepository
from src.repositories.joycare_repository import JoyCareRepository

logger = logging.getLogger("atim")


class TransferService:
    """
    Servicio de transferencia: descarga imágenes desde Orthanc (PACS)
    y las sube a JoyCare.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.orthanc_repo = OrthancRepository(settings)
        self.joycare_repo = JoyCareRepository(settings)

    async def transfer_instance(
        self,
        instance_id: str,
        neonato_id: int,
        uploader_medico_id: int,
        sede_id: Optional[int] = None
    ) -> dict:
        """
        Transferir una instancia DICOM desde Orthanc a JoyCare.
        
        1. Descarga el archivo DICOM desde Orthanc
        2. Obtiene los tags para el nombre del archivo
        3. Sube el archivo a JoyCare
        """
        logger.info(
            f"Iniciando transferencia: instancia={instance_id} → "
            f"neonato={neonato_id}, médico={uploader_medico_id}"
        )

        # 1. Descargar archivo DICOM desde Orthanc
        file_bytes = await self.orthanc_repo.get_instance_file(instance_id)
        logger.info(f"Descargado de Orthanc: {len(file_bytes)} bytes")

        # 2. Obtener tags para construir un nombre de archivo descriptivo
        try:
            tags = await self.orthanc_repo.get_instance_tags(instance_id)
            patient_name = tags.get("PatientName", "unknown")
            modality = tags.get("Modality", "US")
            instance_number = tags.get("InstanceNumber", "0")
            filename = f"{patient_name}_{modality}_{instance_number}.dcm"
            # Limpiar caracteres no válidos
            filename = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
        except Exception:
            filename = f"{instance_id}.dcm"

        # 3. Subir a JoyCare
        result = await self.joycare_repo.upload_ecografia(
            neonato_id=neonato_id,
            file_bytes=file_bytes,
            filename=filename,
            uploader_medico_id=uploader_medico_id,
            sede_id=sede_id,
            mime_type="application/dicom"
        )

        logger.info(f"Transferencia completada: {filename} → JoyCare id={result.get('id')}")

        return {
            "status": "success",
            "message": "Imagen transferida exitosamente de PACS a JoyCare",
            "orthanc_instance_id": instance_id,
            "filename": filename,
            "file_size_bytes": len(file_bytes),
            "joycare_response": result
        }

    async def transfer_series(
        self,
        series_id: str,
        neonato_id: int,
        uploader_medico_id: int,
        sede_id: Optional[int] = None
    ) -> dict:
        """
        Transferir TODAS las instancias de una serie desde Orthanc a JoyCare.
        
        Útil cuando una serie tiene múltiples imágenes (ej: ecografía con varios frames).
        """
        logger.info(f"Iniciando transferencia de serie completa: {series_id}")

        # Obtener todas las instancias de la serie
        instances = await self.orthanc_repo.get_series_instances(series_id)
        logger.info(f"Serie {series_id}: {len(instances)} instancias encontradas")

        results = []
        errors = []

        for inst in instances:
            instance_id = inst.get("ID")
            try:
                result = await self.transfer_instance(
                    instance_id=instance_id,
                    neonato_id=neonato_id,
                    uploader_medico_id=uploader_medico_id,
                    sede_id=sede_id
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error transfiriendo instancia {instance_id}: {str(e)}")
                errors.append({
                    "instance_id": instance_id,
                    "error": str(e)
                })

        return {
            "status": "completed",
            "series_id": series_id,
            "total_instances": len(instances),
            "transferred": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors
        }

    async def get_joycare_neonatos(self) -> list:
        """Obtener la lista de neonatos desde JoyCare (para el frontend)."""
        return await self.joycare_repo.get_neonatos()

    async def check_joycare_connection(self) -> dict:
        """Verificar conexión con JoyCare."""
        return await self.joycare_repo.check_connection()