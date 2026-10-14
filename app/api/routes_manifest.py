import os
import io
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, Path, HTTPException, status, Response
from fastapi.responses import PlainTextResponse

from app.api.middleware import get_current_api_user
from app.core.upstream_client import upstream_client
from app.core.cache_manager import cache_manager
from app.core.fallback_engine import fallback_engine
from app.config import ENABLE_FALLBACK_MIRRORS

router = APIRouter(prefix="/api/v1", tags=["Manifest & Lua"])

async def get_or_download_zip(appid: int, game_name: str = "", force_refresh: bool = False) -> bytes:
    """Helper to retrieve ZIP from cache, upstream engine, or fallback mirrors."""
    if not force_refresh and cache_manager.has_manifest(appid):
        cached = cache_manager.get_zip_bytes(appid)
        if cached:
            return cached

    # 1. Try Upstream Manifest Engine
    try:
        zip_bytes = await upstream_client.fetch_manifest_zip(appid, game_name)
        if zip_bytes and len(zip_bytes) >= 512:
            cache_manager.save_zip(appid, zip_bytes)
            return zip_bytes
    except Exception as e:
        print(f"[ManifestRoute] Upstream download error for AppID {appid}: {e}")

    # 2. Try Fallback Mirrors if enabled
    if ENABLE_FALLBACK_MIRRORS:
        try:
            print(f"[ManifestRoute] Falling back to SteamCMD & GitHub mirrors for AppID {appid}...")
            mirror_zip = await fallback_engine.generate_zip_from_mirrors(appid, game_name)
            if mirror_zip and len(mirror_zip) >= 100:
                cache_manager.save_zip(appid, mirror_zip)
                return mirror_zip
        except Exception as fallback_err:
            print(f"[ManifestRoute] Fallback engine failed for AppID {appid}: {fallback_err}")

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Unable to find or compile manifest for Steam AppID {appid} across all providers."
    )

@router.get("/manifest/{appid}", summary="Download complete manifest ZIP archive")
async def get_manifest_zip(
    appid: int = Path(..., description="Steam Application ID (e.g. 730, 1817190)"),
    name: Optional[str] = Query("", description="Optional game title"),
    force: bool = Query(False, description="Force fresh fetch bypassing cache"),
    user: Dict[str, Any] = Depends(get_current_api_user)
):
    """
    Downloads a complete ZIP package containing the `{appid}.lua` configuration
    and all associated `{depot_id}_{manifest_gid}.manifest` binary files.
    """
    zip_bytes = await get_or_download_zip(appid, game_name=name, force_refresh=force)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={appid}.zip",
            "Content-Length": str(len(zip_bytes)),
            "X-AppID": str(appid),
            "X-Source": "AetherVault-API-Gateway"
        }
    )

@router.get("/lua/{appid}", summary="Get raw Lua configuration script")
async def get_lua_config(
    appid: int = Path(..., description="Steam Application ID"),
    name: Optional[str] = Query("", description="Optional game title"),
    as_attachment: bool = Query(False, description="Return as downloadable attachment"),
    user: Dict[str, Any] = Depends(get_current_api_user)
):
    """
    Extracts and returns the Steam `{appid}.lua` configuration script.
    """
    lua_code = cache_manager.get_lua_content(appid)
    if not lua_code:
        # Fetch package first to extract Lua
        await get_or_download_zip(appid, game_name=name)
        lua_code = cache_manager.get_lua_content(appid)

    if not lua_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lua configuration not found for AppID {appid}."
        )

    headers = {"Content-Type": "text/plain; charset=utf-8"}
    if as_attachment:
        headers["Content-Disposition"] = f"attachment; filename={appid}.lua"

    return PlainTextResponse(content=lua_code, headers=headers)

@router.get("/manifest/{appid}/{depot_id}", summary="Download specific depot manifest binary")
async def get_single_manifest(
    appid: int = Path(..., description="Steam Application ID"),
    depot_id: str = Path(..., description="Depot ID (e.g. 731)"),
    user: Dict[str, Any] = Depends(get_current_api_user)
):
    """
    Returns a specific `.manifest` binary file from the game's manifest archive.
    """
    if not cache_manager.has_manifest(appid):
        await get_or_download_zip(appid)

    m_bytes = cache_manager.get_manifest_file(appid, depot_id)
    if not m_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manifest binary for depot {depot_id} not found in package for AppID {appid}."
        )

    return Response(
        content=m_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={depot_id}.manifest"}
    )

@router.get("/info/{appid}", summary="Inspect manifest package metadata")
async def get_package_info(
    appid: int = Path(..., description="Steam Application ID"),
    user: Dict[str, Any] = Depends(get_current_api_user)
):
    """
    Returns metadata regarding the manifest package for an AppID without downloading the whole binary.
    """
    if not cache_manager.has_manifest(appid):
        await get_or_download_zip(appid)

    info = cache_manager.inspect_archive(appid)
    if not info:
        raise HTTPException(status_code=404, detail="Archive information unavailable.")
    return info

# Compatibility endpoint for VesperDownloader style callers
@router.get("/partner/lua", tags=["Compatibility Endpoints"], summary="Vesper/Partner format compatibility")
async def partner_compatibility_endpoint(
    appid: int = Query(..., description="Steam AppID"),
    name: Optional[str] = Query("", description="Game Title"),
    user: Dict[str, Any] = Depends(get_current_api_user)
):
    """
    Drop-in compatibility route for tools expecting the `/api/partner/lua?appid={id}` format.
    """
    zip_bytes = await get_or_download_zip(appid, game_name=name)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={appid}.zip"}
    )
