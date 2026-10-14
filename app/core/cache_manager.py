import os
import io
import zipfile
from typing import Optional, Dict, Any, Tuple
from app.config import CACHE_DIR, ENABLE_CACHE

class CacheManager:
    """
    Local filesystem and in-memory cache for downloaded manifest packages.
    """

    def __init__(self, cache_dir: str = CACHE_DIR, enabled: bool = ENABLE_CACHE):
        self.cache_dir = cache_dir
        self.enabled = enabled
        if self.enabled:
            os.makedirs(self.cache_dir, exist_ok=True)

    def _get_zip_path(self, appid: int) -> str:
        return os.path.join(self.cache_dir, f"{appid}.zip")

    def has_manifest(self, appid: int) -> bool:
        if not self.enabled:
            return False
        return os.path.exists(self._get_zip_path(appid))

    def get_zip_bytes(self, appid: int) -> Optional[bytes]:
        if not self.enabled:
            return None
        path = self._get_zip_path(appid)
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return f.read()
            except Exception as e:
                print(f"[CacheManager] Read error for {appid}: {e}")
        return None

    def save_zip(self, appid: int, zip_bytes: bytes) -> bool:
        if not self.enabled or not zip_bytes:
            return False
        path = self._get_zip_path(appid)
        try:
            with open(path, "wb") as f:
                f.write(zip_bytes)
            return True
        except Exception as e:
            print(f"[CacheManager] Write error for {appid}: {e}")
            return False

    def get_lua_content(self, appid: int) -> Optional[str]:
        """Extracts the .lua configuration from the cached ZIP."""
        zip_bytes = self.get_zip_bytes(appid)
        if not zip_bytes:
            return None
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as z:
                for name in z.namelist():
                    if name.endswith(".lua"):
                        with z.open(name) as f:
                            return f.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"[CacheManager] Failed to extract Lua for {appid}: {e}")
        return None

    def get_manifest_file(self, appid: int, depot_id: str) -> Optional[bytes]:
        """Extracts a specific .manifest file for a depot from the cached ZIP."""
        zip_bytes = self.get_zip_bytes(appid)
        if not zip_bytes:
            return None
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as z:
                for name in z.namelist():
                    if name.startswith(f"{depot_id}_") and name.endswith(".manifest"):
                        with z.open(name) as f:
                            return f.read()
        except Exception as e:
            print(f"[CacheManager] Failed to extract manifest for {appid}/{depot_id}: {e}")
        return None

    def inspect_archive(self, appid: int) -> Optional[Dict[str, Any]]:
        """Inspects archive and returns depot lists and stats."""
        zip_bytes = self.get_zip_bytes(appid)
        if not zip_bytes:
            return None
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as z:
                manifest_files = [n for n in z.namelist() if n.endswith(".manifest")]
                lua_files = [n for n in z.namelist() if n.endswith(".lua")]
                return {
                    "appid": appid,
                    "total_files": len(z.namelist()),
                    "manifest_count": len(manifest_files),
                    "has_lua": len(lua_files) > 0,
                    "manifests": manifest_files,
                    "archive_size_bytes": len(zip_bytes)
                }
        except Exception as e:
            print(f"[CacheManager] Inspect error for {appid}: {e}")
        return None

cache_manager = CacheManager()
