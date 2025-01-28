import os
import secrets
import base64
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from pilott.errors.keys import KeyManagementError


class KeyManager:
    """Manages secure key generation and storage for the prompt system"""

    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir) if config_dir else Path.home() / '.pilott'
        self.config_file = self.config_dir / 'prompt_security.json'
        self.key_file = self.config_dir / '.prompt_keys'

    def generate_new_keys(self) -> Tuple[str, str]:
        """Generate new salt and key"""
        # Generate cryptographically secure salt and key
        salt = base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
        key = base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
        return salt, key

    def setup_secure_environment(self) -> Dict[str, str]:
        """Setup secure environment for prompt system"""
        try:
            # Create config directory if it doesn't exist
            self.config_dir.mkdir(parents=True, exist_ok=True)

            # Generate keys if they don't exist
            if not self.key_file.exists():
                salt, key = self.generate_new_keys()

                # Store keys securely
                keys_data = {
                    'salt': salt,
                    'key': key,
                    'created_at': str(datetime.now()),
                    'version': '1.0'
                }

                # Encrypt keys before storing
                cipher = self._create_file_cipher()
                encrypted_data = cipher.encrypt(json.dumps(keys_data).encode())
                self.key_file.write_bytes(encrypted_data)

                # Create public config file
                config_data = {
                    'version': '1.0',
                    'key_file': str(self.key_file),
                    'last_updated': str(datetime.now())
                }
                self.config_file.write_text(json.dumps(config_data, indent=2))

                return {
                    'PROMPT_SALT': salt,
                    'PROMPT_KEY': key
                }
            else:
                return self.load_keys()

        except Exception as e:
            raise KeyManagementError(f"Failed to setup secure environment: {str(e)}")

    def load_keys(self) -> Dict[str, str]:
        """Load existing keys"""
        try:
            if not self.key_file.exists():
                raise KeyManagementError("No existing keys found")

            cipher = self._create_file_cipher()
            encrypted_data = self.key_file.read_bytes()
            decrypted_data = cipher.decrypt(encrypted_data)
            keys_data = json.loads(decrypted_data)

            return {
                'PROMPT_SALT': keys_data['salt'],
                'PROMPT_KEY': keys_data['key']
            }

        except Exception as e:
            raise KeyManagementError(f"Failed to load keys: {str(e)}")

    def rotate_keys(self) -> Dict[str, str]:
        """Rotate existing keys"""
        try:
            # Generate new keys
            new_salt, new_key = self.generate_new_keys()

            # Load existing data
            existing_keys = self.load_keys()

            # Store new keys
            keys_data = {
                'salt': new_salt,
                'key': new_key,
                'previous_salt': existing_keys['PROMPT_SALT'],
                'previous_key': existing_keys['PROMPT_KEY'],
                'rotated_at': str(datetime.now()),
                'version': '1.1'
            }

            # Encrypt and store new keys
            cipher = self._create_file_cipher()
            encrypted_data = cipher.encrypt(json.dumps(keys_data).encode())
            self.key_file.write_bytes(encrypted_data)

            # Update config file
            config_data = json.loads(self.config_file.read_text())
            config_data.update({
                'last_rotated': str(datetime.now()),
                'version': '1.1'
            })
            self.config_file.write_text(json.dumps(config_data, indent=2))

            return {
                'PROMPT_SALT': new_salt,
                'PROMPT_KEY': new_key
            }

        except Exception as e:
            raise KeyManagementError(f"Failed to rotate keys: {str(e)}")

    def _create_file_cipher(self) -> Fernet:
        """Create cipher for file encryption"""
        # Use system-specific values to create a deterministic key
        system_salt = self._get_system_specific_salt()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=system_salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(system_salt))
        return Fernet(key)

    def _get_system_specific_salt(self) -> bytes:
        """Get system-specific salt for file encryption"""
        # Use system-specific values that are relatively stable
        system_info = f"{os.getlogin()}:{os.name}:{Path.home()}"
        return hashlib.sha256(system_info.encode()).digest()

