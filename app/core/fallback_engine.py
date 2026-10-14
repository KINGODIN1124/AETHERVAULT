import io
import json
import zipfile
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import aiohttp

# Public GitHub manifest mirrors
GITHUB_MANIFEST_REPOS = [
    "qwe213312/k25FCdfEOoEJ42S6",
    "AobaSora/SteamManifest",
    "AobaSora/Manifests",
    "ManifestAutoUpdate/ManifestAutoUpdate",
    "steam-manifest/steam-manifest",
    "sushi-dev55-alt/sushitools-games-repo-alt",
    "Selectively11/CloudRedirect",
    "madoiscool/LTSP"
]

class FallbackEngine:
    """
    Fallback manifest generator using SteamCMD PICS metadata and public GitHub mirrors.
    Generates a full .zip package containing all depot manifests and a compiled .lua script.
    """

    async def fetch_steamcmd_info(self, appid: int) -> Optional[Dict[str, Any]]:
        url = f"https://api.steamcmd.net/v1/info/{appid}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status") == "success":
                            return data.get("data", {}).get(str(appid), {})
        except Exception as e:
            print(f"[FallbackEngine] SteamCMD fetch error for {appid}: {e}")
        return None

    async def generate_zip_from_mirrors(self, appid: int, game_name: str = "") -> Optional[bytes]:
        app_info = await self.fetch_steamcmd_info(appid)
        if not app_info:
            return None

        actual_name = game_name or app_info.get("common", {}).get("name", f"AppID_{appid}")
        depots = app_info.get("depots", {})
        if not depots:
            return None

        # Collect public manifests
        depot_manifest_map = {}
        for d_id, d_val in depots.items():
            if d_id.isdigit() and isinstance(d_val, dict):
                manifests = d_val.get("manifests", {})
                public_manifest = manifests.get("public", {})
                if isinstance(public_manifest, dict):
                    gid = public_manifest.get("gid")
                    size = public_manifest.get("size")
                    if gid:
                        depot_manifest_map[str(d_id)] = {
                            "gid": str(gid),
                            "size": int(size) if size else None
                        }

        if not depot_manifest_map:
            return None

        # Fetch manifests from GitHub mirrors in parallel
        async with aiohttp.ClientSession() as session:
            async def fetch_one(d_id: str, gid: str) -> Tuple[str, str, Optional[bytes]]:
                for repo in GITHUB_MANIFEST_REPOS:
                    for branch in ["main", "master"]:
                        url = f"https://raw.githubusercontent.com/{repo}/{branch}/{d_id}_{gid}.manifest"
                        try:
                            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                                if r.status == 200:
                                    b = await r.read()
                                    if b and len(b) > 0:
                                        return d_id, gid, b
                        except Exception:
                            pass
                return d_id, gid, None

            tasks = [fetch_one(d_id, depot_manifest_map[d_id]["gid"]) for d_id in depot_manifest_map]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        manifest_files = {}
        for res in results:
            if isinstance(res, tuple) and res[2] is not None:
                d_id, gid, m_bytes = res
                manifest_files[f"{d_id}_{gid}.manifest"] = m_bytes

        if not manifest_files:
            return None

        # Build clean Lua script
        now_str = datetime.now().strftime("%B %d, %Y at %I:%M:%S %p")
        lua_lines = [
            "-- ============================================================",
            f"-- AUTOMATED STEAM CONFIG FOR {actual_name}",
            f"-- Generated via AetherVault Gateway",
            f"-- AppID:   {appid}",
            f"-- Date:    {now_str}",
            "-- ============================================================",
            "",
            f"addappid({appid}) -- {actual_name}",
            ""
        ]

        for d_id, d_info in depot_manifest_map.items():
            gid = d_info["gid"]
            size = d_info["size"]
            lua_lines.append(f"addappid({d_id}, 1)")
            if size:
                lua_lines.append(f"setManifestid({d_id}, \"{gid}\", {size})")
            else:
                lua_lines.append(f"setManifestid({d_id}, \"{gid}\")")

        lua_lines.extend([
            "",
            "-- ============================================================",
            f"-- Total Depots: {len(depot_manifest_map)}",
            "-- ============================================================"
        ])
        lua_content = "\n".join(lua_lines) + "\n"

        # Pack into ZIP archive
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
            for fname, bdata in manifest_files.items():
                z.writestr(fname, bdata)
            z.writestr(f"{appid}.lua", lua_content.encode("utf-8"))

        return zip_buffer.getvalue()

fallback_engine = FallbackEngine()
