import logging
from src.repositories.orthanc_repository import OrthancRepository
from src.repositories.joeycare_repository import JoeyCareRepository
from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TransferService:
    """
    Servicio que orquesta la descarga de imágenes desde Orthanc (PACS)
    y las sube a JoeyCare.
    """

    def __init__(self):
        self.orthanc_repo = OrthancRepository(settings)
        self.joeycare_repo = JoeyCareRepository()

    async def transfer_instance(
        self,
        instance_id: str,
        neonato_id: int,
        uploader_medico_id: int,
        sede_id: int = None
    ) -> dict:
        """
        Transferir una instancia DICOM de Orthanc a JoeyCare.

        Flujo:
        1. Descarga el archivo DICOM desde Orthanc
        2. Extrae metadata y UIDs relevantes
        3. Sube el archivo a JoeyCare con uploader_medico_id y sede_id
        """
        logger.info(
            f"Iniciando transferencia: instance={instance_id}, neonato={neonato_id}, "
            f"uploader_medico={uploader_medico_id}, sede={sede_id}"
        )

        # 1. Descargar desde Orthanc
        dicom_data = await self.orthanc_repo.get_instance_file(instance_id)
        logger.info(f"Descargado desde Orthanc: {len(dicom_data)} bytes")

        # 2. Obtener metadata y tags
        instance_info = await self.orthanc_repo.get_instance_tags(instance_id)
        filename = f"eco_{neonato_id}_{instance_id}.dcm"

        transfer_metadata = {
            "orthanc_instance_id": instance_id,
            "patient_name": instance_info.get("PatientName", ""),
            "study_description": instance_info.get("StudyDescription", ""),
        }

        # 3. Subir a JoeyCare con TODOS los parámetros requeridos
        result = await self.joeycare_repo.upload_ecografia(
            neonato_id=neonato_id,
            file_content=dicom_data,
            filename=filename,
            uploader_medico_id=uploader_medico_id,
            sede_id=sede_id,
            metadata=transfer_metadata
        )

        logger.info(f"Transferencia completada: instance={instance_id}")

        return {
            "status": "success",
            "message": "Imagen transferida exitosamente",
            "orthanc_instance_id": instance_id,
            "neonato_id": neonato_id,
            "file_size_bytes": len(dicom_data),
            "filename": filename,
            "joycare_response": result
        }

    async def transfer_study(
        self,
        study_id: str,
        neonato_id: int,
        uploader_medico_id: int,
        sede_id: int = None
    ) -> dict:
        """
        Transferir TODAS las instancias de un estudio de Orthanc a JoeyCare.
        """
        logger.info(
            f"Transferencia de estudio: study={study_id}, neonato={neonato_id}, "
            f"uploader_medico={uploader_medico_id}, sede={sede_id}"
        )

        instances = await self.orthanc_repo.get_study_instances(study_id)
        results = []
        errors = []

        for instance in instances:
            try:
                result = await self.transfer_instance(
                    instance_id=instance["ID"],
                    neonato_id=neonato_id,
                    uploader_medico_id=uploader_medico_id,
                    sede_id=sede_id
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error transfiriendo instancia {instance['ID']}: {e}")
                errors.append({
                    "instance_id": instance["ID"],
                    "error": str(e)
                })

        return {
            "status": "completed",
            "study_id": study_id,
            "neonato_id": neonato_id,
            "total_instances": len(instances),
            "transferred": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors
        }

    async def get_joeycare_neonatos(self) -> list:
        """Obtener la lista de neonatos desde JoeyCare."""
        return await self.joeycare_repo.get_neonatos()

    async def check_joeycare_connection(self) -> dict:
        """Verificar conexión con JoeyCare."""
        return await self.joeycare_repo.check_connection()