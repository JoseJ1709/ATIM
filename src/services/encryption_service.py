import os
import base64
import logging
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

from src.config.settings import get_settings

logger = logging.getLogger("atim")


class EncryptionService:
    """
    Servicio de cifrado AES-256-CBC para imágenes DICOM.

    Cifra los archivos DICOM antes de transmitirlos (doble capa de seguridad):
    - Capa 1: Cifrado AES-256 a nivel de payload
    - Capa 2: TLS en tránsito (manejado por infraestructura)

    Formato del payload cifrado:
    [IV (16 bytes)] + [datos cifrados con AES-256-CBC + PKCS7 padding]
    """

    def __init__(self):
        settings = get_settings()
        key = settings.aes_encryption_key.encode("utf-8")

        # Asegurar que la key sea exactamente 32 bytes (AES-256)
        if len(key) < 32:
            key = key.ljust(32, b"\0")
        elif len(key) > 32:
            key = key[:32]

        self.key = key
        logger.info("EncryptionService inicializado con AES-256-CBC")

    def encrypt(self, data: bytes) -> bytes:
        """
        Cifrar datos con AES-256-CBC.

        Args:
            data: Bytes del archivo DICOM sin cifrar

        Returns:
            Bytes cifrados con formato: IV (16 bytes) + ciphertext
        """
        # Generar IV aleatorio de 16 bytes
        iv = os.urandom(16)

        # Aplicar padding PKCS7 (necesario para CBC)
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()

        # Cifrar con AES-256-CBC
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        # Prepend IV al ciphertext
        result = iv + ciphertext

        logger.info(
            f"Cifrado AES-256: {len(data)} bytes -> {len(result)} bytes "
            f"(overhead: {len(result) - len(data)} bytes)"
        )

        return result

    def decrypt(self, encrypted_data: bytes) -> bytes:
        """
        Descifrar datos con AES-256-CBC.

        Args:
            encrypted_data: Bytes cifrados con formato: IV (16 bytes) + ciphertext

        Returns:
            Bytes del archivo DICOM original
        """
        if len(encrypted_data) < 32:
            raise ValueError("Datos cifrados demasiado cortos (mínimo 32 bytes)")

        # Extraer IV (primeros 16 bytes)
        iv = encrypted_data[:16]
        ciphertext = encrypted_data[16:]

        # Descifrar con AES-256-CBC
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()

        # Quitar padding PKCS7
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()

        logger.info(f"Descifrado AES-256: {len(encrypted_data)} bytes -> {len(data)} bytes")

        return data

    def encrypt_to_base64(self, data: bytes) -> str:
        """Cifrar y codificar en base64 (útil para JSON)."""
        encrypted = self.encrypt(data)
        return base64.b64encode(encrypted).decode("utf-8")

    def decrypt_from_base64(self, b64_data: str) -> bytes:
        """Decodificar base64 y descifrar."""
        encrypted = base64.b64decode(b64_data)
        return self.decrypt(encrypted)