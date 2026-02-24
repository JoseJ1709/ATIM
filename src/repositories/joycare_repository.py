import httpx
import logging

from src.config.settings import Settings

logger = logging.getLogger("atim")


class JoyCareRepository:
    """Repositorio para comunicación con el backend de JoyCare."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.joycare_url

    async def check_connection(self) -> dict:
        """Verificar si JoyCare backend está accesible."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/neonatos")
                return {
                    "reachable": response.status_code == 200,
                    "message": "Conexión exitosa con JoyCare"
                }
        except httpx.ConnectError:
            return {
                "reachable": False,
                "message": f"No se puede conectar a JoyCare en {self.base_url}"
            }
        except Exception as e:
            return {
                "reachable": False,
                "message": f"Error inesperado: {str(e)}"
            }

    async def get_neonatos(self) -> list:
        """Obtener la lista de neonatos desde JoyCare."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/api/neonatos")
            response.raise_for_status()
            return response.json()

    async def upload_ecografia(
        self,
        neonato_id: int,
        file_bytes: bytes,
        filename: str,
        uploader_medico_id: int,
        sede_id: int = None,
        mime_type: str = "application/dicom"
    ) -> dict:
        """
        Subir una ecografía al backend de JoyCare.
        
        Envía el archivo como multipart/form-data al endpoint:
        POST /api/ecografias/{neonatoId}
        """
        logger.info(
            f"Subiendo ecografía a JoyCare: neonato={neonato_id}, "
            f"archivo={filename}, tamaño={len(file_bytes)} bytes"
        )

        # Construir el formulario multipart
        files = {
            "imagen": (filename, file_bytes, mime_type)
        }
        data = {
            "uploader_medico_id": str(uploader_medico_id)
        }
        if sede_id is not None:
            data["sede_id"] = str(sede_id)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/api/ecografias/{neonato_id}",
                files=files,
                data=data
            )
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"Ecografía subida exitosamente a JoyCare: "
                f"id={result.get('id')}, filepath={result.get('filepath')}"
            )
            return result