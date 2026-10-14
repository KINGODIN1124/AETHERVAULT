import os
import json
import time
import asyncio
from typing import Optional, Dict, Any, Tuple
from app.config import DEPOTBOX_COOKIE

try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

import aiohttp

class DepotBoxClient:
    """
    High-performance client to fetch manifest ZIP archives from depotbox.org
    using a Premium session cookie (connect.sid).
    """

    def __init__(self, cookie: str = DEPOTBOX_COOKIE):
        self.cookie = cookie
        self.base_url = "https://depotbox.org"
        self.default_ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )

    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": self.default_ua,
            "Cookie": f"connect.sid={self.cookie}",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def check_session_health(self) -> Tuple[bool, str]:
        """
        Tests if the DepotBox session cookie is valid and accepted.
        Returns: (is_valid, message)
        """
        if not self.cookie:
            return False, "No DEPOTBOX_COOKIE configured in .env"

        url = f"{self.base_url}/dashboard"
        headers = self._get_headers()

        # Try with curl_cffi first for TLS impersonation
        if HAS_CURL_CFFI:
            try:
                loop = asyncio.get_event_loop()
                def _probe():
                    s = curl_requests.Session(impersonate="chrome120")
                    return s.get(url, headers=headers, timeout=12)
                resp = await loop.run_in_executor(None, _probe)
                if resp.status_code == 200 and "/login" not in resp.url.lower():
                    return True, "DepotBox session active and verified (Premium)"
                elif resp.status_code == 403:
                    return False, "Cloudflare challenge received on dashboard (Check Turnstile or cookie freshness)"
                return False, f"Unexpected response from dashboard: HTTP {resp.status_code}"
            except Exception as e:
                pass

        # Fallback to aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10, allow_redirects=True) as resp:
                    final_url = str(resp.url)
                    if resp.status == 200 and "/login" not in final_url.lower():
                        return True, "DepotBox session active and verified (Premium)"
                    return False, f"Session invalid (Redirected to {final_url}, HTTP {resp.status})"
        except Exception as e:
            return False, f"Network error checking session: {e}"

    async def initiate_download(self, appid: int, game_name: str = "") -> str:
        """
        Initiates a download job for a given Steam AppID.
        Returns the job token.
        """
        if not self.cookie:
            raise ValueError("DepotBox session cookie is missing. Set DEPOTBOX_COOKIE in .env.")

        url = f"{self.base_url}/initiate-download"
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"
        payload = {"appId": str(appid), "gameName": game_name or f"App_{appid}"}

        # Attempt with curl_cffi first
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
                    if "CAPTCHA" in text:
                        raise Exception("DepotBox: CAPTCHA required. Session cookie may be expired or not Premium.")
                    raise Exception(f"DepotBox returned 400: {text[:200]}")
            except Exception as e:
                if "CAPTCHA" in str(e):
                    raise e
                # Fall through to aiohttp if curl_cffi encountered non-auth error

        # aiohttp attempt
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
                data=json.dumps(payload).encode("utf-8"),
                timeout=aiohttp.ClientTimeout(total=25)
            ) as resp:
                if resp.status == 400:
                    body = await resp.text()
                    if "CAPTCHA" in body:
                        raise Exception("DepotBox: CAPTCHA required. Session cookie may be expired or not Premium.")
                    raise Exception(f"DepotBox initiate-download 400: {body[:200]}")
                if resp.status != 200:
                    raise Exception(f"DepotBox initiate-download HTTP {resp.status}")

                data = await resp.json()
                token = data.get("token")
                if not token:
                    raise Exception(f"No token received from initiate-download: {data}")
                return token

    async def poll_status(self, token: str, max_wait_seconds: int = 240, poll_interval: float = 1.0) -> Dict[str, Any]:
        """
        Polls the status endpoint until the manifest compilation finishes.
        """
        url = f"{self.base_url}/status/{token}"
        headers = self._get_headers()
        elapsed = 0.0

        async with aiohttp.ClientSession() as session:
            while elapsed < max_wait_seconds:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        raise Exception(f"DepotBox status poll failed with HTTP {resp.status}")
                    data = await resp.json()

                status = data.get("status", "")
                if status in ("completed", "completed_with_warnings"):
                    return data
                elif status == "failed":
                    reason = data.get("failureReason", data.get("message", "Unknown failure"))
                    raise Exception(f"DepotBox manifest generation failed: {reason}")
                elif status == "invalid_or_expired":
                    raise Exception("DepotBox download token has expired.")

                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

        raise TimeoutError(f"DepotBox manifest generation timed out after {max_wait_seconds} seconds.")

    async def download_file(self, token: str) -> bytes:
        """
        Streams and downloads the final manifest ZIP archive.
        """
        url = f"{self.base_url}/download/{token}"
        headers = self._get_headers()

        # Retry loop for download
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        if len(content) >= 512:
                            return content

            if attempt < max_attempts:
                await asyncio.sleep(1.0)

        raise Exception("Failed to retrieve valid ZIP payload from DepotBox after 3 attempts.")

    async def fetch_manifest_zip(self, appid: int, game_name: str = "") -> bytes:
        """
        Complete end-to-end pipeline:
        1. Initiate download
        2. Poll until completed
        3. Download and return raw ZIP bytes
        """
        token = await self.initiate_download(appid, game_name)
        await self.poll_status(token)
        return await self.download_file(token)

# Global client instance
depotbox_client = DepotBoxClient()
