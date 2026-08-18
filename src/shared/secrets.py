"""
Secrets management for production security.
Supports multiple backends: environment variables, AWS Secrets Manager, HashiCorp Vault.
"""
import os
import json
from typing import Optional, Dict, Any
from enum import Enum


class SecretsBackend(Enum):
    ENV = "env"
    AWS_SECRETS_MANAGER = "aws"
    HASHICORP_VAULT = "vault"


class SecretsManager:
    """
    Centralized secrets management.
    Falls back to environment variables if cloud services unavailable.
    """

    def __init__(self, backend: SecretsBackend = SecretsBackend.ENV):
        self.backend = backend
        self._cache: Dict[str, Any] = {}

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Retrieve secret from configured backend.

        Args:
            key: Secret key name
            default: Default value if secret not found

        Returns:
            Secret value or default
        """
        # Check cache first
        if key in self._cache:
            return self._cache[key]

        if self.backend == SecretsBackend.ENV:
            value = os.getenv(key, default)
        elif self.backend == SecretsBackend.AWS_SECRETS_MANAGER:
            value = self._get_from_aws(key, default)
        elif self.backend == SecretsBackend.HASHICORP_VAULT:
            value = self._get_from_vault(key, default)
        else:
            value = default

        # Cache the value
        if value is not None:
            self._cache[key] = value

        return value

    def _get_from_aws(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve secret from AWS Secrets Manager."""
        try:
            import boto3
            from botocore.exceptions import ClientError

            secret_name = os.getenv("AWS_SECRET_NAME", "sweetsnipe/production")
            region_name = os.getenv("AWS_REGION", "us-east-1")

            session = boto3.session.Session()
            client = session.client(
                service_name='secretsmanager',
                region_name=region_name
            )

            try:
                get_secret_value_response = client.get_secret_value(SecretId=secret_name)
            except ClientError as e:
                # Fall back to environment variable
                return os.getenv(key, default)

            # Parse the secret
            if 'SecretString' in get_secret_value_response:
                secret = get_secret_value_response['SecretString']
                secrets_dict = json.loads(secret)
                return secrets_dict.get(key, default)
            else:
                return default

        except ImportError:
            # boto3 not installed, fall back to env vars
            return os.getenv(key, default)

    def _get_from_vault(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve secret from HashiCorp Vault."""
        try:
            import hvac

            vault_url = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
            vault_token = os.getenv("VAULT_TOKEN")
            vault_path = os.getenv("VAULT_SECRET_PATH", "secret/data/sweetsnipe")

            if not vault_token:
                return os.getenv(key, default)

            client = hvac.Client(url=vault_url, token=vault_token)

            if not client.is_authenticated():
                return os.getenv(key, default)

            # Read secret
            secret_response = client.secrets.kv.v2.read_secret_version(path=vault_path)
            secrets_dict = secret_response['data']['data']
            return secrets_dict.get(key, default)

        except ImportError:
            # hvac not installed, fall back to env vars
            return os.getenv(key, default)
        except Exception:
            return os.getenv(key, default)

    def get_treasury_private_key(self) -> str:
        """
        Securely retrieve treasury private key.
        SECURITY: Should never be logged or exposed.
        """
        key = self.get_secret("TREASURY_PRIVATE_KEY")
        if not key:
            raise ValueError("TREASURY_PRIVATE_KEY not configured in secrets backend")
        return key

    def get_encryption_key(self) -> str:
        """Retrieve encryption key for database encryption."""
        key = self.get_secret("ENCRYPTION_KEY")
        if not key:
            raise ValueError("ENCRYPTION_KEY not configured in secrets backend")
        return key

    def get_secret_key(self) -> str:
        """Retrieve secret key for JWT signing."""
        key = self.get_secret("SECRET_KEY")
        if not key:
            raise ValueError("SECRET_KEY not configured in secrets backend")
        return key

    def clear_cache(self):
        """Clear the secrets cache."""
        self._cache.clear()


# Determine backend from environment
backend_type = os.getenv("SECRETS_BACKEND", "env").lower()
if backend_type == "aws":
    secrets_backend = SecretsBackend.AWS_SECRETS_MANAGER
elif backend_type == "vault":
    secrets_backend = SecretsBackend.HASHICORP_VAULT
else:
    secrets_backend = SecretsBackend.ENV

# Global singleton instance
secrets_manager = SecretsManager(backend=secrets_backend)
