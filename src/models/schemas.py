from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ============================
# HEALTH
# ============================

class HealthResponse(BaseModel):
    """Respuesta del endpoint de health check."""
    status: str
    app_name: str
    version: str
    environment: str
    timestamp: datetime


class PacsStatusResponse(BaseModel):
    """Respuesta del estado de conexión con un PACS."""
    pacs_name: str
    host: str
    port: int
    reachable: bool
    dicomweb_available: bool
    message: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Respuesta estándar de error."""
    error: str
    detail: Optional[str] = None
    status_code: int


# ============================
# PACIENTES
# ============================

class PatientSummary(BaseModel):
    """Resumen de un paciente."""
    orthanc_id: str
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    birth_date: Optional[str] = None
    sex: Optional[str] = None
    studies_count: int = 0


# ============================
# ESTUDIOS
# ============================

class StudySummary(BaseModel):
    """Resumen de un estudio."""
    orthanc_id: str
    study_instance_uid: Optional[str] = None
    study_date: Optional[str] = None
    study_description: Optional[str] = None
    patient_name: Optional[str] = None
    patient_id: Optional[str] = None
    series_count: int = 0


class StudyDetail(StudySummary):
    """Detalle completo de un estudio con sus series."""
    series: List[dict] = []


# ============================
# SERIES
# ============================

class SeriesSummary(BaseModel):
    """Resumen de una serie."""
    orthanc_id: str
    series_instance_uid: Optional[str] = None
    modality: Optional[str] = None
    series_description: Optional[str] = None
    instances_count: int = 0


# ============================
# INSTANCIAS
# ============================

class InstanceSummary(BaseModel):
    """Resumen de una instancia (imagen DICOM individual)."""
    orthanc_id: str
    sop_instance_uid: Optional[str] = None
    instance_number: Optional[str] = None


# ============================
# TRANSFERENCIA
# ============================

class TransferInstanceRequest(BaseModel):
    """Solicitud para transferir una instancia DICOM de Orthanc a JoyCare."""
    instance_id: str
    neonato_id: int
    uploader_medico_id: int
    sede_id: Optional[int] = None


class TransferSeriesRequest(BaseModel):
    """Solicitud para transferir una serie completa de Orthanc a JoyCare."""
    series_id: str
    neonato_id: int
    uploader_medico_id: int
    sede_id: Optional[int] = None


class TransferResult(BaseModel):
    """Resultado de la transferencia de una instancia."""
    status: str
    message: str
    orthanc_instance_id: str
    filename: str
    file_size_bytes: int
    joycare_response: dict


class TransferSeriesResult(BaseModel):
    """Resultado de la transferencia de una serie completa."""
    status: str
    series_id: str
    total_instances: int
    transferred: int
    failed: int
    results: List[dict] = []
    errors: List[dict] = []