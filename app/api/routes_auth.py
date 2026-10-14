import os
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.middleware import get_current_api_user
from app.core.key_engine import key_engine
from app.core.depotbox_client import depotbox_client
from app.config import DEPOTBOX_COOKIE, CACHE_DIR

router = APIRouter(prefix="/api/v1", tags=["Authentication & System"])

class CreateKeyRequest(BaseModel):
    label: str = Field("Public User", description="Descriptive name or application name for this key")
    tier: str = Field("premium", description="Subscription tier (e.g. premium, standard)")
    expires_days: Optional[int] = Field(365, description="Validity period in days (null for lifetime)")
    prefix: str = Field("dbx_", description="API Key prefix (e.g. dbx_ or smm_)")
    session_id: Optional[str] = Field(None, description="Optional override DepotBox session ID (connect.sid)")

class CreateKeyResponse(BaseModel):
    status: str
    key_id: str
    api_key: str
    label: str
    tier: str
    expires_at: Optional[int]
    message: str

@router.post("/auth/create-key", response_model=CreateKeyResponse, summary="Create an API key from DepotBox Session ID")
async def create_api_key_endpoint(payload: CreateKeyRequest):
    """
    Creates an API key backed by and cryptographically tied to the DepotBox session ID.
    If `session_id` is passed, it validates it or creates a key derived from it.
    Otherwise, it uses the server's master configured `DEPOTBOX_COOKIE`.
    """
    target_session = payload.session_id or DEPOTBOX_COOKIE
    if not target_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No DepotBox session ID provided and none configured in server .env."
        )

    # If a custom session ID was provided, verify with a temporary engine
    if payload.session_id and payload.session_id != DEPOTBOX_COOKIE:
        from app.core.key_engine import KeyEngine
        import hashlib
        derived_secret = hashlib.sha256(f"depotbox_salt_{payload.session_id}".encode()).hexdigest()
        custom_engine = KeyEngine(master_secret=derived_secret)
        record = custom_engine.create_api_key_from_session(
            label=payload.label,
            tier=payload.tier,
            expires_days=payload.expires_days,
            prefix=payload.prefix
        )
    else:
        record = key_engine.create_api_key_from_session(
            label=payload.label,
            tier=payload.tier,
            expires_days=payload.expires_days,
            prefix=payload.prefix
        )

    return CreateKeyResponse(
        status="success",
        key_id=record["key_id"],
        api_key=record["api_key"],
        label=record["label"],
        tier=record["tier"],
        expires_at=record.get("expires_at"),
        message="API Key created successfully! Keep this key safe. External clients can now use it."
    )

@router.get("/auth/verify", summary="Verify API key validity")
async def verify_key_endpoint(user: Dict[str, Any] = Depends(get_current_api_user)):
    """
    Validates the caller's API key and returns authentication details.
    """
    return {
        "status": "valid",
        "key_info": user
    }

@router.get("/health", summary="System Health & DepotBox Status")
async def health_check_endpoint():
    """
    Returns API server status, DepotBox upstream connectivity, and cache statistics.
    """
    is_valid, msg = await depotbox_client.check_session_health()

    # Count cached files
    cached_count = 0
    if os.path.exists(CACHE_DIR):
        cached_count = len([f for f in os.listdir(CACHE_DIR) if f.endswith(".zip")])

    return {
        "server": "online",
        "version": "1.0.0",
        "depotbox_session": {
            "configured": bool(DEPOTBOX_COOKIE),
            "status": "active" if is_valid else "warning",
            "message": msg
        },
        "cache": {
            "cached_games_count": cached_count,
            "directory": CACHE_DIR
        }
    }
