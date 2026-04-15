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

    # JoeyCare
    joeycare_host: str = "joeycare-backend"
    joeycare_port: int = 4000
    joeycare_upload_endpoint: str = "/api/upload"

    # Security - JWT
    secret_key: str = "cambiar-esto-en-produccion-con-algo-seguro"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Security - AES-256 Encryption
    aes_encryption_key: str = "cambiar-esto-tambien-32-bytes!!"  # Exactamente 32 bytes

    # Security - API Keys (ATIM <-> PACS)
    api_key_atim: str = "atim-pacs-key-cambiar-en-produccion-2026"

    # Security - Rate Limiting
    rate_limit_per_minute: int = 60
    rate_limit_upload_per_minute: int = 20

    @property
    def orthanc_url(self) -> str:
        return f"http://{self.orthanc_host}:{self.orthanc_http_port}"

    @property
    def orthanc_dicomweb_url(self) -> str:
        return f"{self.orthanc_url}/dicom-web"

    @property
    def joeycare_url(self) -> str:
        return f"http://{self.joeycare_host}:{self.joeycare_port}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


def get_settings() -> Settings:
    return Settings()