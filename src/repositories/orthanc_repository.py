import httpx
from typing import Optional

from src.config.settings import Settings


class OrthancRepository:
    """Repositorio para comunicación directa con Orthanc via API REST y DICOMweb."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.orthanc_url
        self.dicomweb_url = settings.orthanc_dicomweb_url
        self.auth = (settings.orthanc_username, settings.orthanc_password)

    # ============================
    # CONEXIÓN
    # ============================

    async def check_connection(self) -> dict:
        """Verificar si Orthanc está accesible."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/system",
                    auth=self.auth
                )
                response.raise_for_status()
                return {
                    "reachable": True,
                    "system_info": response.json(),
                    "message": "Conexión exitosa con Orthanc"
                }
        except httpx.ConnectError:
            return {
                "reachable": False,
                "system_info": None,
                "message": f"No se puede conectar a Orthanc en {self.base_url}"
            }
        except httpx.HTTPStatusError as e:
            return {
                "reachable": False,
                "system_info": None,
                "message": f"Orthanc respondió con error: {e.response.status_code}"
            }
        except Exception as e:
            return {
                "reachable": False,
                "system_info": None,
                "message": f"Error inesperado: {str(e)}"
            }

    async def check_dicomweb(self) -> bool:
        """Verificar si el plugin DICOMweb está disponible en Orthanc."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.dicomweb_url}/studies",
                    auth=self.auth
                )
                return response.status_code == 200
        except Exception:
            return False

    # ============================
    # PACIENTES
    # ============================

    async def get_all_patients(self) -> list:
        """Obtener la lista de IDs de todos los pacientes."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/patients",
                auth=self.auth
            )
            response.raise_for_status()
            return response.json()

    async def get_patient_details(self, patient_id: str) -> dict:
        """Obtener los detalles de un paciente específico."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/patients/{patient_id}",
                auth=self.auth
            )
            response.raise_for_status()
            return response.json()

    # ============================
    # ESTUDIOS
    # ============================

    async def get_all_studies(self) -> list:
        """Obtener la lista de IDs de todos los estudios."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/studies",
                auth=self.auth
            )
            response.raise_for_status()
            return response.json()

    async def get_study_details(self, study_id: str) -> dict:
        """Obtener los detalles de un estudio específico."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/studies/{study_id}",
                auth=self.auth
            )
            response.raise_for_status()
            return response.json()

    # ============================
    # SERIES
    # ============================

    async def get_study_series(self, study_id: str) -> list:
        """Obtener todas las series de un estudio."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/studies/{study_id}/series",
                auth=self.auth
            )
            response.raise_for_status()
            return response.json()

    async def get_series_details(self, series_id: str) -> dict:
        """Obtener los detalles de una serie específica."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/series/{series_id}",
                auth=self.auth
            )
            response.raise_for_status()
            return response.json()

    # ============================
    # INSTANCIAS (imágenes individuales)
    # ============================

    async def get_series_instances(self, series_id: str) -> list:
        """Obtener todas las instancias (imágenes) de una serie."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/series/{series_id}/instances",
                auth=self.auth
            )
            response.raise_for_status()
            return response.json()

    async def get_instance_details(self, instance_id: str) -> dict:
        """Obtener los detalles de una instancia específica."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/instances/{instance_id}",
                auth=self.auth
            )
            response.raise_for_status()
            return response.json()

    async def get_instance_file(self, instance_id: str) -> bytes:
        """Descargar el archivo DICOM de una instancia."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{self.base_url}/instances/{instance_id}/file",
                auth=self.auth
            )
            response.raise_for_status()
            return response.content

    async def get_instance_preview(self, instance_id: str) -> bytes:
        """Obtener una vista previa PNG de una instancia."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/instances/{instance_id}/preview",
                auth=self.auth
            )
            response.raise_for_status()
            return response.content

    async def get_instance_tags(self, instance_id: str) -> dict:
        """Obtener los tags DICOM de una instancia."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/instances/{instance_id}/simplified-tags",
                auth=self.auth
            )
            response.raise_for_status()
            return response.json()