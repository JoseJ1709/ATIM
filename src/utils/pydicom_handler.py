"""
Este módulo encapsula toda la lógica de análisis y validación de archivos DICOM
binarios usando pydicom. Se utiliza principalmente después de descargar archivos
desde DICOMweb para garantizar integridad y compatibilidad antes de transferir a JoyCare.

Responsabilidades:
- Validar que el archivo DICOM sea íntegro y no corrupto
- Extraer tags DICOM críticos de manera confiable
- Detectar ETF de manera más robusta (análisis de tags reales)
- Sanitizar datos antes de transferencia
- Proporcionar información de calidad de imagen
"""

import logging
import io
from typing import Dict, Optional, Any
from datetime import datetime

try:
    import pydicom
    from pydicom.errors import InvalidDicomError
    PYDICOM_AVAILABLE = True
except ImportError:
    PYDICOM_AVAILABLE = False
    logging.warning("⚠️ pydicom no está instalado. Validación de DICOM deshabilitada.")

logger = logging.getLogger("atim")


class PyDICOMHandler:
    """
    Métodos principales:
    - validate_dicom_integrity() — Validar que el archivo sea íntegro
    - extract_critical_tags() — Extraer tags esenciales
    - detect_etf() — Detectar ETF de manera robusta
    - get_pixel_information() — Información sobre píxeles
    """

    @staticmethod
    async def validate_dicom_integrity(file_bytes: bytes) -> Dict[str, Any]:
        """
        Validar que el archivo DICOM sea íntegro y transferible.
        
        Realiza múltiples validaciones:
        1. Es un archivo DICOM válido (encabezado correcto)
        2. Estructura interna no está corrupta
        3. Tiene datos de píxeles (para imágenes)
        4. Tags esenciales están presentes
        5. Codificación de caracteres es válida
        
        Args:
            file_bytes: Bytes del archivo DICOM descargado
        
        Returns:
            Diccionario con resultado de validación:
            {
              "is_valid": True,
              "file_size": 2048000,
              "errors": [],  # Vacío si es válido
              "modality": "US",
              "has_pixels": True,
              "patient_id": "12345",
              "patient_name": "Maria García",
              "sop_instance_uid": "1.2.840.10008..."
            }
        
        Raises:
            ValueError: Si el archivo es completamente inválido
        
        """
        if not PYDICOM_AVAILABLE:
            logger.warning("⚠️ pydicom no disponible, saltando validación profunda")
            return {
                "is_valid": True,
                "file_size": len(file_bytes),
                "warning": "Validación incompleta (pydicom no instalado)",
                "errors": []
            }

        logger.info(f"🔍 Validando integridad DICOM ({len(file_bytes)} bytes)...")
        errors = []
        
        try:
            # 1. Verificar que sea un archivo DICOM válido
            try:
                dicom_obj = pydicom.dcmread(io.BytesIO(file_bytes))
                logger.info("✅ Archivo DICOM válido - encabezado correcto")
            except InvalidDicomError as e:
                errors.append(f"Encabezado DICOM inválido: {str(e)}")
                logger.error(f"❌ {errors[-1]}")
                return {
                    "is_valid": False,
                    "file_size": len(file_bytes),
                    "errors": errors,
                    "reason": "DICOM inválido"
                }
            except Exception as e:
                errors.append(f"Error lectura DICOM: {str(e)}")
                logger.error(f"❌ {errors[-1]}")
                return {
                    "is_valid": False,
                    "file_size": len(file_bytes),
                    "errors": errors,
                    "reason": "Archivo corrupto"
                }

            # 2. Verificar tags esenciales
            essential_tags = {
                "SOPInstanceUID": "Identificador único de la instancia",
                "SOPClassUID": "Tipo de objeto DICOM",
                "Modality": "Modalidad de imagen",
                "PatientID": "ID del paciente"
            }
            
            for tag_name, tag_desc in essential_tags.items():
                if not hasattr(dicom_obj, tag_name):
                    errors.append(f"Tag esencial faltante: {tag_name} ({tag_desc})")
                    logger.warning(f"⚠️ {errors[-1]}")

            # 3. Verificar datos de píxeles (si aplica)
            has_pixels = False
            pixel_info = {}
            
            if hasattr(dicom_obj, "pixel_array"):
                try:
                    pixel_array = dicom_obj.pixel_array
                    has_pixels = True
                    pixel_info = {
                        "shape": pixel_array.shape,
                        "size": pixel_array.size,
                        "dtype": str(pixel_array.dtype),
                        "min_value": float(pixel_array.min()),
                        "max_value": float(pixel_array.max())
                    }
                    logger.info(
                        f"✅ Píxeles válidos: {pixel_array.shape}, "
                        f"rango [{pixel_array.min()}-{pixel_array.max()}]"
                    )
                except Exception as e:
                    errors.append(f"Error accediendo a píxeles: {str(e)}")
                    logger.warning(f"⚠️ {errors[-1]}")
            else:
                logger.info("ℹ️ DICOM sin datos de píxeles (ej: SR, KOS)")

            # 4. Verificar codificación de caracteres
            try:
                patient_name = PyDICOMHandler._safely_get_tag(
                    dicom_obj, "PatientName", ""
                )
                if isinstance(patient_name, bytes):
                    try:
                        patient_name = patient_name.decode('utf-8')
                    except UnicodeDecodeError:
                        errors.append("Codificación de caracteres inválida")
                        logger.warning(f"⚠️ {errors[-1]}")
            except Exception as e:
                errors.append(f"Error validando caracteres: {str(e)}")
                logger.warning(f"⚠️ {errors[-1]}")

            # 5. Construir resultado
            result = {
                "is_valid": len(errors) == 0,
                "file_size": len(file_bytes),
                "errors": errors,
                "modality": PyDICOMHandler._safely_get_tag(dicom_obj, "Modality", "UNKNOWN"),
                "has_pixels": has_pixels,
                "pixel_info": pixel_info if has_pixels else None,
                "patient_id": PyDICOMHandler._safely_get_tag(dicom_obj, "PatientID", "unknown"),
                "patient_name": PyDICOMHandler._safely_get_tag(dicom_obj, "PatientName", "Unknown"),
                "sop_instance_uid": PyDICOMHandler._safely_get_tag(
                    dicom_obj, "SOPInstanceUID", "unknown"
                ),
                "sop_class_uid": PyDICOMHandler._safely_get_tag(dicom_obj, "SOPClassUID", ""),
                "study_date": PyDICOMHandler._safely_get_tag(dicom_obj, "StudyDate", ""),
                "series_number": PyDICOMHandler._safely_get_tag(dicom_obj, "SeriesNumber", ""),
                "instance_number": PyDICOMHandler._safely_get_tag(dicom_obj, "InstanceNumber", "")
            }

            if result["is_valid"]:
                logger.info(f"✅ DICOM íntegro y transferible")
            else:
                logger.warning(f"⚠️ DICOM con {len(errors)} problemas, pero intentaremos transferir")

            return result

        except Exception as e:
            logger.error(f"❌ Error fatal en validación DICOM: {str(e)}")
            return {
                "is_valid": False,
                "file_size": len(file_bytes),
                "errors": [f"Error fatal: {str(e)}"],
                "reason": "Excepción no controlada"
            }

    @staticmethod
    async def extract_critical_tags(file_bytes: bytes) -> Dict[str, Any]:
        """
        Extraer todos los tags DICOM críticos de manera confiable.
        
        Extrae tags importantes sin depender del mapeo manual.
        
        Args:
            file_bytes: Bytes del archivo DICOM
        
        Returns:
            Diccionario con tags DICOM parseados (nombres legibles)
        """
        if not PYDICOM_AVAILABLE:
            logger.warning("⚠️ pydicom no disponible, no se pueden extraer tags")
            return {}

        logger.info(f"📋 Extrayendo tags críticos DICOM...")
        
        try:
            dicom_obj = pydicom.dcmread(io.BytesIO(file_bytes))
            
            # Tags críticos que queremos extraer
            critical_tags = [
                "PatientName",
                "PatientID",
                "PatientAge",
                "PatientSex",
                "StudyDate",
                "StudyTime",
                "StudyDescription",
                "SeriesNumber",
                "SeriesDescription",
                "SeriesTime",
                "Modality",
                "Manufacturer",
                "ManufacturerModelName",
                "InstitutionName",
                "InstanceNumber",
                "SOPInstanceUID",
                "SOPClassUID",
                "ReferencedImageSequence",
                "AnatomicRegionSequence",
                "ProcedureCodeSequence"
            ]
            
            extracted_tags = {}
            
            for tag_name in critical_tags:
                value = PyDICOMHandler._safely_get_tag(dicom_obj, tag_name, None)
                if value is not None:
                    extracted_tags[tag_name] = value
            
            logger.info(f"✅ {len(extracted_tags)} tags extraídos")
            return extracted_tags
            
        except Exception as e:
            logger.error(f"❌ Error extrayendo tags: {str(e)}")
            return {}

    @staticmethod
    async def detect_etf(file_bytes: bytes) -> Dict[str, Any]:
        """
        Detectar si el DICOM es probablemente ETF (Ecografía Transfontanelar).
                
        Criterios:
        1. Modalidad es "US" (Ultrasound)
        2. AnatomicRegionSequence contiene "HEAD" o "BRAIN"
        3. Descripción contiene keywords ETF (fallback)
        4. SeriesDescription sugiere posición (anterior, posterior, fontanelle)
        
        Args:
            file_bytes: Bytes del archivo DICOM
        
        Returns:
            Diccionario con análisis ETF:
            {
              "is_etf": True,
              "confidence": 0.95,  # 0-1
              "criteria_met": ["Modality=US", "AnatomicRegion=HEAD"],
              "modality": "US",
              "anatomic_region": "HEAD",
              "series_description": "Brain midline view",
              "reasoning": "Ecografía cerebral en neonato"
            }
        """
        if not PYDICOM_AVAILABLE:
            logger.warning("⚠️ pydicom no disponible, detección ETF limitada")
            return {
                "is_etf": False,
                "confidence": 0.0,
                "warning": "Detección incompleta (pydicom no instalado)"
            }

        logger.info(f"🧠 Detectando si es ETF...")
        
        try:
            dicom_obj = pydicom.dcmread(io.BytesIO(file_bytes))
            
            criteria_met = []
            confidence = 0.0
            
            # Criterio 1: Modalidad US
            modality = PyDICOMHandler._safely_get_tag(dicom_obj, "Modality", "")
            if modality == "US":
                criteria_met.append("Modality=US")
                confidence += 0.3
                logger.info("✅ Criterio 1: Modalidad US confirmada")
            else:
                logger.warning(f"❌ Modalidad no es US: {modality}")
                return {
                    "is_etf": False,
                    "confidence": 0.0,
                    "reason": f"Modalidad es {modality}, no US"
                }
            
            # Criterio 2: Región anatómica (tags DICOM)
            anatomic_region = None
            if hasattr(dicom_obj, "AnatomicRegionSequence"):
                try:
                    for item in dicom_obj.AnatomicRegionSequence:
                        if hasattr(item, "CodeMeaning"):
                            anatomic_region = str(item.CodeMeaning)
                            if "HEAD" in anatomic_region.upper() or "BRAIN" in anatomic_region.upper():
                                criteria_met.append(f"AnatomicRegion={anatomic_region}")
                                confidence += 0.4
                                logger.info(f"✅ Criterio 2: Región anatómica cerebral detectada: {anatomic_region}")
                except Exception as e:
                    logger.debug(f"No se pudo leer AnatomicRegionSequence: {str(e)}")
            
            # Criterio 3: Descripción (fallback)
            series_description = PyDICOMHandler._safely_get_tag(
                dicom_obj, "SeriesDescription", ""
            ).lower()
            
            etf_keywords = [
                "transfontanelar", "fontanel", "fontanelle",
                "anterior fontanelle", "posterior fontanelle",
                "brain", "cerebral", "cranial",
                "cerebro", "etf"
            ]
            
            if any(keyword in series_description for keyword in etf_keywords):
                criteria_met.append(f"Description_Keywords=[{', '.join([k for k in etf_keywords if k in series_description])}]")
                confidence += 0.25
                logger.info(f"✅ Criterio 3: Keywords ETF encontrados en descripción")
            
            # Criterio 4: Edad del paciente (neonato/lactante)
            patient_age = PyDICOMHandler._safely_get_tag(dicom_obj, "PatientAge", "")
            is_neonatal = False
            if patient_age:
                try:
                    # Format típico: "030D" (30 días), "002W" (2 semanas)
                    age_value = int(patient_age[:-1]) if len(patient_age) > 1 else 0
                    age_unit = patient_age[-1] if len(patient_age) > 1 else ""
                    
                    # Convertir a días
                    if age_unit == "D":
                        age_days = age_value
                    elif age_unit == "W":
                        age_days = age_value * 7
                    elif age_unit == "M":
                        age_days = age_value * 30
                    elif age_unit == "Y":
                        age_days = age_value * 365
                    else:
                        age_days = 0
                    
                    # Neonato/lactante: 0-365 días (0-12 meses)
                    if 0 <= age_days <= 365:
                        is_neonatal = True
                        criteria_met.append(f"PatientAge=Neonatal({patient_age})")
                        confidence += 0.15
                        logger.info(f"✅ Criterio 4: Edad neonatal detectada: {patient_age}")
                except Exception as e:
                    logger.debug(f"No se pudo parsear edad del paciente: {str(e)}")
            
            # Resultado final
            is_etf = confidence >= 0.5
            
            result = {
                "is_etf": is_etf,
                "confidence": round(confidence, 2),
                "criteria_met": criteria_met,
                "modality": modality,
                "anatomic_region": anatomic_region,
                "series_description": series_description,
                "patient_age": patient_age,
                "is_neonatal_age": is_neonatal
            }
            
            if is_etf:
                logger.info(f"🧠 ✅ Es probablemente ETF (confianza: {confidence})")
            else:
                logger.info(f"🧠 ⚠️ No hay suficientes criterios ETF (confianza: {confidence})")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error detectando ETF: {str(e)}")
            return {
                "is_etf": False,
                "confidence": 0.0,
                "error": str(e)
            }

    @staticmethod
    def _safely_get_tag(dicom_obj: Any, tag_name: str, default: Any = None) -> Any:
        """
        Obtener un tag DICOM de manera segura sin raises.
        
        Maneja:
        - Tags que no existen
        - Valores None
        - Conversión de tipos
        - Excepciones internas
        
        Args:
            dicom_obj: Objeto pydicom Dataset
            tag_name: Nombre del tag (ej: "PatientName")
            default: Valor por defecto si no existe o hay error
        
        Returns:
            Valor del tag o valor default
        """
        try:
            if not hasattr(dicom_obj, tag_name):
                return default
            
            value = getattr(dicom_obj, tag_name)
            
            if value is None:
                return default
            
            # Convertir bytes a string si es necesario
            if isinstance(value, bytes):
                try:
                    return value.decode('utf-8').strip()
                except UnicodeDecodeError:
                    return str(value)
            
            return value
            
        except Exception as e:
            logger.debug(f"Error accediendo a tag {tag_name}: {str(e)}")
            return default

    @staticmethod
    async def get_pixel_information(file_bytes: bytes) -> Dict[str, Any]:
        """
        Obtener información detallada sobre los píxeles de la imagen.
        
        Útil para validar integridad de datos de imagen.
        
        Args:
            file_bytes: Bytes del archivo DICOM
        
        Returns:
            Diccionario con información de píxeles
        
        """
        if not PYDICOM_AVAILABLE:
            return {"error": "pydicom no disponible"}

        try:
            dicom_obj = pydicom.dcmread(io.BytesIO(file_bytes))
            
            info = {
                "has_pixels": hasattr(dicom_obj, "pixel_array"),
                "samples_per_pixel": PyDICOMHandler._safely_get_tag(
                    dicom_obj, "SamplesPerPixel", None
                ),
                "rows": PyDICOMHandler._safely_get_tag(dicom_obj, "Rows", None),
                "columns": PyDICOMHandler._safely_get_tag(dicom_obj, "Columns", None),
                "bits_allocated": PyDICOMHandler._safely_get_tag(
                    dicom_obj, "BitsAllocated", None
                ),
                "bits_stored": PyDICOMHandler._safely_get_tag(
                    dicom_obj, "BitsStored", None
                ),
                "photometric_interpretation": PyDICOMHandler._safely_get_tag(
                    dicom_obj, "PhotometricInterpretation", None
                )
            }
            
            if info["has_pixels"] and info["rows"] and info["columns"]:
                info["resolution"] = f"{info['columns']}x{info['rows']}"
                info["is_multiframe"] = hasattr(dicom_obj, "NumberOfFrames")
                if info["is_multiframe"]:
                    info["number_of_frames"] = int(
                        PyDICOMHandler._safely_get_tag(
                            dicom_obj, "NumberOfFrames", 1
                        )
                    )
            
            return info
            
        except Exception as e:
            logger.error(f"Error obteniendo información de píxeles: {str(e)}")
            return {"error": str(e)}