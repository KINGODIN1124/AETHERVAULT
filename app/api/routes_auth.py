import os
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.middleware import get_current_api_user
from app.core.key_engine import key_engine
from app.core.upstream_client import upstream_client
from app.core.anti_scrape import anti_scrape
from app.config import SESSION_COOKIE, CACHE_DIR

router = APIRouter(prefix="/api/v1", tags=["Authentication & System"])

class CreateKeyRequest(BaseModel):
    label: str = Field("Developer Key", description="Name or application name for this key")
    tier: str = Field("standard", description="Subscription tier (public_trial, discord_member, premium, admin)")
    expires_days: Optional[int] = Field(30, description="Validity period in days (e.g. 7 for trial, 30 for Discord)")
    prefix: str = Field("av_", description="Key prefix (e.g. av_, smm_)")

class CreateKeyResponse(BaseModel):
    status: str
    key_id: str
    api_key: str
    label: str
    tier: str
    expires_at: Optional[int]
    message: str

class DiscordClaimRequest(BaseModel):
    user_id: int = Field(..., description="Discord User ID")
    username: str = Field(..., description="Discord Username")

@router.get("/auth/public-key", summary="Get 7-Day Public Community Trial Key")
async def get_public_trial_key():
    """
    Returns the active 7-Day Public Community Trial Key.
    Quota: 30 requests per 24 hours. Rotates weekly.
    """
    record = key_engine.get_or_create_public_7day_key()
    return {
        "status": "success",
        "api_key": record["api_key"],
        "tier": "public_trial",
        "validity_days": 7,
        "daily_limit": 30,
        "expires_at": record.get("expires_at"),
        "note": "For 1-Month Extended Access with 150 req/day, join our Discord server and use /claimkey!"
    }

@router.post("/auth/create-key", response_model=CreateKeyResponse, summary="Create an API key (Admin / Master)")
async def create_api_key_endpoint(payload: CreateKeyRequest, admin: Dict[str, Any] = Depends(get_current_api_user)):
    """Admin endpoint to mint an authorized API key."""
    if admin.get("tier") not in ("admin", "static", "unlimited"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin keys can mint new API keys via REST."
        )

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
        message="API Key created successfully!"
    )

@router.post("/auth/claim-discord-key", response_model=CreateKeyResponse, summary="Discord Bot 1-Month Key Minter")
async def claim_discord_key(payload: DiscordClaimRequest):
    """
    Internal/Bot endpoint used by your Discord Bot to issue a 1-month API key to verified server members.
    """
    record = key_engine.create_discord_member_key(user_id=payload.user_id, username=payload.username)
    return CreateKeyResponse(
        status="success",
        key_id=record["key_id"],
        api_key=record["api_key"],
        label=record["label"],
        tier="discord_member",
        expires_at=record.get("expires_at"),
        message="1-Month Discord Member Key generated successfully!"
    )

@router.get("/auth/verify", summary="Verify API key validity")
async def verify_key_endpoint(user: Dict[str, Any] = Depends(get_current_api_user)):
    """Validates the caller's API key and returns tier and quota information."""
    return {
        "status": "valid",
        "key_info": user
    }

@router.get("/admin/banned-ips", summary="List Banned IPs (Anti-Scrape)")
async def list_banned_ips(admin: Dict[str, Any] = Depends(get_current_api_user)):
    """Returns list of currently blacklisted IPs."""
    return anti_scrape.banned_ips

@router.post("/admin/unban/{ip}", summary="Unban IP Address")
async def unban_ip_endpoint(ip: str, admin: Dict[str, Any] = Depends(get_current_api_user)):
    """Removes an IP address from the scraper blacklist."""
    ok = anti_scrape.unban_ip(ip)
    if not ok:
        raise HTTPException(status_code=404, detail="IP address not found in ban list.")
    return {"status": "success", "message": f"IP {ip} has been unbanned."}

@router.get("/health", summary="System Health & Upstream Status")
async def health_check_endpoint():
    """Returns API server status, upstream engine connection, and cache stats."""
    is_valid, msg = await upstream_client.check_session_health()

    cached_count = 0
    if os.path.exists(CACHE_DIR):
        cached_count = len([f for f in os.listdir(CACHE_DIR) if f.endswith(".zip")])

    return {
        "service": "AetherVault Gateway",
        "status": "healthy",
        "version": "2.0.0",
        "upstream_engine": {
            "configured": bool(SESSION_COOKIE),
            "status": "active" if is_valid else "warning",
            "message": msg
        },
        "cache": {
            "cached_packages": cached_count,
            "directory": CACHE_DIR
        },
        "anti_scraping_shield": {
            "status": "active" if anti_scrape.enabled else "disabled",
            "banned_ips_count": len(anti_scrape.banned_ips)
        }
    }
