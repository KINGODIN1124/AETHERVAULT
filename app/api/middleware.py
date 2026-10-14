import time
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from app.core.key_engine import key_engine
from app.config import RATE_LIMIT_PER_MINUTE

header_api_key = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)

# In-memory sliding rate limiter: {key_or_ip: [timestamps]}
RATE_LIMIT_BUCKETS: Dict[str, list] = {}

def check_rate_limit(client_id: str, max_requests: int = RATE_LIMIT_PER_MINUTE, window_seconds: int = 60):
    now = time.time()
    if client_id not in RATE_LIMIT_BUCKETS:
        RATE_LIMIT_BUCKETS[client_id] = []

    # Clean old requests
    RATE_LIMIT_BUCKETS[client_id] = [t for t in RATE_LIMIT_BUCKETS[client_id] if now - t < window_seconds]

    if len(RATE_LIMIT_BUCKETS[client_id]) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({max_requests} requests per minute). Please try again shortly."
        )

    RATE_LIMIT_BUCKETS[client_id].append(now)

async def get_current_api_user(
    request: Request,
    api_key_header: Optional[str] = Security(header_api_key),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth)
) -> Dict[str, Any]:
    """
    Extracts and authenticates the API key from Header, Bearer token, or Query param.
    """
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
            detail="API Key required. Provide via 'X-API-Key' header, 'Authorization: Bearer <key>', or '?key=<key>' query param."
        )

    is_valid, key_record = key_engine.verify_api_key(api_key)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid, expired, or revoked API key."
        )

    # Rate limiting by key
    client_ident = key_record.get("key_id", api_key[:10])
    check_rate_limit(client_ident)

    return key_record
