import httpx
import logging
from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class JoeyCareRepository:
    """Repositorio para comunicación con JoeyCare Backend."""

    def __init__(self):
        self.base_url = settings.joeycare_url

    async def check_connection(self) -> dict:
        """Verificar si JoeyCare está disponible."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/neonatos", timeout=5.0)
                return {
                    "status": "connected",
                    "message": "JoeyCare Backend está disponible",
                    "url": self.base_url
                }
        except Exception as e:
            return {
                "status": "disconnected",
                "message": f"No se pudo conectar con JoeyCare: {str(e)}",
                "url": self.base_url
            }

    async def get_neonatos(self) -> list:
        """Obtener la lista de neonatos desde JoeyCare."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/neonatos",
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()

    async def upload_ecografia(
        self,
        neonato_id: int,
        file_content: bytes,
        filename: str,
        uploader_medico_id: int,
        sede_id: int | None = None,
        fecha_hora: str | None = None,
        mime_type: str = "application/dicom",
        metadata: dict | None = None,
    ) -> dict:
        """Subir una ecografia a JoeyCare."""
        upload_url = f"{self.base_url}{settings.joeycare_upload_endpoint}/{neonato_id}"

        logger.info(
            f"Subiendo ecografia a JoeyCare: neonato_id={neonato_id}, "
            f"filename={filename}, size={len(file_content)} bytes"
        )

        data = {"uploader_medico_id": str(uploader_medico_id)}
        if sede_id is not None:
            data["sede_id"] = str(sede_id)
        if fecha_hora:
            data["fecha_hora"] = fecha_hora
        if metadata:
            for key, value in metadata.items():
                data[key] = str(value)

        files = {"imagen": (filename, file_content, mime_type)}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                upload_url,
                files=files,
                data=data,
                timeout=30.0
            )
            response.raise_for_status()

        logger.info(
            f"Ecografia subida exitosamente a JoeyCare: "
            f"neonato_id={neonato_id}, status={response.status_code}"
        )

        return response.json()