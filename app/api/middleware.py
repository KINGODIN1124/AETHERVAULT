import time
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from app.core.key_engine import key_engine
from app.core.anti_scrape import anti_scrape

header_api_key = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)

def get_client_ip(request: Request) -> str:
    """Extracts client IP, respecting X-Forwarded-For when behind proxy/Cloudflare."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"

async def get_current_api_user(
    request: Request,
    api_key_header: Optional[str] = Security(header_api_key),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth)
) -> Dict[str, Any]:
    """
    Extracts, authenticates, and validates API keys.
    Enforces anti-scraping burst protection, IP blacklisting, and 24-hour daily quotas.
    """
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")

    # Pre-check IP Ban
    banned, ban_reason = anti_scrape.is_ip_banned(client_ip)
    if banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ban_reason
        )

    api_key = None

    # 1. Check X-API-Key header
    if api_key_header:
        api_key = api_key_header

    # 2. Check Bearer token
    elif bearer_creds and bearer_creds.credentials:
        api_key = bearer_creds.credentials

    # 3. Check Query parameter (?key= or ?api_key=)
    elif "key" in request.query_params:
        api_key = request.query_params.get("key")
    elif "api_key" in request.query_params:
        api_key = request.query_params.get("api_key")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "API Key required. Use the 7-Day Public Trial Key from our GitHub README, "
                "or pass your key via 'X-API-Key' header or '?key=<key>' parameter."
            )
        )

    is_valid, key_record = key_engine.verify_api_key(api_key)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid, expired, or revoked API key."
        )

    # Enforce Anti-Scraping Shield & Daily Quota Limits
    allowed, error_msg = anti_scrape.check_request(client_ip, user_agent, key_record)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS if "Daily limit" in error_msg else status.HTTP_403_FORBIDDEN,
            detail=error_msg
        )

    return key_record
