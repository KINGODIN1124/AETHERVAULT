import os
import json
import time
import asyncio
from typing import Optional, Dict, Any, Tuple
from app.config import SESSION_COOKIE, UPSTREAM_URL
from app.core.session_refresher import session_refresher

try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

import aiohttp

class UpstreamEngineClient:
    """
    High-performance client to fetch manifest ZIP archives from the upstream
    manifest engine using an authenticated session.
    Features automatic session rejuvenation on expiry.
    """

    def __init__(self):
        self.base_url = UPSTREAM_URL
        self.default_ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )

    def _get_cookie(self) -> str:
        import app.config as cfg
        return cfg.SESSION_COOKIE

    def _get_headers(self) -> Dict[str, str]:
        cookie = self._get_cookie()
        return {
            "User-Agent": self.default_ua,
            "Cookie": f"connect.sid={cookie}",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def check_session_health(self) -> Tuple[bool, str]:
        """Tests if the upstream session is active."""
        cookie = self._get_cookie()
        if not cookie:
            return False, "No session cookie configured in .env"

        url = f"{self.base_url}/dashboard"
        headers = self._get_headers()

        if HAS_CURL_CFFI:
            try:
                loop = asyncio.get_event_loop()
                def _probe():
                    s = curl_requests.Session(impersonate="chrome120")
                    return s.get(url, headers=headers, timeout=12)
                resp = await loop.run_in_executor(None, _probe)
                if resp.status_code == 200 and "/login" not in resp.url.lower():
                    return True, "Upstream engine session active and verified"
                elif resp.status_code == 403:
                    return False, "Upstream challenge received (cookie refresh recommended)"
                return False, f"Unexpected response: HTTP {resp.status_code}"
            except Exception:
                pass

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10, allow_redirects=True) as resp:
                    final_url = str(resp.url)
                    if resp.status == 200 and "/login" not in final_url.lower():
                        return True, "Upstream engine session active and verified"
                    return False, f"Session invalid (Redirected to {final_url})"
        except Exception as e:
            return False, f"Network check error: {e}"

    async def _initiate_download_raw(self, appid: int, game_name: str = "") -> str:
        cookie = self._get_cookie()
        if not cookie:
            raise ValueError("Upstream session cookie missing.")

        url = f"{self.base_url}/initiate-download"
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"
        payload = {"appId": str(appid), "gameName": game_name or f"App_{appid}"}

        if HAS_CURL_CFFI:
            try:
                loop = asyncio.get_event_loop()
                def _do_post():
                    s = curl_requests.Session(impersonate="chrome120")
                    return s.post(url, headers=headers, json=payload, timeout=20)
                resp = await loop.run_in_executor(None, _do_post)
                if resp.status_code == 200:
                    data = resp.json()
                    token = data.get("token")
                    if token:
                        return token
                elif resp.status_code == 400:
                    text = resp.text
                    if "CAPTCHA" in text or "expired" in text.lower():
                        raise Exception("SESSION_EXPIRED: CAPTCHA required or session timed out.")
                    raise Exception(f"Upstream returned 400: {text[:200]}")
            except Exception as e:
                if "SESSION_EXPIRED" in str(e):
                    raise e

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
                data=json.dumps(payload).encode("utf-8"),
                timeout=aiohttp.ClientTimeout(total=25)
            ) as resp:
                if resp.status == 400:
                    body = await resp.text()
                    if "CAPTCHA" in body or "expired" in body.lower():
                        raise Exception("SESSION_EXPIRED: Session timed out.")
                    raise Exception(f"Upstream initiate 400: {body[:200]}")
                if resp.status != 200:
                    raise Exception(f"Upstream initiate HTTP {resp.status}")

                data = await resp.json()
                token = data.get("token")
                if not token:
                    raise Exception(f"No token received: {data}")
                return token

    async def initiate_download(self, appid: int, game_name: str = "") -> str:
        """Initiates download with auto-refresh retry on expired session."""
        try:
            return await self._initiate_download_raw(appid, game_name)
        except Exception as e:
            if "SESSION_EXPIRED" in str(e):
                print("⚠️ [UpstreamClient] Session expired! Triggering automated rejuvenation...")
                refreshed, msg = await session_refresher.auto_refresh_session()
                if refreshed:
                    print(f"🔄 [UpstreamClient] Retrying download with refreshed session...")
                    return await self._initiate_download_raw(appid, game_name)
                else:
                    print(f"❌ [UpstreamClient] Auto-refresh failed: {msg}")
            raise e

    async def poll_status(self, token: str, max_wait_seconds: int = 240, poll_interval: float = 1.0) -> Dict[str, Any]:
        url = f"{self.base_url}/status/{token}"
        headers = self._get_headers()
        elapsed = 0.0

        async with aiohttp.ClientSession() as session:
            while elapsed < max_wait_seconds:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        raise Exception(f"Upstream status poll failed HTTP {resp.status}")
                    data = await resp.json()

                status = data.get("status", "")
                if status in ("completed", "completed_with_warnings"):
                    return data
                elif status == "failed":
                    reason = data.get("failureReason", data.get("message", "Build failed"))
                    raise Exception(f"Manifest generation failed: {reason}")
                elif status == "invalid_or_expired":
                    raise Exception("Job token expired.")

                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

        raise TimeoutError(f"Job timed out after {max_wait_seconds}s.")

    async def download_file(self, token: str) -> bytes:
        url = f"{self.base_url}/download/{token}"
        headers = self._get_headers()

        for attempt in range(1, 4):
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        if len(content) >= 512:
                            return content
            await asyncio.sleep(1.0)

        raise Exception("Failed to stream valid payload from upstream archive.")

    async def fetch_manifest_zip(self, appid: int, game_name: str = "") -> bytes:
        token = await self.initiate_download(appid, game_name)
        await self.poll_status(token)
        return await self.download_file(token)

upstream_client = UpstreamEngineClient()
