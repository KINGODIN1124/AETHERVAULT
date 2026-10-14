"""
Example client script showing how to consume the DepotBox Manifest & Lua API
using Python and an API Key.
"""

import requests
import json
import os

API_BASE_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "YOUR_GENERATED_API_KEY_HERE")

def test_api():
    print(f"[*] Testing DepotBox Manifest API at: {API_BASE_URL}")

    headers = {
        "X-API-Key": API_KEY,
        "User-Agent": "DepotBox-Test-Client/1.0"
    }

    # 1. Health check (no auth required)
    try:
        r = requests.get(f"{API_BASE_URL}/api/v1/health")
        print(f"[+] Health Check (HTTP {r.status_code}):", json.dumps(r.json(), indent=2))
    except Exception as e:
        print(f"[-] Could not connect to API server: {e}")
        return

    # 2. Key verification
    try:
        r = requests.get(f"{API_BASE_URL}/api/v1/auth/verify", headers=headers)
        if r.status_code == 200:
            print(f"[+] API Key Verified successfully! Details:", json.dumps(r.json(), indent=2))
        else:
            print(f"[-] API Key verification failed (HTTP {r.status_code}):", r.text)
            return
    except Exception as e:
        print(f"[-] Auth verification error: {e}")
        return

    # 3. Fetch Lua configuration for Counter-Strike 2 (AppID: 730)
    target_appid = 730
    print(f"\n[*] Requesting Lua config for AppID {target_appid}...")
    try:
        r = requests.get(f"{API_BASE_URL}/api/v1/lua/{target_appid}", headers=headers)
        if r.status_code == 200:
            print(f"[+] Received Lua config ({len(r.text)} characters):")
            print("--- Lua Preview ---")
            print("\n".join(r.text.splitlines()[:15]))
            print("-------------------")
        else:
            print(f"[-] Failed to fetch Lua (HTTP {r.status_code}): {r.text}")
    except Exception as e:
        print(f"[-] Error fetching Lua: {e}")

    # 4. Download complete manifest ZIP
    print(f"\n[*] Requesting complete Manifest ZIP archive for AppID {target_appid}...")
    try:
        r = requests.get(f"{API_BASE_URL}/api/v1/manifest/{target_appid}", headers=headers, stream=True)
        if r.status_code == 200:
            out_filename = f"{target_appid}_downloaded.zip"
            with open(out_filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"[+] Successfully saved ZIP archive: {out_filename} ({os.path.getsize(out_filename):,} bytes)")
        else:
            print(f"[-] Failed to download manifest ZIP (HTTP {r.status_code}): {r.text}")
    except Exception as e:
        print(f"[-] Error downloading ZIP: {e}")

if __name__ == "__main__":
    test_api()
