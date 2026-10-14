import os
import hashlib
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# DepotBox Authentication
DEPOTBOX_COOKIE = os.getenv("DEPOTBOX_COOKIE", "").strip()

# Derived or explicit Master Secret for cryptographic API key signing
RAW_MASTER_SECRET = os.getenv("API_MASTER_SECRET", "").strip()
if not RAW_MASTER_SECRET and DEPOTBOX_COOKIE:
    # Deterministically derive master signing secret from SHA256 of session ID
    API_MASTER_SECRET = hashlib.sha256(f"depotbox_salt_{DEPOTBOX_COOKIE}".encode()).hexdigest()
else:
    API_MASTER_SECRET = RAW_MASTER_SECRET or "default_depotbox_api_secret_change_me"

# Pre-authorized static keys
STATIC_KEYS_ENV = os.getenv("STATIC_API_KEYS", "")
STATIC_API_KEYS = set(k.strip() for k in STATIC_KEYS_ENV.split(",") if k.strip())

# Server Settings
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

# Rate Limiting
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", 60))

# Cache
ENABLE_CACHE = os.getenv("ENABLE_CACHE", "true").lower() in ("1", "true", "yes")
CACHE_DIR = os.getenv("CACHE_DIR", os.path.join(BASE_DIR, "cache_storage"))
os.makedirs(CACHE_DIR, exist_ok=True)

# Fallbacks
ENABLE_FALLBACK_MIRRORS = os.getenv("ENABLE_FALLBACK_MIRRORS", "true").lower() in ("1", "true", "yes")
