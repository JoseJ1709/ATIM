import httpx
import logging
from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class JoeyCareRepository:
    """Repositorio para comunicación con JoeyCare Backend."""

    def __init__(self):
        self.base_url = settings.joeycare_url

    async def check_status(self) -> dict:
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
        self, neonato_id: int, file_content: bytes, filename: str, metadata: dict = None
    ) -> dict:
        """Subir una ecografía a JoeyCare."""
        upload_url = f"{self.base_url}{settings.joeycare_upload_endpoint}"

        logger.info(
            f"Subiendo ecografía a JoeyCare: neonato_id={neonato_id}, "
            f"filename={filename}, size={len(file_content)} bytes"
        )

        async with httpx.AsyncClient() as client:
            files = {"file": (filename, file_content, "application/dicom")}
            data = {"neonato_id": str(neonato_id)}

            if metadata:
                for key, value in metadata.items():
                    data[key] = str(value)

            response = await client.post(
                upload_url,
                files=files,
                data=data,
                timeout=30.0
            )
            response.raise_for_status()

            logger.info(
                f"Ecografía subida exitosamente a JoeyCare: "
                f"neonato_id={neonato_id}, status={response.status_code}"
            )

            return response.json()