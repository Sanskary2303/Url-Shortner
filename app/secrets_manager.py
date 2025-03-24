import hvac
import os
from dotenv import load_dotenv
from .logger import log_error

load_dotenv()

VAULT_URL = os.getenv("VAULT_URL", "http://localhost:8200")
VAULT_TOKEN = os.getenv("VAULT_TOKEN", "")
VAULT_ENABLED = os.getenv("VAULT_ENABLED", "False").lower() in ("true", "1", "t")
VAULT_PATH = "urlshortener/api-keys"

API_KEY_ENV = os.getenv("API_KEY", "")

class SecretsManager:
    def __init__(self):
        self.client = None
        if VAULT_ENABLED:
            try:
                self.client = hvac.Client(url=VAULT_URL, token=VAULT_TOKEN)
                if not self.client.is_authenticated():
                    log_error("Vault client failed to authenticate, falling back to environment variables")
                    self.client = None
            except Exception as e:
                log_error("Failed to initialize Vault client", e)
                self.client = None

    def get_api_key(self, key_name: str = "default") -> str:
        """Get API key from the secrets manager or fallback to environment variable"""
        if not self.client:
            return API_KEY_ENV
            
        try:
            secret_path = f"{VAULT_PATH}/{key_name}"
            secret = self.client.secrets.kv.read_secret_version(path=secret_path)
            return secret["data"]["data"].get("api_key", API_KEY_ENV)
        except Exception as e:
            log_error(f"Failed to retrieve API key from Vault: {key_name}", e)
            return API_KEY_ENV
            
    def store_api_key(self, key_name: str, api_key: str) -> bool:
        """Store API key in the secrets manager"""
        if not self.client:
            return False
            
        try:
            secret_path = f"{VAULT_PATH}/{key_name}"
            self.client.secrets.kv.create_or_update_secret(
                path=secret_path,
                secret={"api_key": api_key}
            )
            return True
        except Exception as e:
            log_error(f"Failed to store API key in Vault: {key_name}", e)
            return False
            
    def delete_api_key(self, key_name: str) -> bool:
        """Delete API key from the secrets manager"""
        if not self.client:
            return False
            
        try:
            secret_path = f"{VAULT_PATH}/{key_name}"
            self.client.secrets.kv.delete_metadata_and_all_versions(path=secret_path)
            return True
        except Exception as e:
            log_error(f"Failed to delete API key from Vault: {key_name}", e)
            return False

secrets_manager = SecretsManager()