"""
Encryption Service for Data Protection
Handles encryption/decryption of sensitive data at rest and in transit
"""

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


class EncryptionService:
    """Service for encrypting/decrypting sensitive data"""

    def __init__(self):
        self._fernet: Optional[Fernet] = None
        self._master_key: Optional[bytes] = None
        self._salt = b"envoyou_sec_salt_2024"  # Should be configurable in production

        # Initialize encryption keys
        self._initialize_keys()

    def _initialize_keys(self):
        """Initialize encryption keys from environment or generate them"""
        try:
            # Get master key from environment or generate one
            master_key_env = getattr(settings, "ENCRYPTION_MASTER_KEY", None)

            if master_key_env:
                # Use provided key
                self._master_key = base64.urlsafe_b64decode(master_key_env)
            else:
                # Generate key from application secret (development only)
                # In production, this should be a proper key from secure storage
                key_material = settings.SECRET_KEY.encode()
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=self._salt,
                    iterations=100000,
                    backend=default_backend(),
                )
                self._master_key = base64.urlsafe_b64encode(kdf.derive(key_material))

            self._fernet = Fernet(self._master_key)
            logger.info("Encryption service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize encryption service: {str(e)}")
            # In development, allow service to continue without encryption
            if settings.ENVIRONMENT == "development":
                logger.warning("Running in development mode without encryption")
                self._fernet = None
            else:
                raise

    def encrypt_data(self, data: Any, key_id: Optional[str] = None) -> str:
        """
        Encrypt data using Fernet symmetric encryption

        Args:
            data: Data to encrypt (will be JSON serialized)
            key_id: Optional key identifier for key rotation

        Returns:
            Base64 encoded encrypted data
        """
        if not self._fernet:
            # In development, return data as-is with marker
            if settings.ENVIRONMENT == "development":
                return f"DEV_UNENCRYPTED:{json.dumps(data)}"
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Encryption service not available",
            )

        try:
            # Prepare data for encryption
            if isinstance(data, (dict, list)):
                data_str = json.dumps(data, default=str)
            else:
                data_str = str(data)

            # Create encrypted payload with metadata
            payload = {
                "data": data_str,
                "encrypted_at": datetime.utcnow().isoformat(),
                "key_id": key_id or "default",
                "version": "1.0",
            }

            payload_json = json.dumps(payload)

            # Encrypt
            encrypted_bytes = self._fernet.encrypt(payload_json.encode())
            encrypted_b64 = base64.urlsafe_b64encode(encrypted_bytes).decode()

            return encrypted_b64

        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Data encryption failed",
            )

    def decrypt_data(self, encrypted_data: str) -> Any:
        """
        Decrypt data using Fernet symmetric encryption

        Args:
            encrypted_data: Base64 encoded encrypted data

        Returns:
            Decrypted data
        """
        if not self._fernet:
            # In development, handle unencrypted data
            if settings.ENVIRONMENT == "development" and encrypted_data.startswith(
                "DEV_UNENCRYPTED:"
            ):
                data_str = encrypted_data[16:]  # Remove DEV_UNENCRYPTED: prefix
                return json.loads(data_str)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Encryption service not available",
            )

        try:
            # Decode from base64
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data)

            # Decrypt
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            payload_json = decrypted_bytes.decode()

            # Parse payload
            payload = json.loads(payload_json)

            # Extract original data
            data_str = payload["data"]

            # Try to parse as JSON first, then fallback to string
            try:
                return json.loads(data_str)
            except json.JSONDecodeError:
                return data_str

        except InvalidToken:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid encrypted data or decryption key",
            )
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Data decryption failed",
            )

    def hash_sensitive_data(self, data: str, salt: Optional[str] = None) -> str:
        """
        Create a secure hash of sensitive data (one-way)

        Args:
            data: Data to hash
            salt: Optional salt (will generate if not provided)

        Returns:
            Hexadecimal hash string
        """
        if salt is None:
            salt = base64.b64encode(self._salt).decode()[:16]

        # Create salted hash
        salted_data = f"{salt}:{data}"
        hash_obj = hashlib.sha256(salted_data.encode())

        # Add key stretching
        for _ in range(1000):
            hash_obj = hashlib.sha256(hash_obj.digest())

        return hash_obj.hexdigest()

    def verify_data_integrity(self, data: Any, expected_hash: str) -> bool:
        """
        Verify data integrity using hash comparison

        Args:
            data: Data to verify
            expected_hash: Expected hash value

        Returns:
            True if data matches hash
        """
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, sort_keys=True, default=str)
        else:
            data_str = str(data)

        computed_hash = self.hash_sensitive_data(data_str)
        return hmac.compare_digest(computed_hash, expected_hash)

    def create_data_signature(self, data: Any, key: Optional[str] = None) -> str:
        """
        Create HMAC signature for data integrity verification

        Args:
            data: Data to sign
            key: Optional signing key (uses master key if not provided)

        Returns:
            Base64 encoded signature
        """
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, sort_keys=True, default=str)
        else:
            data_str = str(data)

        signing_key = key or self._master_key.decode()
        signature = hmac.new(
            signing_key.encode(), data_str.encode(), hashlib.sha256
        ).digest()

        return base64.urlsafe_b64encode(signature).decode()

    def verify_data_signature(
        self, data: Any, signature: str, key: Optional[str] = None
    ) -> bool:
        """
        Verify HMAC signature for data integrity

        Args:
            data: Data to verify
            signature: Base64 encoded signature
            key: Optional verification key

        Returns:
            True if signature is valid
        """
        expected_signature = self.create_data_signature(data, key)

        try:
            return hmac.compare_digest(expected_signature, signature)
        except Exception:
            return False

    def rotate_encryption_key(self, new_key: Optional[str] = None) -> bool:
        """
        Rotate encryption keys (for key rotation security)

        Args:
            new_key: New encryption key (base64 encoded)

        Returns:
            True if rotation successful
        """
        try:
            if new_key:
                self._master_key = base64.urlsafe_b64decode(new_key)
            else:
                # Generate new key (simplified - should use proper key management)
                import secrets

                self._master_key = base64.urlsafe_b64encode(secrets.token_bytes(32))

            self._fernet = Fernet(self._master_key)
            logger.info("Encryption key rotated successfully")
            return True

        except Exception as e:
            logger.error(f"Key rotation failed: {str(e)}")
            return False

    def get_encryption_status(self) -> Dict[str, Any]:
        """Get encryption service status"""
        return {
            "encryption_enabled": self._fernet is not None,
            "environment": settings.ENVIRONMENT,
            "key_rotation_supported": True,
            "supported_algorithms": ["Fernet", "SHA256", "HMAC-SHA256"],
            "master_key_configured": bool(
                getattr(settings, "ENCRYPTION_MASTER_KEY", None)
            ),
        }


# Global encryption service instance
encryption_service = EncryptionService()
