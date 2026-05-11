import logging
from typing import List
import zipfile
import io
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

    async def download_study_as_zip(self, study_id: str) -> bytes:
        """
        Descargar un estudio completo (todas sus series) como ZIP.
        Usa estructura plana para evitar paths muy largos en Windows.
        
        Estructura del ZIP:
        - metadata.json (info del estudio)
        - 001.dcm, 002.dcm, 003.dcm... (archivos DICOM)
        """
        import json
        
        logger.info(f"📦 Preparando descarga de estudio como ZIP: {study_id}")
        
        try:
            # Obtener detalles del estudio
            study_details = await self.orthanc_repo.get_study_details(study_id)
            study_tags = study_details.get("MainDicomTags", {})
            patient_tags = study_details.get("PatientMainDicomTags", {})
            
            # Metadatos del estudio
            study_metadata = {
                "study_id": study_id,
                "study_uid": study_tags.get("StudyInstanceUID", ""),
                "patient_name": patient_tags.get("PatientName", ""),
                "patient_id": patient_tags.get("PatientID", ""),
                "study_date": study_tags.get("StudyDate", ""),
                "study_description": study_tags.get("StudyDescription", ""),
                "series_count": len(study_details.get("Series", [])),
                "files": []
            }
            
            # Crear ZIP en memoria
            zip_buffer = io.BytesIO()
            instance_counter = 1
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Iterar sobre todas las series del estudio
                for series_id in study_details.get("Series", []):
                    series_details = await self.orthanc_repo.get_series_details(series_id)
                    series_tags = series_details.get("MainDicomTags", {})
                    modality = series_tags.get("Modality", "UNKNOWN")
                    series_desc = series_tags.get("SeriesDescription", "unknown")
                    series_uid = series_tags.get("SeriesInstanceUID", "")
                    
                    # Iterar sobre todas las instancias de la serie
                    for instance_id in series_details.get("Instances", []):
                        try:
                            # Descargar el archivo DICOM
                            dicom_bytes = await self.orthanc_repo.get_instance_file(instance_id)
                            
                            # Nombre corto: 001.dcm, 002.dcm, etc.
                            filename = f"{instance_counter:03d}.dcm"
                            
                            # Añadir al ZIP
                            zf.writestr(filename, dicom_bytes)
                            
                            # Registrar en metadatos
                            study_metadata["files"].append({
                                "file": filename,
                                "instance_id": instance_id,
                                "series_id": series_id,
                                "modality": modality,
                                "series_description": series_desc,
                                "series_uid": series_uid,
                                "size_bytes": len(dicom_bytes)
                            })
                            
                            logger.info(f"✅ Añadido a ZIP: {filename} ({len(dicom_bytes)} bytes)")
                            instance_counter += 1
                            
                        except Exception as e:
                            logger.error(f"❌ Error descargando instancia {instance_id}: {str(e)}")
                            continue
                
                # Agregar metadata.json
                metadata_json = json.dumps(study_metadata, indent=2)
                zf.writestr("metadata.json", metadata_json)
                logger.info(f"✅ Metadatos guardados en metadata.json")
            
            zip_data = zip_buffer.getvalue()
            logger.info(f"📦 ZIP creado exitosamente: {len(zip_data)} bytes, {instance_counter-1} archivos")
            return zip_data
            
        except Exception as e:
            logger.error(f"❌ Error en download_study_as_zip: {str(e)}")
            raise

    async def download_series_as_zip(self, series_id: str) -> bytes:
        """
        Descargar una serie completa (todas sus instancias) como ZIP.
        Usa estructura plana para evitar paths muy largos.
        """
        import json
        
        logger.info(f"📦 Preparando descarga de serie como ZIP: {series_id}")
        
        try:
            # Obtener detalles de la serie
            series_details = await self.orthanc_repo.get_series_details(series_id)
            series_tags = series_details.get("MainDicomTags", {})
            
            modality = series_tags.get("Modality", "UNKNOWN")
            series_desc = series_tags.get("SeriesDescription", "unknown")
            series_uid = series_tags.get("SeriesInstanceUID", "")
            
            # Metadatos de la serie
            series_metadata = {
                "series_id": series_id,
                "series_uid": series_uid,
                "modality": modality,
                "series_description": series_desc,
                "instances_count": len(series_details.get("Instances", [])),
                "files": []
            }
            
            # Crear ZIP en memoria
            zip_buffer = io.BytesIO()
            instance_counter = 1
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Iterar sobre todas las instancias de la serie
                for instance_id in series_details.get("Instances", []):
                    try:
                        # Descargar el archivo DICOM
                        dicom_bytes = await self.orthanc_repo.get_instance_file(instance_id)
                        
                        # Nombre corto: 001.dcm, 002.dcm, etc.
                        filename = f"{instance_counter:03d}.dcm"
                        
                        # Añadir al ZIP
                        zf.writestr(filename, dicom_bytes)
                        
                        # Registrar en metadatos
                        series_metadata["files"].append({
                            "file": filename,
                            "instance_id": instance_id,
                            "size_bytes": len(dicom_bytes)
                        })
                        
                        logger.info(f"✅ Añadido a ZIP: {filename} ({len(dicom_bytes)} bytes)")
                        instance_counter += 1
                        
                    except Exception as e:
                        logger.error(f"❌ Error descargando instancia {instance_id}: {str(e)}")
                        continue
                
                # Agregar metadata.json
                metadata_json = json.dumps(series_metadata, indent=2)
                zf.writestr("metadata.json", metadata_json)
                logger.info(f"✅ Metadatos guardados en metadata.json")
            
            zip_data = zip_buffer.getvalue()
            logger.info(f"📦 ZIP creado exitosamente: {len(zip_data)} bytes, {instance_counter-1} archivos")
            return zip_data
            
        except Exception as e:
            logger.error(f"❌ Error en download_series_as_zip: {str(e)}")
            raise

    async def get_instance_preview(self, instance_id: str) -> bytes:
        """Obtener la vista previa PNG de una instancia."""
        return await self.orthanc_repo.get_instance_preview(instance_id)

    async def get_instance_tags(self, instance_id: str) -> dict:
        """Obtener los tags DICOM de una instancia."""
        return await self.orthanc_repo.get_instance_tags(instance_id)