"""
Mapeo de tags DICOM a nombres legibles.

Los tags DICOM son códigos hexadecimales como "0020000D" que representan
campos específicos. Este módulo traduce esos códigos a nombres comprensibles.

Referencia: https://dicom.nema.org/medical/dicom/current/output/chtml/part06/chapter_6.html
"""

# Mapeo completo de tags DICOM usados en DICOMweb
DICOM_TAG_NAMES = {
    # Patient-related tags (0x0010,xxxx)
    "00100010": "PatientName",
    "00100020": "PatientID",
    "00100030": "PatientBirthDate",
    "00100040": "PatientSex",
    "00101000": "OtherPatientIDs",
    "00101001": "OtherPatientNames",

    # Study-related tags (0x0020,xxxx)
    "0020000D": "StudyInstanceUID",
    "0020000E": "SeriesInstanceUID",
    "00080020": "StudyDate",
    "00080030": "StudyTime",
    "00080050": "AccessionNumber",
    "00081030": "StudyDescription",
    "00080060": "Modality",
    "00080070": "Manufacturer",
    "00080080": "InstitutionName",
    "00081110": "ReferencedStudySequence",

    # Series-related tags
    "0008103E": "SeriesDescription",
    "00200011": "SeriesNumber",
    "00200060": "SeriesDescription",
    "0008103F": "SeriesNumber",

    # Instance-related tags (0x0008,xxxx)
    "00080018": "SOPInstanceUID",
    "00080016": "SOPClassUID",
    "00200013": "InstanceNumber",
    "00200032": "ImagePositionPatient",
    "00200037": "ImageOrientationPatient",
    "00280010": "Rows",
    "00280011": "Columns",
    "00280002": "SamplesperPixel",
    "00280004": "PhotometricInterpretation",
    "00280008": "NumberofFrames",
    "00280010": "Rows",
    "00280011": "Columns",
    "00280100": "BitsAllocated",
    "00280101": "BitsStored",
    "00280102": "HighBit",
    "00280103": "PixelRepresentation",

    # Acquisition-related tags
    "00180050": "SliceThickness",
    "00180088": "SpacingBetweenSlices",
    "00181030": "ProtocolName",
    "00181090": "CardiacNumberofImages",

    # Image-related tags
    "00280002": "SamplesperPixel",
    "00280004": "PhotometricInterpretation",
    "00280008": "NumberofFrames",
    "00280010": "Rows",
    "00280011": "Columns",
    "00280030": "PixelSpacing",
    "00280100": "BitsAllocated",
    "00280101": "BitsStored",
    "00280102": "HighBit",
    "00280103": "PixelRepresentation",
    "00281050": "WindowCenter",
    "00281051": "WindowWidth",
}


def get_tag_name(tag_hex: str) -> str:
    """
    Obtener el nombre legible de un tag DICOM.
    
    Args:
        tag_hex: Tag en formato hexadecimal (ej: "0020000D")
    
    Returns:
        Nombre del tag (ej: "StudyInstanceUID") o el tag original si no existe.
    
    Ejemplo:
        >>> get_tag_name("0020000D")
        "StudyInstanceUID"
        
        >>> get_tag_name("99999999")
        "99999999"  # Tag desconocido
    """
    return DICOM_TAG_NAMES.get(tag_hex.upper(), tag_hex)


def extract_value(dicom_element: dict) -> str | int | None:
    """
    Extraer el valor de un elemento DICOM.
    
    DICOMweb devuelve elementos con estructura:
    {
        "VR": "UI",           # Value Representation (tipo)
        "Value": ["1.3.12..."] # Array con el(los) valor(es)
    }
    
    Args:
        dicom_element: Elemento DICOM del JSON
    
    Returns:
        El primer valor del array Value, o None si no existe.
    
    Ejemplo:
        >>> element = {"VR": "UI", "Value": ["1.3.12.2.1107..."]}
        >>> extract_value(element)
        "1.3.12.2.1107..."
    """
    if not isinstance(dicom_element, dict):
        return None
    
    value_array = dicom_element.get("Value", [])
    
    if not value_array:
        return None
    
    # El primer valor es generalmente lo que queremos
    first_value = value_array[0]
    
    # Si es un diccionario con "Alphabetic" (nombre de paciente), extraerlo
    if isinstance(first_value, dict):
        return first_value.get("Alphabetic", str(first_value))
    
    return first_value


def extract_vr(dicom_element: dict) -> str | None:
    """
    Obtener el tipo de dato (Value Representation) de un elemento DICOM.
    
    Args:
        dicom_element: Elemento DICOM del JSON
    
    Returns:
        El VR (ej: "UI", "PN", "DA") o None
    
    Ejemplo:
        >>> element = {"VR": "UI", "Value": ["1.3.12..."]}
        >>> extract_vr(element)
        "UI"
    """
    return dicom_element.get("VR") if isinstance(dicom_element, dict) else None


def parse_dicom_json(dicom_json: dict) -> dict:
    """
    Parsear un JSON DICOM completo y convertirlo a diccionario legible.
    
    Convierte:
        {
            "0020000D": {"VR": "UI", "Value": ["1.3.12..."]},
            "00100010": {"VR": "PN", "Value": [{"Alphabetic": "John DOE"}]},
            ...
        }
    
    En:
        {
            "StudyInstanceUID": "1.3.12...",
            "PatientName": "John DOE",
            ...
        }
    
    Args:
        dicom_json: JSON DICOM crudo de DICOMweb
    
    Returns:
        Diccionario con nombres legibles y valores extraídos
    
    Ejemplo:
        >>> raw = {
        ...     "0020000D": {"VR": "UI", "Value": ["1.3.12..."]},
        ...     "00100010": {"VR": "PN", "Value": [{"Alphabetic": "John"}]}
        ... }
        >>> parse_dicom_json(raw)
        {"StudyInstanceUID": "1.3.12...", "PatientName": "John"}
    """
    parsed = {}
    
    for tag_hex, element in dicom_json.items():
        tag_name = get_tag_name(tag_hex)
        value = extract_value(element)
        
        if value is not None:
            parsed[tag_name] = value
    
    return parsed


# Mapeo de tags DICOM a campos estándar para nuestros schemas
# Útil para normalizar nombres entre API REST y DICOMweb
DICOM_TO_SCHEMA_MAPPING = {
    # Study
    "StudyInstanceUID": "study_instance_uid",
    "StudyDate": "study_date",
    "StudyDescription": "study_description",
    "StudyTime": "study_time",
    "AccessionNumber": "accession_number",
    
    # Series
    "SeriesInstanceUID": "series_instance_uid",
    "SeriesDescription": "series_description",
    "Modality": "modality",
    "SeriesNumber": "series_number",
    
    # Instance
    "SOPInstanceUID": "sop_instance_uid",
    "SOPClassUID": "sop_class_uid",
    "InstanceNumber": "instance_number",
    
    # Patient
    "PatientName": "patient_name",
    "PatientID": "patient_id",
    "PatientBirthDate": "birth_date",
    "PatientSex": "sex",
}


def normalize_field_name(dicom_tag_name: str) -> str:
    """
    Convertir nombre DICOM a campo de schema.
    
    Args:
        dicom_tag_name: Nombre DICOM (ej: "PatientName")
    
    Returns:
        Nombre de campo snake_case (ej: "patient_name")
    
    Ejemplo:
        >>> normalize_field_name("PatientName")
        "patient_name"
    """
    return DICOM_TO_SCHEMA_MAPPING.get(dicom_tag_name, dicom_tag_name.lower())