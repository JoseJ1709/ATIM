from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración centralizada de ATIM cargada desde variables de entorno."""

    # App
    app_name: str = "ATIM"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = True

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Orthanc (PACS)
    orthanc_host: str = "localhost"
    orthanc_http_port: int = 8042
    orthanc_dicom_port: int = 4242
    orthanc_username: str = "orthanc"
    orthanc_password: str = "orthanc"
    orthanc_use_dicomweb: bool = True

    # JoyCare
    joycare_host: str = "joycare-backend"
    joycare_port: int = 3000
    joycare_upload_endpoint: str = "/api/upload"

    # Security
    secret_key: str = "cambiar-esto-en-produccion-con-algo-seguro"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    aes_encryption_key: str = "cambiar-esto-tambien-32-bytes-key"

    @property
    def orthanc_url(self) -> str:
        """URL base de Orthanc."""
        return f"http://{self.orthanc_host}:{self.orthanc_http_port}"

    @property
    def orthanc_dicomweb_url(self) -> str:
        """URL de DICOMweb de Orthanc."""
        return f"{self.orthanc_url}/dicom-web"

    @property
    def joycare_url(self) -> str:
        """URL base de JoyCare."""
        return f"http://{self.joycare_host}:{self.joycare_port}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


def get_settings() -> Settings:
    """Obtener la instancia de configuración."""
    return Settings()