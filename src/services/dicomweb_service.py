"""
Servicio de DICOMweb para consultar estudios, series e instancias.

Este servicio usa el estándar DICOMweb (QIDO-RS, WADO-RS) para comunicarse
con cualquier PACS compatible, no solo Orthanc. Usa UIDs estándar DICOM
en lugar de IDs propietarios.

"""

import logging
from typing import List, Optional

from src.config.settings import Settings
from src.repositories.dicomweb_repository import DICOMwebRepository
from src.models.schemas import (
    PatientSummary,
    StudySummary,
    StudyDetail,
    InstanceSummary,
)

logger = logging.getLogger("atim")


class DICOMwebService:
    """Servicio para consultar estudios, series e instancias via DICOMweb."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.dicomweb_repo = DICOMwebRepository(settings)

    # ============================
    # ESTUDIOS
    # ============================

    async def get_all_studies(self) -> List[StudySummary]:
        """
        Obtener todos los estudios via DICOMweb (QIDO-RS).
        
        Returns:
            Lista de StudySummary con información básica de cada estudio
        
        Ejemplo:
            [
              StudySummary(
                orthanc_id="1.3.12.2.1107...",  # En DICOMweb es el StudyInstanceUID
                study_instance_uid="1.3.12.2.1107...",
                study_date="20220315",
                study_description="Ecografía 20 semanas",
                patient_name="Maria García",
                patient_id="12345678",
                series_count=2
              ),
              ...
            ]
        """
        logger.info("🔍 Obteniendo todos los estudios via DICOMweb")
        
        try:
            studies_data = await self.dicomweb_repo.get_all_studies()
            
            studies = []
            for study_data in studies_data:
                study = StudySummary(
                    # En DICOMweb, el ID es el StudyInstanceUID
                    orthanc_id=study_data.get("StudyInstanceUID", "unknown"),
                    study_instance_uid=study_data.get("StudyInstanceUID"),
                    study_date=study_data.get("StudyDate"),
                    study_description=study_data.get("StudyDescription", ""),
                    patient_name=study_data.get("PatientName", "Unknown"),
                    patient_id=study_data.get("PatientID", "unknown"),
                    series_count=0
                )
                studies.append(study)
            
            logger.info(f"✅ Se encontraron {len(studies)} estudios via DICOMweb")
            return studies
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo estudios DICOMweb: {str(e)}")
            raise

    async def get_study_detail(self, study_uid: str) -> StudyDetail:
        """
        Obtener el detalle completo de un estudio con todas sus series via DICOMweb.
        
        Args:
            study_uid: StudyInstanceUID (ej: "1.3.12.2.1107...")
        
        Returns:
            StudyDetail con información del estudio y lista de series
        
        Raises:
            httpx.HTTPStatusError: Si el estudio no existe
        
        Ejemplo:
            detail = await service.get_study_detail("1.3.12.2.1107...")
            # Obtiene:
            # - Información del estudio
            # - Lista de todas las series
            # - Información del paciente
        """
        logger.info(f"🔍 Obteniendo detalle de estudio: {study_uid}")
        
        try:
            # 1. Obtener información general del estudio
            study_data = await self.dicomweb_repo.get_study_by_uid(study_uid)
            
            # 2. Obtener todas las series del estudio
            series_list_data = await self.dicomweb_repo.get_series_by_study_uid(study_uid)
            
            # 3. Procesar información de cada serie
            series_list = []
            for series_data in series_list_data:
                series_uid = series_data.get("SeriesInstanceUID")
                
                # Obtener número de instancias
                instances_count = 0
                try:
                    instances_count = await self.dicomweb_repo.count_instances_in_series(
                        study_uid, series_uid
                    )
                except Exception as e:
                    logger.warning(f"No se pudo contar instancias de {series_uid}: {str(e)}")
                
                series_list.append({
                    "orthanc_id": series_uid,
                    "series_instance_uid": series_uid,
                    "modality": series_data.get("Modality", "UNKNOWN"),
                    "series_description": series_data.get("SeriesDescription", ""),
                    "series_number": series_data.get("SeriesNumber"),
                    "instances_count": instances_count
                })
            
            # 4. Construir respuesta
            study_detail = StudyDetail(
                orthanc_id=study_uid,
                study_instance_uid=study_uid,
                study_date=study_data.get("StudyDate"),
                study_description=study_data.get("StudyDescription", ""),
                patient_name=study_data.get("PatientName", "Unknown"),
                patient_id=study_data.get("PatientID", "unknown"),
                series_count=len(series_list),
                series=series_list
            )
            
            logger.info(f"✅ Estudio {study_uid}: {len(series_list)} series encontradas")
            return study_detail
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo detalle de estudio {study_uid}: {str(e)}")
            raise

    # ============================
    # SERIES
    # ============================

    async def get_series_instances(
        self,
        study_uid: str,
        series_uid: str
    ) -> List[InstanceSummary]:
        """
        Obtener todas las instancias de una serie via DICOMweb.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
        
        Returns:
            Lista de InstanceSummary con información de cada instancia
        
        Ejemplo:
            instances = await service.get_series_instances(
                study_uid="1.3.12.2.1107...",
                series_uid="1.3.46.670589.11..."
            )
            # Retorna:
            # [
            #   InstanceSummary(
            #     orthanc_id="1.2.840.10008...",
            #     sop_instance_uid="1.2.840.10008...",
            #     instance_number="1"
            #   ),
            #   ...
            # ]
        """
        logger.info(f"🔍 Obteniendo instancias de serie: {series_uid}")
        
        try:
            instances_data = await self.dicomweb_repo.get_instances_by_series_uid(
                study_uid, series_uid
            )
            
            instances = []
            for inst_data in instances_data:
                instance = InstanceSummary(
                    # En DICOMweb es el SOPInstanceUID
                    orthanc_id=inst_data.get("SOPInstanceUID", "unknown"),
                    sop_instance_uid=inst_data.get("SOPInstanceUID"),
                    instance_number=inst_data.get("InstanceNumber")
                )
                instances.append(instance)
            
            logger.info(f"✅ Serie {series_uid}: {len(instances)} instancias encontradas")
            return instances
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo instancias de {series_uid}: {str(e)}")
            raise

    # ============================
    # INSTANCIAS (Descarga)
    # ============================

    async def get_instance_file(
        self,
        study_uid: str,
        series_uid: str,
        instance_uid: str
    ) -> bytes:
        """
        Descargar el archivo DICOM completo de una instancia.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_uid: SOPInstanceUID
        
        Returns:
            Bytes del archivo DICOM (.dcm)
        
        Raises:
            httpx.HTTPStatusError: Si la instancia no existe
        
        Ejemplo:
            file_bytes = await service.get_instance_file(
                study_uid="1.3.12.2.1107...",
                series_uid="1.3.46.670589.11...",
                instance_uid="1.2.840.10008..."
            )
            # file_bytes contiene el DICOM descargado
        """
        logger.info(f"⬇️ Descargando instancia: {instance_uid}")
        
        try:
            file_bytes = await self.dicomweb_repo.download_instance_file(
                study_uid, series_uid, instance_uid
            )
            logger.info(f"✅ Instancia descargada: {len(file_bytes)} bytes")
            return file_bytes
            
        except Exception as e:
            logger.error(f"❌ Error descargando instancia {instance_uid}: {str(e)}")
            raise

    async def get_instance_frames(
        self,
        study_uid: str,
        series_uid: str,
        instance_uid: str,
        frame_numbers: Optional[List[int]] = None
    ) -> bytes:
        """
        Descargar frames específicos de una instancia multi-frame.
        
        Útil para imágenes de ultrasound o fluoroscopia que tienen múltiples frames.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_uid: SOPInstanceUID
            frame_numbers: Lista de números de frame a descargar (ej: [1, 2, 3])
                          Si None, descarga todos los frames
        
        Returns:
            Bytes del archivo DICOM con los frames solicitados
        
        Ejemplo:
            # Descargar solo los frames 1 y 3 de una ecografía
            file_bytes = await service.get_instance_frames(
                study_uid="1.3.12.2.1107...",
                series_uid="1.3.46.670589.11...",
                instance_uid="1.2.840.10008...",
                frame_numbers=[1, 3]
            )
        """
        logger.info(f"⬇️ Descargando frames {frame_numbers} de instancia: {instance_uid}")
        
        try:
            file_bytes = await self.dicomweb_repo.download_instance_frames(
                study_uid, series_uid, instance_uid, frame_numbers
            )
            logger.info(f"✅ Frames descargados: {len(file_bytes)} bytes")
            return file_bytes
            
        except Exception as e:
            logger.error(f"❌ Error descargando frames de {instance_uid}: {str(e)}")
            raise

    async def get_instance_tags(
        self,
        study_uid: str,
        series_uid: str,
        instance_uid: str
    ) -> dict:
        """
        Obtener todos los tags DICOM de una instancia.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_uid: SOPInstanceUID
        
        Returns:
            Diccionario con los tags DICOM parseados (nombres legibles)
        
        Ejemplo:
            tags = await service.get_instance_tags(
                study_uid="1.3.12.2.1107...",
                series_uid="1.3.46.670589.11...",
                instance_uid="1.2.840.10008..."
            )
            # Retorna:
            # {
            #   "SOPInstanceUID": "1.2.840.10008...",
            #   "SOPClassUID": "1.2.840.10008.5.1.4.1.1.7",
            #   "PatientName": "Maria García",
            #   "StudyDate": "20220315",
            #   ...
            # }
        """
        logger.info(f"🔍 Obteniendo tags DICOM de instancia: {instance_uid}")
        
        try:
            tags = await self.dicomweb_repo.get_instance_by_uid(
                study_uid, series_uid, instance_uid
            )
            logger.info(f"✅ {len(tags)} tags recuperados de {instance_uid}")
            return tags
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo tags de {instance_uid}: {str(e)}")
            raise

    # ============================
    # BÚSQUEDA AVANZADA
    # ============================

    async def search_ecograph_studies(
        self,
        patient_id: Optional[str] = None,
        patient_name: Optional[str] = None,
        study_date_from: Optional[str] = None,
        study_date_to: Optional[str] = None
    ) -> List[StudySummary]:
        """
        Buscar estudios de ecografía (modalidad US) con filtros.
        
        Esta es una búsqueda especializada para ecografías obstétricas.
        Filtra automáticamente por modalidad "US" (Ultrasound).
        
        Args:
            patient_id: ID del paciente (ej: "12345678")
            patient_name: Nombre del paciente con wildcards (ej: "Maria*" o "*García")
            study_date_from: Fecha desde (formato YYYYMMDD, ej: "20220101")
            study_date_to: Fecha hasta (formato YYYYMMDD, ej: "20221231")
        
        Returns:
            Lista de StudySummary que coinciden con los filtros
        
        Ejemplo:
            # Buscar ecografías de María entre enero y marzo de 2022
            studies = await service.search_ecograph_studies(
                patient_name="Maria*",
                study_date_from="20220101",
                study_date_to="20220331"
            )
        """
        logger.info(f"🔍 Buscando ecografías con filtros: paciente={patient_name}, rango={study_date_from}-{study_date_to}")
        
        try:
            # Buscar estudios con modalidad "US" (Ultrasound)
            studies_data = await self.dicomweb_repo.search_studies(
                patient_id=patient_id,
                patient_name=patient_name,
                study_date_from=study_date_from,
                study_date_to=study_date_to,
                modality="US"
            )
            
            studies = []
            for study_data in studies_data:
                study = StudySummary(
                    orthanc_id=study_data.get("StudyInstanceUID", "unknown"),
                    study_instance_uid=study_data.get("StudyInstanceUID"),
                    study_date=study_data.get("StudyDate"),
                    study_description=study_data.get("StudyDescription", ""),
                    patient_name=study_data.get("PatientName", "Unknown"),
                    patient_id=study_data.get("PatientID", "unknown"),
                    series_count=0
                )
                studies.append(study)
            
            logger.info(f"✅ Se encontraron {len(studies)} ecografías")
            return studies
            
        except Exception as e:
            logger.error(f"❌ Error buscando ecografías: {str(e)}")
            raise

    # ============================
    # UTILIDADES
    # ============================

    async def get_series_modality(
        self,
        study_uid: str,
        series_uid: str
    ) -> str:
        """
        Obtener la modalidad de una serie.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
        
        Returns:
            Código de modalidad (ej: "US", "CT", "XA")
        
        Ejemplo:
            modality = await service.get_series_modality(
                study_uid="1.3.12.2.1107...",
                series_uid="1.3.46.670589.11..."
            )
            # Retorna: "US"
        """
        logger.info(f"🔍 Obteniendo modalidad de serie: {series_uid}")
        
        try:
            modality = await self.dicomweb_repo.get_modality_by_series_uid(
                study_uid, series_uid
            )
            logger.info(f"✅ Modalidad de {series_uid}: {modality}")
            return modality
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo modalidad de {series_uid}: {str(e)}")
            raise


    async def is_ultrasound_series(
        self,
        study_uid: str,
        series_uid: str
    ) -> bool:
        """
        Verificar si una serie es de ultrasound (ecografía).
        
        En DICOM, "US" (Ultrasound) es el código estándar para TODAS las ecografías,
        incluyendo:
        - Ecografía transfontanelar (ETF) — Para visualización cerebral en neonatos
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
        
        Returns:
            True si es ecografía (modalidad "US"), False en caso contrario
        
        """
        try:
            modality = await self.get_series_modality(study_uid, series_uid)
            return modality == "US"
        except Exception:
            return False

    async def is_transfontanelar_echography(
        self,
        study_uid: str,
        series_uid: str,
        series_description: Optional[str] = None
    ) -> bool:
        """
        Verificar si una serie es ecografía transfontanelar (ETF).
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            series_description: Descripción de la serie (opcional)
                               Si no se proporciona, se obtiene del PACS
        
        Returns:
            True si probablemente es ETF, False en caso contrario
        
        """
        # Criterio 1: Debe ser ultrasound
        is_us = await self.is_ultrasound_series(study_uid, series_uid)
        if not is_us:
            return False
        
        # Criterio 2: Obtener descripción si no la tenemos
        if series_description is None:
            try:
                series_data = await self.dicomweb_repo.get_series_by_uid(study_uid, series_uid)
                series_description = series_data.get("SeriesDescription", "").lower()
            except Exception:
                return False
        else:
            series_description = series_description.lower()
        
        # Criterio 3: Búsqueda de keywords típicos de ETF
        etf_keywords = [
            "transfontanelar",
            "fontanel",
            "fontanelle",
            "anterior fontanelle",
            "posterior fontanelle",
            "brain",
            "cerebral",
            "cranial",
            "cerebro",
            "cerebral",
            "ecografía transfontanelar",
            "echography transfontanelar",
        ]
        
        is_etf = any(keyword in series_description for keyword in etf_keywords)
        
        logger.info(f"🧠 Serie {series_uid}: ¿Es ETF? {is_etf}")
        return is_etf

    async def filter_transfontanelar_studies(
        self,
        studies: List[StudySummary]
    ) -> List[StudySummary]:
        """
        Filtrar solo estudios que puedan ser ecografía transfontanelar (ETF).
         
        Args:
            studies: Lista de estudios a filtrar
        
        Returns:
            Subconjunto de estudios solo con estudios US (ultrasonido)
        
        """
        etf_compatible = []
        
        for study in studies:
            try:
                # Obtener detalles del estudio para verificar series
                study_detail = await self.get_study_detail(study.study_instance_uid)
                
                # Verificar si alguna serie es US
                has_ultrasound = False
                for series in study_detail.series:
                    if series.get("modality") == "US":
                        has_ultrasound = True
                        break
                
                if has_ultrasound:
                    etf_compatible.append(study)
                    
            except Exception as e:
                logger.warning(f"No se pudo verificar estudio {study.study_instance_uid}: {str(e)}")
        
        logger.info(f"🧠 {len(etf_compatible)} de {len(studies)} estudios son US (potencialmente ETF)")
        return etf_compatible