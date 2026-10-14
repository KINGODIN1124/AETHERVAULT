import os
import base64
import hashlib
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Upstream Session & Authentication
SESSION_COOKIE = (
    os.getenv("UPSTREAM_SESSION_COOKIE", "")
    or os.getenv("SESSION_COOKIE", "")
).strip()

# Internal upstream engine target
_DEF_UPSTREAM = base64.b64decode("aHR0cHM6Ly9kZXBvdGJveC5vcmc=").decode("utf-8")
UPSTREAM_URL = os.getenv("UPSTREAM_URL", _DEF_UPSTREAM).rstrip("/")
UPSTREAM_EMAIL = os.getenv("UPSTREAM_EMAIL", "").strip()
UPSTREAM_PASSWORD = os.getenv("UPSTREAM_PASSWORD", "").strip()

# Derived or explicit Master Secret for cryptographic API key signing
RAW_MASTER_SECRET = os.getenv("API_MASTER_SECRET", "").strip()
if not RAW_MASTER_SECRET and SESSION_COOKIE:
    API_MASTER_SECRET = hashlib.sha256(f"aethervault_salt_{SESSION_COOKIE}".encode()).hexdigest()
else:
    API_MASTER_SECRET = RAW_MASTER_SECRET or "aethervault_default_secret_key_change_me"

# Pre-authorized static keys
STATIC_KEYS_ENV = os.getenv("STATIC_API_KEYS", "")
STATIC_API_KEYS = set(k.strip() for k in STATIC_KEYS_ENV.split(",") if k.strip())

# Server Settings
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

# Rate Limiting & Anti-Scraping Defense
ENABLE_ANTI_SCRAPING = os.getenv("ENABLE_ANTI_SCRAPING", "true").lower() in ("1", "true", "yes")
PUBLIC_DAILY_LIMIT = int(os.getenv("PUBLIC_DAILY_LIMIT", 30))             # Max requests per day for public keys
DISCORD_DAILY_LIMIT = int(os.getenv("DISCORD_DAILY_LIMIT", 150))          # Max requests per day for 1-month Discord keys
BURST_LIMIT_PER_SECOND = int(os.getenv("BURST_LIMIT_PER_SECOND", 5))      # Ban if > 5 req/sec
BAN_DURATION_HOURS = int(os.getenv("BAN_DURATION_HOURS", 24))             # Auto-ban duration

# Cache
ENABLE_CACHE = os.getenv("ENABLE_CACHE", "true").lower() in ("1", "true", "yes")
CACHE_DIR = os.getenv("CACHE_DIR", os.path.join(BASE_DIR, "cache_storage"))
os.makedirs(CACHE_DIR, exist_ok=True)

# Session Storage
SESSION_STORAGE_DIR = os.path.join(BASE_DIR, "session_storage")
os.makedirs(SESSION_STORAGE_DIR, exist_ok=True)

# Fallbacks
ENABLE_FALLBACK_MIRRORS = os.getenv("ENABLE_FALLBACK_MIRRORS", "true").lower() in ("1", "true", "yes")
