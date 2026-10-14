import os
import json
import time
import hmac
import base64
import hashlib
import uuid
from typing import Optional, Dict, Any, Tuple
from app.config import (
    API_MASTER_SECRET,
    DEPOTBOX_COOKIE,
    STATIC_API_KEYS,
    BASE_DIR
)

KEYS_REGISTRY_FILE = os.path.join(BASE_DIR, "keys.json")

class KeyEngine:
    """
    Manages API keys created from and verified against the DepotBox session ID.
    Supports both stateless cryptographically signed tokens (HMAC-SHA256)
    and a local audited JSON key registry.
    """

    def __init__(self, master_secret: str = API_MASTER_SECRET):
        self.master_secret = master_secret.encode("utf-8")
        self._load_registry()

    def _load_registry(self) -> Dict[str, Any]:
        self.registry: Dict[str, Any] = {}
        if os.path.exists(KEYS_REGISTRY_FILE):
            try:
                with open(KEYS_REGISTRY_FILE, "r", encoding="utf-8") as f:
                    self.registry = json.load(f)
            except Exception as e:
                print(f"[KeyEngine] Warning: failed to parse {KEYS_REGISTRY_FILE}: {e}")
                self.registry = {}
        return self.registry

    def _save_registry(self):
        try:
            with open(KEYS_REGISTRY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.registry, f, indent=2)
        except Exception as e:
            print(f"[KeyEngine] Error saving {KEYS_REGISTRY_FILE}: {e}")

    def create_api_key_from_session(
        self,
        label: str = "Default Client",
        tier: str = "premium",
        expires_days: Optional[int] = 365,
        prefix: str = "dbx_"
    ) -> Dict[str, Any]:
        """
        Creates a new cryptographically signed API key tied to the DepotBox session ID.
        """
        key_id = uuid.uuid4().hex[:12]
        created_at = int(time.time())
        exp = (created_at + (expires_days * 86400)) if expires_days else None

        # Build payload
        payload = {
            "kid": key_id,
            "label": label,
            "tier": tier,
            "iat": created_at,
            "exp": exp
        }
        payload_bytes = json.dumps(payload, separators=(',', ':')).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")

        # Compute HMAC signature using master secret (derived from DepotBox session)
        sig = hmac.new(self.master_secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()

        # Final key format
        api_key = f"{prefix}{payload_b64}.{sig[:32]}"

        # Record in registry for management and tracking
        key_record = {
            "key_id": key_id,
            "api_key": api_key,
            "label": label,
            "tier": tier,
            "created_at": created_at,
            "expires_at": exp,
            "active": True,
            "request_count": 0
        }
        self.registry[key_id] = key_record
        self._save_registry()

        return key_record

    def verify_api_key(self, api_key: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validates an API key.
        Checks:
          1. Static pre-configured keys in .env
          2. Cryptographic signature derived from DepotBox session ID
          3. Local registry for revocation and expiration
        """
        if not api_key or not isinstance(api_key, str):
            return False, None

        api_key = api_key.strip()

        # 1. Check static whitelist
        if api_key in STATIC_API_KEYS:
            return True, {
                "key_id": "static",
                "label": "Static Environment Key",
                "tier": "premium",
                "active": True
            }

        # 2. Check registry by exact key match
        for kid, record in self.registry.items():
            if record.get("api_key") == api_key:
                if not record.get("active", True):
                    return False, None  # Revoked
                exp = record.get("expires_at")
                if exp and time.time() > exp:
                    return False, None  # Expired
                return True, record

        # 3. Check stateless cryptographic token
        # Format: prefix<payload_b64>.<sig>
        if "." in api_key:
            parts = api_key.split(".", 1)
            raw_payload = parts[0]
            received_sig = parts[1]

            # Strip known prefixes like dbx_ or smm_
            payload_b64 = raw_payload
            for pfx in ["dbx_", "smm_"]:
                if payload_b64.startswith(pfx):
                    payload_b64 = payload_b64[len(pfx):]
                    break

            try:
                # Add padding back if necessary
                padding = len(payload_b64) % 4
                if padding:
                    payload_b64 += "=" * (4 - padding)
                payload_json = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
                payload = json.loads(payload_json)

                # Recompute signature
                raw_token_data = parts[0]
                if raw_token_data.startswith("dbx_") or raw_token_data.startswith("smm_"):
                    # Signature was computed over payload_b64
                    pass
                expected_sig = hmac.new(self.master_secret, payload_b64.rstrip("=").encode("utf-8"), hashlib.sha256).hexdigest()[:32]

                if hmac.compare_digest(received_sig, expected_sig):
                    # Check expiry
                    exp = payload.get("exp")
                    if exp and time.time() > exp:
                        return False, None
                    return True, payload
            except Exception:
                pass

        return False, None

    def revoke_key(self, key_id: str) -> bool:
        """Revokes an API key by ID."""
        if key_id in self.registry:
            self.registry[key_id]["active"] = False
            self._save_registry()
            return True
        return False

    def list_keys(self) -> Dict[str, Any]:
        """Returns all keys in registry."""
        return self.registry

# Global instance
key_engine = KeyEngine()
