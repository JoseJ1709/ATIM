"""
Servicio de transferencia via DICOMweb: descarga imágenes desde cualquier PACS
compatible con DICOMweb (usando UIDs estándar DICOM) y las sube a JoyCare.

Este servicio es la versión "estándar" de TransferService.
- TransferService: Usa API REST propietaria de Orthanc (IDs internos)
- DICOMwebTransferService: Usa DICOMweb estándar (UIDs DICOM universales)

"""

import logging
from typing import List, Optional

from src.config.settings import Settings
from src.services.dicomweb_service import DICOMwebService
from src.repositories.joycare_repository import JoyCareRepository
from src.utils.pydicom_handler import PyDICOMHandler

logger = logging.getLogger("atim")


class DICOMwebTransferService:
    
    @staticmethod
    def _get_value(item, *keys, default=None):
        if isinstance(item, dict):
            for k in keys:
                v = item.get(k)
                if v not in (None, ""):
                    return v
            return default
        for k in keys:
            v = getattr(item, k, None)
            if v not in (None, ""):
                return v
        return default
        
    """
    Servicio de transferencia via DICOMweb: descarga imágenes usando UIDs DICOM
    y las sube a JoyCare para asociarlas a neonatos.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.dicomweb_service = DICOMwebService(settings)
        self.joycare_repo = JoyCareRepository(settings)

    # ============================
    # ESTADO DE JOYCARE
    # ============================

    async def check_joycare_connection(self) -> dict:
        """
        Verificar conexión con JoyCare.
        """
        logger.info("🔗 Verificando conexión con JoyCare...")
        
        try:
            result = await self.joycare_repo.check_connection()
            logger.info("✅ JoyCare conectado")
            return result
        except Exception as e:
            logger.error(f"❌ Error conectando con JoyCare: {str(e)}")
            raise

    async def get_joycare_neonatos(self) -> list:
        """
        Obtener la lista de neonatos desde JoyCare.
        
        Useful para que el frontend muestre qué neonatos están disponibles
        para recibir ecografías.
        
        Returns:
            Lista de neonatos con id, nombre, etc.
        
        """
        logger.info("📋 Obteniendo lista de neonatos de JoyCare...")
        
        try:
            neonatos = await self.joycare_repo.get_neonatos()
            logger.info(f"✅ {len(neonatos)} neonatos obtenidos")
            return neonatos
        except Exception as e:
            logger.error(f"❌ Error obteniendo neonatos: {str(e)}")
            raise

    # ============================
    # TRANSFERENCIA: INSTANCIA ÚNICA
    # ============================

    async def transfer_instance(
        self,
        study_uid: str,
        series_uid: str,
        instance_uid: str,
        neonato_id: int,
        uploader_medico_id: int,
        sede_id: Optional[int] = None
    ) -> dict:
        """
        Transferir una instancia DICOM desde DICOMweb a JoyCare.
        
        MEJORADO: Usa PyDICOMHandler para validación robusta.
        """
        logger.info(
            f"⬇️ Iniciando transferencia DICOMweb: "
            f"instance={instance_uid} → neonato={neonato_id}, médico={uploader_medico_id}"
        )

        try:
            # 1. Obtener tags DICOM para información descriptiva
            logger.info(f"📋 Obteniendo tags DICOM de instancia: {instance_uid}")
            tags = await self.dicomweb_service.get_instance_tags(
                study_uid, series_uid, instance_uid
            )
            
            patient_name = tags.get("PatientName", "unknown")
            modality = tags.get("Modality", "US")
            instance_number = tags.get("InstanceNumber", "0")
            sop_class_uid = tags.get("SOPClassUID", "")
            
            logger.info(f"📊 Tags obtenidos: paciente={patient_name}, modalidad={modality}")

            # 2. Validar que sea ultrasound (compatible con JoyCare)
            if modality != "US":
                logger.warning(
                    f"⚠️ Modalidad {modality} no es ultrasound. "
                    f"JoyCare idealmente espera US (Ultrasound), pero continuaremos"
                )
            else:
                logger.info(f"✅ Modalidad confirmada: US (Ultrasound)")

            # 3. Verificar si es potencialmente ETF (por descripción)
            series_description = tags.get("SeriesDescription", "")
            is_etf_by_description = await self.dicomweb_service.is_transfontanelar_echography(
                study_uid, series_uid, series_description
            )
            
            if is_etf_by_description:
                logger.info(f"🧠 ✅ Probablemente es ETF (análisis de descripción)")
            else:
                logger.info(f"ℹ️ No se confirmó ETF en descripción: {series_description}")

            # 4. Descargar archivo DICOM desde DICOMweb
            logger.info(f"⬇️ Descargando archivo DICOM desde DICOMweb...")
            file_bytes = await self.dicomweb_service.get_instance_file(
                study_uid, series_uid, instance_uid
            )
            file_size = len(file_bytes)
            logger.info(f"✅ Descargado: {file_size} bytes")

            # ============================================================
            # 5. Validar integridad DICOM con PyDICOMHandler
            # ============================================================
            logger.info(f"🔍 Validando integridad del archivo DICOM...")
            validation_result = await PyDICOMHandler.validate_dicom_integrity(file_bytes)
            
            if not validation_result.get("is_valid"):
                errors = validation_result.get("errors", [])
                logger.warning(
                    f"⚠️ Archivo DICOM tiene {len(errors)} problemas: {errors}"
                )
                # Decidimos si continuamos o abortamos
                # Por ahora avisamos pero continuamos
                logger.info("ℹ️ Continuando de todas formas (validación no es crítica)")
            else:
                logger.info("✅ Archivo DICOM íntegro y válido")
            
            # Obtener información adicional del archivo descargado
            validation_modality = validation_result.get("modality", modality)
            validation_patient_id = validation_result.get("patient_id", "unknown")

            # ============================================================
            # 6.  Detectar ETF de manera robusta con pydicom
            # ============================================================
            logger.info(f"🧠 Analizando tags DICOM para detectar ETF...")
            etf_analysis = await PyDICOMHandler.detect_etf(file_bytes)
            
            is_etf_by_dicom = etf_analysis.get("is_etf", False)
            etf_confidence = etf_analysis.get("confidence", 0.0)
            etf_criteria = etf_analysis.get("criteria_met", [])
            
            # Combinar análisis: descripción + tags DICOM reales
            is_etf_final = is_etf_by_description or is_etf_by_dicom
            
            if is_etf_by_dicom:
                logger.info(
                    f"🧠 ✅ ETF detectada por análisis DICOM "
                    f"(confianza: {etf_confidence}, criterios: {etf_criteria})"
                )
            else:
                logger.info(
                    f"🧠 ⚠️ ETF no confirmada por tags DICOM "
                    f"(confianza: {etf_confidence})"
                )

            # ============================================================
            # 7. Extraer tags críticos con pydicom
            # ============================================================
            logger.info(f"📋 Extrayendo tags críticos con pydicom...")
            critical_tags = await PyDICOMHandler.extract_critical_tags(file_bytes)
            
            if critical_tags:
                logger.info(f"✅ {len(critical_tags)} tags críticos extraídos")
            else:
                logger.info(f"ℹ️ No se pudieron extraer tags adicionales (pydicom no disponible)")

            # ============================================================
            # 8. Obtener información de píxeles
            # ============================================================
            logger.info(f"📊 Analizando información de píxeles...")
            pixel_info = await PyDICOMHandler.get_pixel_information(file_bytes)
            
            if pixel_info.get("has_pixels"):
                resolution = pixel_info.get("resolution", "desconocida")
                is_multiframe = pixel_info.get("is_multiframe", False)
                logger.info(f"✅ Píxeles válidos: resolución {resolution}, multiframe: {is_multiframe}")
            else:
                logger.info(f"ℹ️ DICOM sin datos de píxeles")

            # 9. Construir nombre de archivo descriptivo
            filename = self._build_filename(
                patient_name=patient_name,
                modality=modality,
                instance_number=instance_number,
                study_uid=study_uid
            )
            logger.info(f"📝 Nombre de archivo: {filename}")

            # 10. Subir a JoyCare
            logger.info(f"⬆️ Subiendo a JoyCare (neonato={neonato_id})...")
            joycare_result = await self.joycare_repo.upload_ecografia(
                neonato_id=neonato_id,
                file_bytes=file_bytes,
                filename=filename,
                uploader_medico_id=uploader_medico_id,
                sede_id=sede_id,
                mime_type="application/dicom"
            )
            logger.info(f"✅ Subido a JoyCare: id={joycare_result.get('id')}")

            # 11. Retornar resultado completo
            result = {
                "status": "success",
                "message": "Imagen transferida exitosamente de DICOMweb a JoyCare",
                "study_uid": study_uid,
                "series_uid": series_uid,
                "instance_uid": instance_uid,
                "filename": filename,
                "file_size_bytes": file_size,
                "modality": modality,
                "is_etf": is_etf_final,
                "etf_analysis": { 
                    "by_description": is_etf_by_description,
                    "by_dicom_tags": is_etf_by_dicom,
                    "confidence": etf_confidence,
                    "criteria": etf_criteria,
                    "patient_age": etf_analysis.get("patient_age", "desconocida"),
                    "is_neonatal": etf_analysis.get("is_neonatal_age", False)
                },
                "dicom_validation": {  # NUEVO: Detalles de validación
                    "is_valid": validation_result.get("is_valid", True),
                    "errors": validation_result.get("errors", []),
                    "has_pixels": validation_result.get("has_pixels", False),
                    "pixel_info": pixel_info if pixel_info.get("has_pixels") else None
                },
                "patient_name": patient_name,
                "patient_id": validation_patient_id,
                "series_description": series_description,
                "sop_class_uid": sop_class_uid,
                "critical_tags_extracted": len(critical_tags),
                "joycare_response": joycare_result,
                "timestamp": self._get_timestamp()
            }
            
            logger.info(f"🎉 Transferencia completada: {filename}")
            return result
            
        except ValueError as e:
            logger.error(f"❌ Validación fallida: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Error en transferencia de instancia: {str(e)}")
            raise

    # ============================
    # TRANSFERENCIA: SERIE COMPLETA
    # ============================

    async def transfer_series(
        self,
        study_uid: str,
        series_uid: str,
        neonato_id: int,
        uploader_medico_id: int,
        sede_id: Optional[int] = None,
        only_etf: bool = False
    ) -> dict:
        """
        Transferir TODAS las instancias de una serie desde DICOMweb a JoyCare.
        
        MEJORADO: Análisis robusto de ETF con PyDICOMHandler en cada instancia.
        """
        logger.info(
            f"⬇️ Iniciando transferencia de serie completa: {series_uid}"
        )

        try:
            # ============================================================
            # 1.  Clasificar serie por modalidad y ETF (análisis inicial)
            # ============================================================
            logger.info(f"🔍 Verificando serie: modalidad y ETF...")
            series_data = await self.dicomweb_service.dicomweb_repo.get_series_by_uid(
                study_uid, series_uid
            )
            series_description = series_data.get("SeriesDescription", "")
            modality = series_data.get("Modality", "UNKNOWN")
            
            # Verificar modalidad
            if modality != "US":
                logger.warning(
                    f"⚠️ Modalidad {modality} no es ultrasound. "
                    f"Se esperaba US (Ultrasound), pero continuaremos"
                )
            else:
                logger.info(f"✅ Modalidad confirmada: US (Ultrasound)")
            
            # ============================================================
            # 2. Pre-análisis ETF a nivel de serie
            # ============================================================
            # Verificar ETF si está habilitado el filtro
            series_etf_description = False
            if only_etf:
                logger.info(f"🧠 Analizando si la serie es ETF (pre-check)...")
                series_etf_description = await self.dicomweb_service.is_transfontanelar_echography(
                    study_uid, series_uid, series_description
                )
                
                if series_etf_description:
                    logger.info(f"🧠 ✅ Serie probablemente es ETF (por descripción)")
                else:
                    logger.warning(
                        f"⚠️ Serie no parece ser ETF en descripción: '{series_description}'. "
                        f"Continuamos - validaremos en cada instancia"
                    )
            else:
                logger.info(f"ℹ️ Filtro ETF deshabilitado, procesando todas las instancias")

            # ============================================================
            # 3. Obtener todas las instancias de la serie
            # ============================================================
            logger.info(f"📋 Obteniendo instancias de la serie...")
            instances = await self.dicomweb_service.get_series_instances(
                study_uid, series_uid
            )
            logger.info(f"📊 Encontradas {len(instances)} instancias")

            if len(instances) == 0:
                logger.warning(f"⚠️ Serie no tiene instancias")
                return {
                    "status": "completed",
                    "series_uid": series_uid,
                    "study_uid": study_uid,
                    "total_instances": 0,
                    "transferred": 0,
                    "failed": 0,
                    "success_rate": "N/A",
                    "results": [],
                    "errors": [{"reason": "Serie vacía"}],
                    "timestamp": self._get_timestamp()
                }

            # ============================================================
            # 4. Estadísticas de la serie (antes de transferir)
            # ============================================================
            series_stats = {
                "total_instancias": len(instances),
                "etf_por_descripcion": series_etf_description,
                "modalidad": modality,
                "descripcion": series_description,
                "etf_confirmadas_por_dicom": 0,
                "dicom_validos": 0,
                "dicom_invalidos": 0,
                "errores_descarga": 0
            }

            # ============================================================
            # 5. Transferir cada instancia (CON ANÁLISIS MEJORADO)
            # ============================================================
            results = []
            errors = []

            for idx, instance in enumerate(instances, 1):
                instance_uid = self._get_value(instance, "sop_instance_uid", "SOPInstanceUID")
                instance_number = self._get_value(instance, "instance_number", "InstanceNumber", default=str(idx))

                if not instance_uid:
                    raise ValueError(f"Instancia sin SOPInstanceUID en índice {idx}")
                
                logger.info(
                    f"📦 Procesando instancia {idx}/{len(instances)}: {instance_uid}"
                )
                
                try:

                    result = await self.transfer_instance(
                        study_uid=study_uid,
                        series_uid=series_uid,
                        instance_uid=instance_uid,
                        neonato_id=neonato_id,
                        uploader_medico_id=uploader_medico_id,
                        sede_id=sede_id
                    )
                    
                    results.append(result)
                    
                    # ============================================================
                    # 5c. Actualizar estadísticas de la serie
                    # ============================================================
                    if result.get("status") == "success":
                        logger.info(f"✅ Instancia {idx} transferida")
                        
                        # Contar validaciones
                        if result.get("dicom_validation", {}).get("is_valid"):
                            series_stats["dicom_validos"] += 1
                        else:
                            series_stats["dicom_invalidos"] += 1
                        
                        # Contar ETF detectadas
                        if result.get("etf_analysis", {}).get("by_dicom_tags"):
                            series_stats["etf_confirmadas_por_dicom"] += 1
                    
                except Exception as e:
                    error_detail = {
                        "instance_uid": instance_uid,
                        "instance_number": instance_number,
                        "error": str(e),
                        "tipo_error": type(e).__name__
                    }
                    errors.append(error_detail)
                    
                    # Clasificar tipo de error
                    if "descarga" in str(e).lower() or "connection" in str(e).lower():
                        series_stats["errores_descarga"] += 1
                    
                    logger.error(
                        f"❌ Error en instancia {idx} ({instance_uid}): {str(e)}"
                    )

            # ============================================================
            # 6. Análisis final de la serie
            # ============================================================
            logger.info(f"📊 Analizando resultados de la serie...")
            
            # ¿La serie contiene ETF?
            series_contiene_etf = (
                series_etf_description or
                series_stats["etf_confirmadas_por_dicom"] > 0
            )
            
            # Tasa de validación DICOM
            tasa_dicom_validos = (
                series_stats["dicom_validos"] / len(results) * 100
            ) if len(results) > 0 else 0
            
            logger.info(
                f"📊 Estadísticas de serie: "
                f"transferidas={len(results)}, "
                f"DICOM válidos={series_stats['dicom_validos']}, "
                f"ETF detectadas={series_stats['etf_confirmadas_por_dicom']}"
            )

            # ============================================================
            # 7. Construir respuesta mejorada
            # ============================================================
            summary = {
                "status": "completed",
                "series_uid": series_uid,
                "study_uid": study_uid,
                "series_description": series_description,
                "modality": modality,
                "total_instances": len(instances),
                "transferred": len(results),
                "failed": len(errors),
                "success_rate": f"{(len(results)/len(instances)*100):.1f}%" if instances else "N/A",
                
                # Análisis ETF de la serie
                "etf_analysis": {
                    "serie_contiene_etf": series_contiene_etf,
                    "etf_por_descripcion": series_etf_description,
                    "etf_confirmadas_por_dicom": series_stats["etf_confirmadas_por_dicom"],
                    "porcentaje_etf": (
                        (series_stats["etf_confirmadas_por_dicom"] / len(results) * 100)
                        if len(results) > 0 else 0
                    )
                },
                
                # Estadísticas DICOM
                "dicom_stats": {
                    "dicom_validos": series_stats["dicom_validos"],
                    "dicom_invalidos": series_stats["dicom_invalidos"],
                    "tasa_validacion": f"{tasa_dicom_validos:.1f}%",
                    "errores_descarga": series_stats["errores_descarga"]
                },
                
                "results": results,
                "errors": errors,
                "timestamp": self._get_timestamp()
            }

            if errors:
                logger.warning(
                    f"⚠️ Transferencia de serie completada con {len(errors)} errores"
                )
            else:
                logger.info(f"🎉 Transferencia de serie completada exitosamente")

            return summary
            
        except Exception as e:
            logger.error(f"❌ Error fatal en transferencia de serie: {str(e)}")
            raise

    # ============================
    # TRANSFERENCIA: ESTUDIO COMPLETO
    # ============================

    async def transfer_study(
        self,
        study_uid: str,
        neonato_id: int,
        uploader_medico_id: int,
        sede_id: Optional[int] = None,
        only_etf: bool = False,
        only_ultrasound: bool = True
    ) -> dict:
        """
        Transferir TODAS las series de un estudio desde DICOMweb a JoyCare.

        MEJORADO: Análisis robusto con estadísticas DICOM y detección ETF.
        """
        logger.info(
            f"🔄 Iniciando transferencia de estudio completo: {study_uid}"
        )

        try:
            # ============================================================
            # 1. Obtener detalle del estudio
            # ============================================================
            logger.info("📊 Obteniendo series del estudio...")
            series_list = await self.dicomweb_service.dicomweb_repo.get_series_by_study_uid(study_uid)
            logger.info(f"📋 Estudio tiene {len(series_list)} series")

            # ============================================================
            # 2. Clasificar y reportar series por modalidad (detallado)
            # ============================================================
            logger.info(f"📊 Clasificando series por modalidad...")
            
            us_series = []
            non_us_series = []
            series_classification = {
                "US": [],
                "CT": [],
                "MR": [],
                "OTHER": []
            }
            
            for series in series_list:
                modality = self._get_value(series, "modality", "Modality", default="UNKNOWN")
                description = self._get_value(series, "series_description", "SeriesDescription", default="")
                series_uid = self._get_value(series, "series_instance_uid", "SeriesInstanceUID")
                
                # Clasificar por modalidad
                if modality == "US":
                    us_series.append(series)
                    series_classification["US"].append({
                        "uid": series_uid,
                        "description": description
                    })
                    logger.info(f"✅ Serie US: {description or series_uid}")
                elif modality == "CT":
                    series_classification["CT"].append({"uid": series_uid, "description": description})
                    logger.info(f"ℹ️ Serie CT: {description or series_uid}")
                elif modality == "MR":
                    series_classification["MR"].append({"uid": series_uid, "description": description})
                    logger.info(f"ℹ️ Serie MR: {description or series_uid}")
                else:
                    non_us_series.append(series)
                    series_classification["OTHER"].append({
                        "uid": series_uid,
                        "description": description,
                        "modality": modality
                    })
                    logger.info(f"ℹ️ Serie {modality}: {description or series_uid}")
            
            logger.info(
                f"📊 Resumen de modalidades: "
                f"US={len(us_series)}, "
                f"CT={len(series_classification['CT'])}, "
                f"MR={len(series_classification['MR'])}, "
                f"OTHER={len(series_classification['OTHER'])}"
            )

            # ============================================================
            # 3. NUEVO: Estadísticas globales del estudio
            # ============================================================
            study_stats = {
                "total_series": len(series_list),
                "series_us": len(us_series),
                "series_procesadas": 0,
                "instancias_totales": 0,
                "instancias_transferidas": 0,
                "instancias_fallidas": 0,
                "etf_series_detectadas": 0,
                "dicom_validos": 0,
                "dicom_invalidos": 0,
                "errores_por_tipo": {}
            }

            # ============================================================
            # 4. Determinar qué series procesar
            # ============================================================
            series_to_process = us_series if only_ultrasound else series_list
            
            # Si only_ultrasound, podemos informar pero procesar todo
            if only_ultrasound and len(non_us_series) > 0:
                logger.info(
                    f"⚠️ Parámetro only_ultrasound=True, pero procesaremos TODAS las {len(series_list)} series"
                )

            # ============================================================
            # 5. Transferir cada serie
            # ============================================================
            results = []
            errors = []

            for idx, series in enumerate(series_to_process, 1):
                series_uid = self._get_value(series, "series_instance_uid", "SeriesInstanceUID")
                modality = self._get_value(series, "modality", "Modality", default="UNKNOWN")
                description = self._get_value(series, "series_description", "SeriesDescription", default="")

                if not series_uid:
                    errors.append({
                        "series_uid": None,
                        "series_description": description,
                        "modality": modality,
                        "error": "Serie sin SeriesInstanceUID",
                        "tipo_error": "ValidationError"
                    })
                    continue
                try:
                    # ============================================================
                    # 5a. Transferir serie (usa transfer_series mejorado)
                    # ============================================================
                    result = await self.transfer_series(
                        study_uid=study_uid,
                        series_uid=series_uid,
                        neonato_id=neonato_id,
                        uploader_medico_id=uploader_medico_id,
                        sede_id=sede_id,
                        only_etf=False
                    )
                    
                    results.append(result)
                    
                    # ============================================================
                    # 5b. Actualizar estadísticas globales
                    # ============================================================
                    if result.get("status") == "completed":
                        logger.info(f"✅ Serie {idx} procesada")
                        
                        # Contar instancias
                        study_stats["series_procesadas"] += 1
                        study_stats["instancias_totales"] += result.get("total_instances", 0)
                        study_stats["instancias_transferidas"] += result.get("transferred", 0)
                        study_stats["instancias_fallidas"] += result.get("failed", 0)
                        
                        # Contar ETF
                        if result.get("etf_analysis", {}).get("serie_contiene_etf"):
                            study_stats["etf_series_detectadas"] += 1
                        
                        # Contar DICOM válidos/inválidos
                        study_stats["dicom_validos"] += result.get("dicom_stats", {}).get("dicom_validos", 0)
                        study_stats["dicom_invalidos"] += result.get("dicom_stats", {}).get("dicom_invalidos", 0)
                    
                except Exception as e:
                    error_detail = {
                        "series_uid": series_uid,
                        "series_description": description,
                        "modality": modality,
                        "error": str(e),
                        "tipo_error": type(e).__name__
                    }
                    errors.append(error_detail)
                    
                    # Contar por tipo de error
                    error_type = type(e).__name__
                    study_stats["errores_por_tipo"][error_type] = (
                        study_stats["errores_por_tipo"].get(error_type, 0) + 1
                    )
                    
                    logger.error(f"❌ Error en serie {idx}: {str(e)}")

            # ============================================================
            # 6. Análisis final del estudio
            # ============================================================
            logger.info(f"📊 Analizando resultados del estudio...")
            
            # Tasa de éxito global
            tasa_exito_global = (
                (study_stats["instancias_transferidas"] / study_stats["instancias_totales"] * 100)
                if study_stats["instancias_totales"] > 0 else 0
            )
            
            # Porcentaje de series ETF
            porcentaje_etf_series = (
                (study_stats["etf_series_detectadas"] / study_stats["series_procesadas"] * 100)
                if study_stats["series_procesadas"] > 0 else 0
            )
            
            logger.info(
                f"📊 Resumen del estudio: "
                f"series={study_stats['series_procesadas']}, "
                f"instancias transferidas={study_stats['instancias_transferidas']}, "
                f"ETF detectadas={study_stats['etf_series_detectadas']}, "
                f"tasa éxito={tasa_exito_global:.1f}%"
            )

            # ============================================================
            # 7. Construir respuesta mejorada
            # ============================================================
            summary = {
                "status": "completed",
                "study_uid": study_uid,
                
                # Resumen básico
                "series_count": len(series_list),
                "series_procesadas": study_stats["series_procesadas"],
                "total_instances_transferred": study_stats["instancias_transferidas"],
                "total_instances_failed": study_stats["instancias_fallidas"],
                "total_errors": len(errors),
                
                # Tasa de éxito global
                "success_rate": f"{tasa_exito_global:.1f}%",
                
                # Análisis de modalidades
                "modality_analysis": {
                    "us_series": study_stats["series_us"],
                    "total_series": study_stats["total_series"],
                    "classification": series_classification
                },
                
                # Análisis ETF del estudio
                "etf_analysis": {
                    "series_con_etf": study_stats["etf_series_detectadas"],
                    "porcentaje_series_etf": f"{porcentaje_etf_series:.1f}%",
                    "estudio_contiene_etf": study_stats["etf_series_detectadas"] > 0
                },
                
                # Estadísticas DICOM
                "dicom_stats": {
                    "dicom_validos": study_stats["dicom_validos"],
                    "dicom_invalidos": study_stats["dicom_invalidos"],
                    "tasa_validacion_dicom": (
                        (study_stats["dicom_validos"] / (study_stats["dicom_validos"] + study_stats["dicom_invalidos"]) * 100)
                        if (study_stats["dicom_validos"] + study_stats["dicom_invalidos"]) > 0
                        else 0
                    ),
                    "errores_por_tipo": study_stats["errores_por_tipo"]
                },
                
                "series_results": results,
                "series_errors": errors,
                "timestamp": self._get_timestamp()
            }

            if len(errors) > 0:
                logger.warning(
                    f"⚠️ Transferencia de estudio completada con {len(errors)} errores"
                )
            else:
                logger.info(f"🎉 Transferencia de estudio completada exitosamente")

            return summary
            
        except Exception as e:
            logger.error(f"❌ Error fatal en transferencia de estudio: {str(e)}")
            raise

    # ============================
    # UTILIDADES PRIVADAS
    # ============================

    def _build_filename(
        self,
        patient_name: str,
        modality: str,
        instance_number: str,
        study_uid: str
    ) -> str:
        """
        Construir un nombre de archivo descriptivo y único.
        
        Formato: {patient_name}_{modality}_{instance_number}_{timestamp}.dcm
        
        Args:
            patient_name: Nombre del paciente
            modality: Modalidad DICOM (ej: "US")
            instance_number: Número de instancia
            study_uid: StudyInstanceUID (para garantizar unicidad)
        
        Returns:
            Nombre de archivo limpio y válido
        """
        # Extraer últimos 8 caracteres del UID para unicidad
        uid_suffix = study_uid[-8:] if len(study_uid) >= 8 else study_uid
        
        # Construir nombre
        filename = f"{patient_name}_{modality}_{instance_number}_{uid_suffix}.dcm"
        
        # Limpiar caracteres no válidos para nombres de archivo
        import re
        filename = re.sub(r'[^\w\s._-]', '_', filename)
        filename = re.sub(r'[\s]+', '_', filename)
        
        return filename[:255]  # Límite de 255 caracteres

    def _get_timestamp(self) -> str:
        """Obtener timestamp actual en formato ISO."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"