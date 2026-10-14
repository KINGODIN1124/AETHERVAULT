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
    STATIC_API_KEYS,
    BASE_DIR
)

KEYS_REGISTRY_FILE = os.path.join(BASE_DIR, "keys.json")

class KeyEngine:
    """
    Manages API keys created from and verified against the master session secret.
    Supports:
      - 7-Day Public Trial Keys (Max 30 requests/day)
      - 1-Month Discord Member Keys (Max 150 requests/day)
      - Admin & Permanent Client Keys
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
        tier: str = "standard",
        expires_days: Optional[int] = 30,
        prefix: str = "av_"
    ) -> Dict[str, Any]:
        """
        Creates a new cryptographically signed API key.
        Tiers:
          - 'public_trial': 7-day access, 30 req/day
          - 'discord_member': 30-day access, 150 req/day
          - 'premium' / 'admin': Unlimited or high threshold
        """
        key_id = uuid.uuid4().hex[:12]
        created_at = int(time.time())
        exp = (created_at + (expires_days * 86400)) if expires_days else None

        payload = {
            "kid": key_id,
            "label": label,
            "tier": tier,
            "iat": created_at,
            "exp": exp
        }
        payload_bytes = json.dumps(payload, separators=(',', ':')).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")

        sig = hmac.new(self.master_secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        api_key = f"{prefix}{payload_b64}.{sig[:32]}"

        key_record = {
            "key_id": key_id,
            "api_key": api_key,
            "label": label,
            "tier": tier,
            "created_at": created_at,
            "expires_at": exp,
            "active": True
        }
        self.registry[key_id] = key_record
        self._save_registry()
        return key_record

    def get_or_create_public_7day_key(self) -> Dict[str, Any]:
        """Returns the active 7-Day Public Trial Key (rotates if expired)."""
        now = time.time()
        for kid, r in self.registry.items():
            if r.get("tier") == "public_trial" and r.get("active", True):
                if r.get("expires_at", 0) > now:
                    return r

        # Create fresh 7-day public trial key
        return self.create_api_key_from_session(
            label="7-Day Public Community Trial",
            tier="public_trial",
            expires_days=7,
            prefix="av_public_"
        )

    def create_discord_member_key(self, user_id: int, username: str) -> Dict[str, Any]:
        """Generates a 1-Month (30 Days) Extended Access Key for Discord members."""
        return self.create_api_key_from_session(
            label=f"Discord Member: {username} ({user_id})",
            tier="discord_member",
            expires_days=30,
            prefix="av_discord_"
        )

    def verify_api_key(self, api_key: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        if not api_key or not isinstance(api_key, str):
            return False, None

        api_key = api_key.strip()

        # Check static whitelist
        if api_key in STATIC_API_KEYS:
            return True, {
                "key_id": "static",
                "label": "Static Preconfigured Key",
                "tier": "admin",
                "active": True
            }

        # Check registry by exact key match
        for kid, record in self.registry.items():
            if record.get("api_key") == api_key:
                if not record.get("active", True):
                    return False, None  # Revoked
                exp = record.get("expires_at")
                if exp and time.time() > exp:
                    return False, None  # Expired
                return True, record

        # Check stateless cryptographic signature
        if "." in api_key:
            parts = api_key.split(".", 1)
            raw_payload = parts[0]
            received_sig = parts[1]

            payload_b64 = raw_payload
            for pfx in ["av_public_", "av_discord_", "av_", "dbx_", "smm_"]:
                if payload_b64.startswith(pfx):
                    payload_b64 = payload_b64[len(pfx):]
                    break

            try:
                padding = len(payload_b64) % 4
                if padding:
                    payload_b64 += "=" * (4 - padding)
                payload_json = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
                payload = json.loads(payload_json)

                expected_sig = hmac.new(
                    self.master_secret,
                    payload_b64.rstrip("=").encode("utf-8"),
                    hashlib.sha256
                ).hexdigest()[:32]

                if hmac.compare_digest(received_sig, expected_sig):
                    exp = payload.get("exp")
                    if exp and time.time() > exp:
                        return False, None
                    return True, payload
            except Exception:
                pass

        return False, None

    def revoke_key(self, key_id: str) -> bool:
        if key_id in self.registry:
            self.registry[key_id]["active"] = False
            self._save_registry()
            return True
        return False

    def list_keys(self) -> Dict[str, Any]:
        return self.registry

key_engine = KeyEngine()
