"""
Repositorio para comunicación con Orthanc via DICOMweb (estándar DICOM).

DICOMweb usa UIDs (identificadores estándar DICOM) en lugar de IDs internos.
Esto permite interoperabilidad con cualquier PACS que implemente el estándar.

Servicios implementados:
- QIDO-RS: Query/Retrieve de información (GET)
- WADO-RS: Web Access to DICOM Objects (GET binario)
"""

import httpx
import logging
import urllib.parse
from typing import Optional, List
from email.parser import BytesParser
from email.policy import default
from src.config.settings import Settings
from src.utils.dicom_tags import parse_dicom_json, extract_value

logger = logging.getLogger("atim")


class DICOMwebRepository:
    """Repositorio para comunicación con Orthanc via DICOMweb (QIDO-RS, WADO-RS)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.orthanc_dicomweb_url
        self.auth = httpx.BasicAuth(
            username=settings.orthanc_username,
            password=settings.orthanc_password
        )
        logger.info(f"✅ DICOMwebRepository inicializado: {self.base_url}")

    # ============================
    # UTILIDAD: URL Encoding
    # ============================

    @staticmethod
    def _encode_uid(uid: str) -> str:
        """
        Codificar UID DICOM para URL segura.
        
        Los UIDs pueden contener puntos que en ciertos casos
        causan problemas de parsing en el servidor.
        
        Args:
            uid: UID DICOM (ej: "1.3.12.2.1107.5.4.3.123456789012345.19950922.121803.6")
        
        Returns:
            UID encoded para usar en URL
        """
        # ✅ CORRECCIÓN: Usar quote para encoding seguro
        return urllib.parse.quote(uid, safe='')

    # ============================
    # QIDO-RS: Query Information Data Objects
    # ============================

    async def get_all_studies(self) -> List[dict]:
        """
        Obtener lista de todos los estudios via QIDO-RS.
        
        GET /dicom-web/studies
        
        Returns:
            Lista de estudios con StudyInstanceUID, PatientName, etc.
            Cada estudio es un diccionario con tags DICOM parseados.
        
        Raises:
            httpx.HTTPStatusError: Si Orthanc retorna error
        
        Ejemplo:
            [
              {
                "StudyInstanceUID": "1.3.12.2.1107...",
                "PatientName": "John DOE",
                "PatientID": "123456",
                "StudyDate": "20220315"
              },
              ...
            ]
        """
        logger.info("🔍 Obteniendo lista de estudios via QIDO-RS")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/studies",
                    auth=self.auth,  # ✅ Con BasicAuth
                    headers={"Accept": "application/dicom+json"}
                )
                response.raise_for_status()
                
                # DICOMweb retorna un array de objetos DICOM
                dicom_json_array = response.json()
                
                # Parsear cada estudio
                studies = []
                for dicom_obj in dicom_json_array:
                    parsed = parse_dicom_json(dicom_obj)
                    studies.append(parsed)
                
                logger.info(f"✅ Se encontraron {len(studies)} estudios")
                return studies
        except Exception as e:
            logger.error(f"❌ Error en get_all_studies: {str(e)}")
            raise

    async def get_study_by_uid(self, study_uid: str) -> dict:
        """Obtener detalles de un estudio específico via QIDO-RS."""
        logger.info(f"🔍 Obteniendo estudio: {study_uid}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/studies",
                    auth=self.auth,
                    params={"StudyInstanceUID": study_uid},
                    headers={"Accept": "application/dicom+json"},
                )
                response.raise_for_status()

                dicom_json_array = response.json()
                if not dicom_json_array:
                    return {}

                return parse_dicom_json(dicom_json_array[0])
        except Exception as e:
            logger.error(f"❌ Error en get_study_by_uid: {str(e)}")
            raise

    async def get_series_by_study_uid(self, study_uid: str) -> List[dict]:
        """
        Obtener todas las series de un estudio via QIDO-RS.
        
        GET /dicom-web/studies/{StudyInstanceUID}/series
        
        Args:
            study_uid: StudyInstanceUID
        
        Returns:
            Lista de series con SeriesInstanceUID, Modality, etc.
        
        Raises:
            httpx.HTTPStatusError: Si el estudio no existe
        """
        # ✅ CORRECCIÓN: Encodear el UID
        encoded_uid = self._encode_uid(study_uid)
        logger.info(f"🔍 Obteniendo series del estudio: {study_uid}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/studies/{encoded_uid}/series",
                    auth=self.auth,
                    headers={"Accept": "application/dicom+json"}
                )
                response.raise_for_status()
                
                dicom_json_array = response.json()
                
                series_list = []
                for dicom_obj in dicom_json_array:
                    parsed = parse_dicom_json(dicom_obj)
                    series_list.append(parsed)
                
                logger.info(f"✅ Se encontraron {len(series_list)} series en el estudio")
                return series_list
        except Exception as e:
            logger.error(f"❌ Error en get_series_by_study_uid: {str(e)}")
            raise

    async def get_series_by_uid(self, study_uid: str, series_uid: str) -> dict:
        """Obtener detalles de una serie específica via QIDO-RS."""
        encoded_study_uid = self._encode_uid(study_uid)
        logger.info(f"🔍 Obteniendo serie: {series_uid}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/studies/{encoded_study_uid}/series",
                    auth=self.auth,
                    params={"SeriesInstanceUID": series_uid},
                    headers={"Accept": "application/dicom+json"},
                )
                response.raise_for_status()

                dicom_json_array = response.json()
                if not dicom_json_array:
                    return {}

                return parse_dicom_json(dicom_json_array[0])
        except Exception as e:
            logger.error(f"❌ Error en get_series_by_uid: {str(e)}")
            raise

    async def get_instances_by_series_uid(
        self,
        study_uid: str,
        series_uid: str
    ) -> List[dict]:
        """
        Obtener todas las instancias de una serie via QIDO-RS.
        
        GET /dicom-web/studies/{StudyInstanceUID}/series/{SeriesInstanceUID}/instances
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
        
        Returns:
            Lista de instancias con SOPInstanceUID, InstanceNumber, etc.
        """
        # ✅ CORRECCIÓN: Encodear ambos UIDs
        encoded_study_uid = self._encode_uid(study_uid)
        encoded_series_uid = self._encode_uid(series_uid)
        logger.info(f"🔍 Obteniendo instancias de la serie: {series_uid}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/studies/{encoded_study_uid}/series/{encoded_series_uid}/instances",
                    auth=self.auth,
                    headers={"Accept": "application/dicom+json"}
                )
                response.raise_for_status()
                
                dicom_json_array = response.json()
                
                instances = []
                for dicom_obj in dicom_json_array:
                    parsed = parse_dicom_json(dicom_obj)
                    instances.append(parsed)
                
                logger.info(f"✅ Se encontraron {len(instances)} instancias")
                return instances
        except Exception as e:
            logger.error(f"❌ Error en get_instances_by_series_uid: {str(e)}")
            raise

    async def get_instance_by_uid(
        self,
        study_uid: str,
        series_uid: str,
        instance_uid: str
    ) -> dict:
        """Obtener detalles de una instancia específica via QIDO-RS."""
        encoded_study_uid = self._encode_uid(study_uid)
        encoded_series_uid = self._encode_uid(series_uid)
        logger.info(f"🔍 Obteniendo instancia: {instance_uid}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/studies/{encoded_study_uid}/series/{encoded_series_uid}/instances",
                    auth=self.auth,
                    params={"SOPInstanceUID": instance_uid},
                    headers={"Accept": "application/dicom+json"},
                )
                response.raise_for_status()

                dicom_json_array = response.json()
                if not dicom_json_array:
                    return {}

                return parse_dicom_json(dicom_json_array[0])
        except Exception as e:
            logger.error(f"❌ Error en get_instance_by_uid: {str(e)}")
            raise

    # ============================
    # WADO-RS: Web Access to DICOM Objects
    # ============================

    @staticmethod
    def _unwrap_multipart_dicom(content: bytes, content_type: str) -> bytes:
        """Extrae la parte application/dicom si la respuesta viene multipart/related."""
        if not content_type or "multipart/related" not in content_type.lower():
            return content

        raw = (
            f"Content-Type: {content_type}\r\n"
            "MIME-Version: 1.0\r\n\r\n"
        ).encode("utf-8") + content

        msg = BytesParser(policy=default).parsebytes(raw)

        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            ctype = part.get_content_type().lower()
            if ctype in ("application/dicom", "application/octet-stream"):
                payload = part.get_payload(decode=True)
                if payload:
                    return payload

        raise ValueError("No se encontró parte DICOM en respuesta multipart.")

    async def download_instance_file(
        self,
        study_uid: str,
        series_uid: str,
        instance_uid: str
    ) -> bytes:
        """
        Descargar el archivo DICOM completo de una instancia via WADO-RS.
        """
        encoded_study_uid = self._encode_uid(study_uid)
        encoded_series_uid = self._encode_uid(series_uid)
        encoded_instance_uid = self._encode_uid(instance_uid)

        wado_rs_url = (
            f"{self.base_url}/studies/{encoded_study_uid}"
            f"/series/{encoded_series_uid}"
            f"/instances/{encoded_instance_uid}"
        )

        logger.info(f"⬇️ Descargando archivo DICOM: {instance_uid}")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # 1) WADO-RS estándar (retrieve instance -> multipart/related)
                response = await client.get(
                    wado_rs_url,
                    auth=self.auth,
                    headers={
                        "Accept": "multipart/related; type=application/dicom; transfer-syntax=*"
                    },
                )

                # 2) Fallback WADO-URI (más compatible con Orthanc en algunos casos)
                if response.status_code in (400, 404, 406):
                    response = await client.get(
                        f"{self.base_url}/wado",
                        auth=self.auth,
                        params={
                            "requestType": "WADO",
                            "studyUID": study_uid,
                            "seriesUID": series_uid,
                            "objectUID": instance_uid,
                            "contentType": "application/dicom",
                        },
                    )

                # 3) Fallback no estándar /file
                if response.status_code == 404:
                    response = await client.get(
                        f"{wado_rs_url}/file",
                        auth=self.auth,
                        headers={"Accept": "application/dicom"},
                    )

                if response.status_code >= 400:
                    logger.error(
                        f"❌ Orthanc {response.status_code} en descarga instancia. "
                        f"URL={response.request.url}"
                    )

                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                dicom_bytes = self._unwrap_multipart_dicom(response.content, content_type)

                logger.info(f"✅ Archivo descargado: {len(dicom_bytes)} bytes")
                return dicom_bytes

        except Exception as e:
            logger.error(f"❌ Error en download_instance_file: {str(e)}")
            raise

    async def download_instance_frames(
        self,
        study_uid: str,
        series_uid: str,
        instance_uid: str,
        frame_numbers: Optional[List[int]] = None
    ) -> bytes:
        """
        Descargar frames específicos de una instancia multi-frame via WADO-RS.
        """
        if frame_numbers is None:
            return await self.download_instance_file(study_uid, series_uid, instance_uid)

        encoded_study_uid = self._encode_uid(study_uid)
        encoded_series_uid = self._encode_uid(series_uid)
        encoded_instance_uid = self._encode_uid(instance_uid)
        frames_str = ",".join(str(f) for f in frame_numbers)

        frames_url = (
            f"{self.base_url}/studies/{encoded_study_uid}"
            f"/series/{encoded_series_uid}"
            f"/instances/{encoded_instance_uid}"
            f"/frames/{frames_str}"
        )

        logger.info(f"⬇️ Descargando frames {frames_str} de: {instance_uid}")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # 1) WADO-RS recomendado para frames
                response = await client.get(
                    frames_url,
                    auth=self.auth,
                    headers={"Accept": "multipart/related; type=application/octet-stream"},
                )

                # 2) Fallbacks por compatibilidad
                if response.status_code in (400, 404, 406):
                    response = await client.get(
                        frames_url,
                        auth=self.auth,
                        headers={"Accept": "multipart/related; type=application/dicom"},
                    )

                if response.status_code in (400, 404, 406):
                    response = await client.get(
                        frames_url,
                        auth=self.auth,
                        headers={"Accept": "application/octet-stream"},
                    )

                if response.status_code >= 400:
                    logger.error(
                        f"❌ Orthanc {response.status_code} en descarga frames. "
                        f"URL={response.request.url}"
                    )

                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                # Si pidieron 1 frame y vino multipart, extraer payload binario
                if len(frame_numbers) == 1 and "multipart/related" in content_type.lower():
                    frame_bytes = self._unwrap_multipart_dicom(response.content, content_type)
                    logger.info(f"✅ Frame descargado: {len(frame_bytes)} bytes")
                    return frame_bytes

                # Para múltiples frames, retornar respuesta tal cual (multipart)
                logger.info(f"✅ Frames descargados: {len(response.content)} bytes | CT={content_type}")
                return response.content

        except Exception as e:
            logger.error(f"❌ Error en download_instance_frames: {str(e)}")
            raise
    # ============================
    # BÚSQUEDA AVANZADA (QIDO-RS con parámetros)
    # ============================

    async def search_studies(
        self,
        patient_id: Optional[str] = None,
        patient_name: Optional[str] = None,
        study_date_from: Optional[str] = None,
        study_date_to: Optional[str] = None,
        modality: Optional[str] = None
    ) -> List[dict]:
        """
        Buscar estudios con filtros via QIDO-RS.
        
        GET /dicom-web/studies?PatientID=...&StudyDate=...&Modality=...
        
        Args:
            patient_id: ID del paciente (ej: "123456")
            patient_name: Nombre del paciente (ej: "John*DOE" - wildcards)
            study_date_from: Fecha desde (formato YYYYMMDD)
            study_date_to: Fecha hasta (formato YYYYMMDD)
            modality: Modalidad (ej: "US", "XA", "CT")
        
        Returns:
            Lista de estudios que coinciden con los filtros
        
        Ejemplo:
            await repo.search_studies(
                patient_id="123456",
                modality="US",
                study_date_from="20220101"
            )
        """
        params = {}
        
        if patient_id:
            params["PatientID"] = patient_id
        if patient_name:
            params["PatientName"] = patient_name
        if modality:
            params["Modality"] = modality
        if study_date_from or study_date_to:
            # DICOM usa rango: YYYYMMDD-YYYYMMDD
            date_range = ""
            if study_date_from:
                date_range += study_date_from
            date_range += "-"
            if study_date_to:
                date_range += study_date_to
            params["StudyDate"] = date_range
        
        logger.info(f"🔍 Buscando estudios con filtros: {params}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/studies",
                    auth=self.auth,
                    params=params,
                    headers={"Accept": "application/dicom+json"}
                )
                response.raise_for_status()
                
                dicom_json_array = response.json()
                
                studies = []
                for dicom_obj in dicom_json_array:
                    parsed = parse_dicom_json(dicom_obj)
                    studies.append(parsed)
                
                logger.info(f"✅ Se encontraron {len(studies)} estudios")
                return studies
        except Exception as e:
            logger.error(f"❌ Error en search_studies: {str(e)}")
            raise

    # ============================
    # UTILIDADES
    # ============================

    async def get_modality_by_series_uid(
        self,
        study_uid: str,
        series_uid: str
    ) -> str:
        """
        Obtener la modalidad (Modality) de una serie.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
        
        Returns:
            Código de modalidad (ej: "US", "XA", "CT")
        """
        series_data = await self.get_series_by_uid(study_uid, series_uid)
        return series_data.get("Modality", "UNKNOWN")

    async def count_instances_in_series(
        self,
        study_uid: str,
        series_uid: str
    ) -> int:
        """
        Contar el número de instancias en una serie.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
        
        Returns:
            Número de instancias
        """
        instances = await self.get_instances_by_series_uid(study_uid, series_uid)
        return len(instances)