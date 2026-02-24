import logging
from typing import List

from src.config.settings import Settings
from src.repositories.orthanc_repository import OrthancRepository
from src.models.schemas import (
    PatientSummary,
    StudySummary,
    StudyDetail,
    InstanceSummary,
)

logger = logging.getLogger("atim")


class StudiesService:
    """Servicio para consultar estudios, series e instancias desde Orthanc."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.orthanc_repo = OrthancRepository(settings)

    # ============================
    # PACIENTES
    # ============================

    async def get_all_patients(self) -> List[PatientSummary]:
        """Obtener todos los pacientes con su información básica."""
        patient_ids = await self.orthanc_repo.get_all_patients()
        patients = []

        for pid in patient_ids:
            details = await self.orthanc_repo.get_patient_details(pid)
            main_tags = details.get("MainDicomTags", {})

            patients.append(PatientSummary(
                orthanc_id=pid,
                patient_id=main_tags.get("PatientID"),
                patient_name=main_tags.get("PatientName"),
                birth_date=main_tags.get("PatientBirthDate"),
                sex=main_tags.get("PatientSex"),
                studies_count=len(details.get("Studies", []))
            ))

        logger.info(f"Se encontraron {len(patients)} pacientes en Orthanc")
        return patients

    # ============================
    # ESTUDIOS
    # ============================

    async def get_all_studies(self) -> List[StudySummary]:
        """Obtener todos los estudios con su información básica."""
        study_ids = await self.orthanc_repo.get_all_studies()
        studies = []

        for sid in study_ids:
            details = await self.orthanc_repo.get_study_details(sid)
            main_tags = details.get("MainDicomTags", {})
            patient_tags = details.get("PatientMainDicomTags", {})

            studies.append(StudySummary(
                orthanc_id=sid,
                study_instance_uid=main_tags.get("StudyInstanceUID"),
                study_date=main_tags.get("StudyDate"),
                study_description=main_tags.get("StudyDescription"),
                patient_name=patient_tags.get("PatientName"),
                patient_id=patient_tags.get("PatientID"),
                series_count=len(details.get("Series", []))
            ))

        logger.info(f"Se encontraron {len(studies)} estudios en Orthanc")
        return studies

    async def get_study_detail(self, study_id: str) -> StudyDetail:
        """Obtener el detalle de un estudio con todas sus series."""
        details = await self.orthanc_repo.get_study_details(study_id)
        main_tags = details.get("MainDicomTags", {})
        patient_tags = details.get("PatientMainDicomTags", {})

        # Obtener info de cada serie
        series_list = []
        for series_id in details.get("Series", []):
            series_details = await self.orthanc_repo.get_series_details(series_id)
            series_tags = series_details.get("MainDicomTags", {})

            series_list.append({
                "orthanc_id": series_id,
                "modality": series_tags.get("Modality"),
                "series_description": series_tags.get("SeriesDescription"),
                "instances_count": len(series_details.get("Instances", []))
            })

        return StudyDetail(
            orthanc_id=study_id,
            study_instance_uid=main_tags.get("StudyInstanceUID"),
            study_date=main_tags.get("StudyDate"),
            study_description=main_tags.get("StudyDescription"),
            patient_name=patient_tags.get("PatientName"),
            patient_id=patient_tags.get("PatientID"),
            series_count=len(series_list),
            series=series_list
        )

    # ============================
    # SERIES
    # ============================

    async def get_series_instances(self, series_id: str) -> List[InstanceSummary]:
        """Obtener todas las instancias de una serie."""
        instances = await self.orthanc_repo.get_series_instances(series_id)
        result = []

        for inst in instances:
            main_tags = inst.get("MainDicomTags", {})
            result.append(InstanceSummary(
                orthanc_id=inst.get("ID"),
                sop_instance_uid=main_tags.get("SOPInstanceUID"),
                instance_number=main_tags.get("InstanceNumber")
            ))

        logger.info(f"Serie {series_id}: {len(result)} instancias encontradas")
        return result

    # ============================
    # INSTANCIAS (Descarga)
    # ============================

    async def get_instance_file(self, instance_id: str) -> bytes:
        """Descargar el archivo DICOM de una instancia."""
        logger.info(f"Descargando instancia DICOM: {instance_id}")
        file_bytes = await self.orthanc_repo.get_instance_file(instance_id)
        logger.info(f"Instancia {instance_id}: {len(file_bytes)} bytes descargados")
        return file_bytes

    async def get_instance_preview(self, instance_id: str) -> bytes:
        """Obtener la vista previa PNG de una instancia."""
        return await self.orthanc_repo.get_instance_preview(instance_id)

    async def get_instance_tags(self, instance_id: str) -> dict:
        """Obtener los tags DICOM de una instancia."""
        return await self.orthanc_repo.get_instance_tags(instance_id)