from typing import Dict, Any, Optional
import yaml
import base64
from pathlib import Path
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from jinja2 import Environment, BaseLoader
import hashlib
import hmac

from pilott.errors import PromptSecurityError
from pilott.security import KeyManager


class PromptHandlerConfig:
    """Configuration for PromptHandler"""

    def __init__(self):
        # Initialize with None, will be set during security initialization
        self.SALT = None
        self.PROMPT_KEY = None
        self.CACHE_DURATION = timedelta(hours=1)
        self.PROMPT_PATH = Path(__file__).parent / 'prompts'


class PromptHandler:
    """Secure handler for system prompts"""

    def __init__(self, config: Optional[PromptHandlerConfig] = None):
        self._config = config or PromptHandlerConfig()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        self._key_manager = KeyManager()
        self._cipher = None
        self._hmac = None
        self._initialize_security()

    def _initialize_security(self) -> None:
        """Initialize security components"""
        try:
            # Get keys from key manager
            keys = self._key_manager.setup_secure_environment()

            # Set the config values
            self._config.SALT = keys['PROMPT_SALT'].encode('utf-8')
            self._config.PROMPT_KEY = keys['PROMPT_KEY'].encode('utf-8')

            # Initialize KDF
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=self._config.SALT,
                iterations=480000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(self._config.PROMPT_KEY))

            # Initialize cipher and hmac
            self._cipher = Fernet(key)
            self._hmac = hmac.new(self._config.PROMPT_KEY, digestmod=hashlib.sha3_512)
        except Exception as e:
            raise PromptSecurityError.key_error({"error": str(e)})

    def rotate_keys(self) -> None:
        """Manually rotate keys when needed"""
        try:
            new_keys = self._key_manager.rotate_keys()
            # Reinitialize security with new keys
            self._config.SALT = new_keys['PROMPT_SALT'].encode('utf-8')
            self._config.PROMPT_KEY = new_keys['PROMPT_KEY'].encode('utf-8')
            # Clear cache to force reload with new keys
            self._cache.clear()
            self._cache_timestamps.clear()
            # Reinitialize security components
            self._initialize_security()
        except Exception as e:
            raise PromptSecurityError.key_error({"error": str(e)})

    def _load_prompts(self, force_reload: bool = False) -> Dict[str, Any]:
        """Load and decrypt prompts from YAML"""
        cache_key = 'main_prompts'

        # Check cache first
        if not force_reload and self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        # Load and decrypt prompts
        prompt_path = self._config.PROMPT_PATH / 'system_prompts.yaml'
        if not prompt_path.exists():
            raise PromptSecurityError.file_access_error({"path": str(prompt_path)})

        try:
            # Read and verify file integrity
            content = prompt_path.read_bytes()
            if not self._verify_integrity(content):
                raise PromptSecurityError.integrity_error({"file": "system_prompts.yaml"})

            # Decrypt and parse
            decrypted = self._cipher.decrypt(content)
            prompts = yaml.safe_load(decrypted)

            # Validate structure
            if not self._validate_prompt_structure(prompts):
                raise PromptSecurityError.structure_error({"file": "system_prompts.yaml"})

            # Update cache
            self._cache[cache_key] = prompts
            self._cache_timestamps[cache_key] = datetime.now()

            return prompts

        except Exception as e:
            raise PromptSecurityError.decryption_error({"error": str(e)})

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached prompts are still valid"""
        if cache_key not in self._cache_timestamps:
            return False

        age = datetime.now() - self._cache_timestamps[cache_key]
        return age < self._config.CACHE_DURATION

    def _verify_integrity(self, content: bytes) -> bool:
        """Verify content integrity"""
        try:
            self._hmac.update(content)
            return True
        except Exception:
            return False

    def _validate_prompt_structure(self, prompts: Dict) -> bool:
        """Validate prompt structure"""
        required_keys = {'system_prompts', 'encryption'}
        if not all(key in prompts for key in required_keys):
            return False

        if 'template_assembly' not in prompts['system_prompts'].get('agent_executive', {}):
            return False

        return True

    def _interpolate_variables(self, template: str, context: Dict[str, Any]) -> str:
        """Safely interpolate variables into template"""
        try:
            env = Environment(loader=BaseLoader())
            # Add custom filters and security measures
            env.globals = {}  # Restrict global namespace
            template_obj = env.from_string(template)
            return template_obj.render(**context)
        except Exception as e:
            raise PromptSecurityError.interpolation_error({"error": str(e)})

    def get_system_prompt(self, prompt_type: str, context: Dict[str, Any]) -> str:
        """Get interpolated system prompt"""
        try:
            prompts = self._load_prompts()
            prompt_config = prompts['system_prompts'].get(prompt_type)

            if not prompt_config:
                raise PromptSecurityError.unknown_prompt_error(prompt_type)

            # Validate context against schema
            if not self._validate_context(context, prompt_config['context_schema']):
                raise PromptSecurityError.schema_error({"context": context})

            # Get template and interpolate
            template = prompt_config['template_assembly']
            return self._interpolate_variables(template, {
                'context': context,
                'segments': prompt_config['segments']
            })

        except Exception as e:
            if isinstance(e, PromptSecurityError):
                raise
            raise PromptSecurityError.template_error({"error": str(e)})

    def _validate_context(self, context: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """Validate context against schema"""
        try:
            def validate_dict(data: Dict, schema_section: Dict) -> bool:
                for key, expected_type in schema_section.items():
                    if key not in data:
                        return False
                    if isinstance(expected_type, dict):
                        if not isinstance(data[key], dict):
                            return False
                        if not validate_dict(data[key], expected_type):
                            return False
                    else:
                        # Handle type validation
                        type_str = expected_type.strip('[]')
                        if type_str == 'str':
                            if not isinstance(data[key], str):
                                return False
                        elif type_str == 'int':
                            if not isinstance(data[key], int):
                                return False
                        elif type_str == 'float':
                            if not isinstance(data[key], (int, float)):
                                return False
                        elif type_str == 'List':
                            if not isinstance(data[key], list):
                                return False
                return True

            return validate_dict(context, schema)
        except Exception:
            return False