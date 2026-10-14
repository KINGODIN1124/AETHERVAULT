<div align="center">

```
  ____  _____ ____   ___ _____   __     ___   _   _ _ _____ 
 |  _ \| ____|  _ \ / _ \_   _|  \ \   / / \ | | | |_   _|
 | | | |  _| | |_) | | | || | ____\ \ / / _ \| | | | | |  
 | |_| | |___|  __/| |_| || ||_____\ V / ___ \ |_| | | |  
 |____/|_____|_|    \___/ |_|        \_/_/   \_\___/  |_|  
```

# ⚡ DEPOTVAULT
### *The Next-Generation Steam Depot Manifest & Lua Distribution Gateway*

<p align="center">
  <b>Transform your DepotBox Premium session into an enterprise-grade, high-speed REST API.</b><br>
  <i>Mint cryptographically secure API keys, bypass Cloudflare Turnstile, stream manifests instantly, and shield your account credentials from the public.</i>
</p>

<p align="center">
  <a href="https://github.com/KINGODIN1124/Manifest/actions/workflows/ci.yml"><img src="https://github.com/KINGODIN1124/Manifest/actions/workflows/ci.yml/badge.svg" alt="CI Pipeline"></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"></a>
  <a href="https://www.docker.com"><img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-F7DF1E?style=for-the-badge" alt="License"></a>
  <a href="https://swagger.io"><img src="https://img.shields.io/badge/Swagger-OpenAPI%203.0-85EA2D?style=for-the-badge&logo=swagger&logoColor=black" alt="Swagger"></a>
</p>

[✨ Features](#-features) • [🏛️ Architecture](#-system-architecture) • [🚀 Quickstart](#-quickstart-guide) • [🔑 API Keys](#-generating-api-keys) • [📡 REST Endpoints](#-rest-api-documentation) • [🐳 Docker](#-docker-deployment) • [🤖 Bot Integration](#-discord-bot-integration)

---

</div>

## 🌟 Features

<table>
  <tr>
    <td width="50%">
      <h3>🔒 Zero Credential Exposure</h3>
      <p>Host safely on <b>Public GitHub</b> without fear. Your raw <code>connect.sid</code> session cookie remains strictly encrypted on your host machine while external consumers authenticate through tokenized API keys.</p>
    </td>
    <td width="50%">
      <h3>🔑 Cryptographic Key Minting</h3>
      <p>Mints tamper-proof API keys derived from HMAC-SHA256 mathematical signatures of your DepotBox session secret. Includes an audited local registry with instant revocation.</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>⚡ In-Memory & Disk Cache</h3>
      <p>Blazing-fast response times (&lt;15ms for cached items). Compiled ZIP archives and Lua configurations are stored locally, dramatically saving bandwidth and DepotBox rate limits.</p>
    </td>
    <td width="50%">
      <h3>🛡️ Automatic Multi-Tier Fallback</h3>
      <p>If DepotBox is temporarily inaccessible or missing a game, DepotVault seamlessly falls back to SteamCMD PICS and public GitHub mirrors, compiling fresh packages dynamically.</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>🔌 Universal Client Compatibility</h3>
      <p>Direct drop-in replacement for VesperDownloader API, Steam Manifest Manager, SteaMidra, Luie tools, and Discord bots like <code>Manifest-Bot</code>.</p>
    </td>
    <td width="50%">
      <h3>🐳 Cloud & Container Native</h3>
      <p>Production-ready Docker and Docker Compose orchestration. Deploy effortlessly to Railway, Render, Fly.io, or any Linux VPS.</p>
    </td>
  </tr>
</table>

---

## 🏛️ System Architecture

```mermaid
graph TD
    Client["📱 Client / Discord Bot / Tool"] -->|"Request with X-API-Key"| Gateway["⚡ DepotVault API Gateway (FastAPI)"]
    
    subgraph Security Layer
        Gateway --> Auth["🔑 KeyEngine Middleware"]
        Auth -->|"HMAC-SHA256 Verification"| Valid{"Valid Key?"}
        Valid -->|No| Reject["❌ 401 / 403 Forbidden"]
    end

    subgraph Storage & Cache
        Valid -->|Yes| CacheCheck{"In Cache?"}
        CacheCheck -->|Hit (<15ms)| ReturnCache["📦 Stream Cached ZIP/Lua"]
    end

    subgraph Upstream Provider Pipeline
        CacheCheck -->|Miss| DepotBox["🌐 DepotBox.org Engine"]
        DepotBox -->|"connect.sid (Premium Bypass)"| Turnstile["🛡️ Cloudflare Turnstile Bypass"]
        Turnstile -->|"Job Polling & Download"| Success{"Downloaded?"}
        Success -->|Yes| SaveCache["💾 Save to Disk & Memory Cache"]
        SaveCache --> ReturnCache
        Success -->|Failed / Missing| Fallback["🔄 SteamCMD PICS & GitHub Mirrors"]
        Fallback --> DynamicCompile["⚙️ Dynamic Manifest & Lua Synthesis"]
        DynamicCompile --> SaveCache
    end

    ReturnCache -->|"HTTP 200 Binary Stream"| Client
```

---

## 🚀 Quickstart Guide

### 1. Clone the Repository
```bash
git clone https://github.com/KINGODIN1124/Manifest.git
cd Manifest
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Extract Your DepotBox Session
1. Log into your account on [https://depotbox.org/](https://depotbox.org/) (ensure you are a **Premium Member**).
2. Open Browser DevTools (`F12`) -> **Application** -> **Cookies** -> `https://depotbox.org`.
3. Copy the value of the `connect.sid` cookie.

### 4. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Populate `.env`:
```ini
DEPOTBOX_COOKIE=s%3Ayour_actual_connect_sid_here
PORT=8000
RATE_LIMIT_PER_MINUTE=60
ENABLE_CACHE=true
ENABLE_FALLBACK_MIRRORS=true
```

---

## 🔑 Generating API Keys

DepotVault includes an administrative CLI to generate, audit, and revoke API keys:

```bash
# Mint a new API key tied to your session ID
python cli.py create-key --label "Production Bot" --tier premium --days 365
```

```text
====================================================================
      ⚡ DEPOTBOX MANIFEST & LUA API CLI MANAGER ⚡
====================================================================
[*] Creating API key from DepotBox Session ID...

[+] API Key Generated Successfully!
--------------------------------------------------------------------
🔑 API Key:    dbx_eyJraWQiOiIyYmZhY2FkNWFkNzAi...3d904425bcff
🏷️  Label:      Production Bot
⭐ Tier:       premium
🆔 Key ID:     2bfacad5ad70
📅 Expires In: 365 days
--------------------------------------------------------------------
```

### Additional CLI Commands
```bash
# Verify connection to DepotBox upstream
python cli.py check-session

# List all issued keys and their current status
python cli.py list-keys

# Revoke a compromised key immediately
python cli.py revoke-key <KEY_ID>

# Test-download an AppID directly to disk
python cli.py fetch 730 --out ./downloads
```

---

## 🌐 Running the API Server

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Once started:
- 📖 **Interactive Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- 📚 **Alternative ReDoc UI:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 📡 REST API Documentation

### Authentication Methods
Every protected endpoint accepts your API Key through any of the following:
* **Header:** `X-API-Key: dbx_...`
* **Bearer Token:** `Authorization: Bearer dbx_...`
* **Query Parameter:** `?key=dbx_...`

---

### Endpoints Overview

| Method | Endpoint | Description |
| :---: | :--- | :--- |
| `GET` | `/api/v1/manifest/{appid}` | Streams the complete manifest ZIP archive (`.manifest` + `{appid}.lua`). |
| `GET` | `/api/v1/lua/{appid}` | Extracts and streams the raw Steam `{appid}.lua` configuration script. |
| `GET` | `/api/v1/manifest/{appid}/{depot_id}` | Downloads a specific depot's binary `.manifest` file. |
| `GET` | `/api/v1/info/{appid}` | Inspects depot count, manifest GIDs, and total package size. |
| `POST`| `/api/v1/auth/create-key` | Programmatically creates a new API key derived from a session. |
| `GET` | `/api/v1/auth/verify` | Validates API key authenticity and returns key metadata. |
| `GET` | `/api/v1/health` | Upstream health status, cache volume, and session diagnostic. |
| `GET` | `/api/v1/partner/lua` | Drop-in compatibility endpoint for Vesper/Luie tools. |

---

### Request & Response Examples

<details>
<summary><b>1. Download Manifest ZIP (`/api/v1/manifest/{appid}`)</b></summary>

```bash
curl -H "X-API-Key: YOUR_API_KEY" \
     "http://localhost:8000/api/v1/manifest/730" \
     -o "730.zip"
```
**Response:** Complete binary ZIP package containing all depot manifests and `730.lua`.
</details>

<details>
<summary><b>2. Fetch Raw Lua Config (`/api/v1/lua/{appid}`)</b></summary>

```bash
curl -H "X-API-Key: YOUR_API_KEY" \
     "http://localhost:8000/api/v1/lua/730"
```
**Response Preview:**
```lua
-- ============================================================
-- AUTOMATED STEAM CONFIG FOR Counter-Strike 2
-- Generated via DepotVault Gateway
-- AppID:   730
-- ============================================================

addappid(730)
addappid(731, 1)
setManifestid(731, "2846174982635019283", 421092834)
addappid(732, 1)
setManifestid(732, "8293740192837401928")
```
</details>

<details>
<summary><b>3. Inspect Package Metadata (`/api/v1/info/{appid}`)</b></summary>

```bash
curl -H "X-API-Key: YOUR_API_KEY" \
     "http://localhost:8000/api/v1/info/730"
```
**Response:**
```json
{
  "appid": 730,
  "total_files": 9,
  "manifest_count": 8,
  "has_lua": true,
  "manifests": [
    "731_2846174982635019283.manifest",
    "732_8293740192837401928.manifest"
  ],
  "archive_size_bytes": 1420952
}
```
</details>

---

## 🤖 Discord Bot Integration

To connect your Discord bot (such as [`Manifest-Bot`](https://github.com/KINGODIN1124/Manifest-Bot)) to DepotVault:

1. Update your bot's `.env`:
```ini
MANIFEST_API_KEY=YOUR_GENERATED_DBX_API_KEY
MANIFEST_API_URL=http://your-server-ip:8000
```

2. Call DepotVault in your bot's download logic:
```python
import aiohttp

async def download_game_manifest(appid: int, api_key: str, gateway_url: str):
    headers = {"X-API-Key": api_key}
    endpoint = f"{gateway_url}/api/v1/manifest/{appid}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint, headers=headers) as resp:
            if resp.status == 200:
                return await resp.read()
            raise Exception(f"Gateway Error (HTTP {resp.status}): {await resp.text()}")
```

---

## 🐳 Docker Deployment

Deploy with Docker Compose in a single command:

```bash
docker-compose up -d --build
```

The stack automatically mounts `./cache_storage` and `./keys.json` to the container host, guaranteeing that cached files and issued API keys persist across container restarts and updates.

---

## 🛡️ Security Best Practices

> [!IMPORTANT]
> - **Public Repository Isolation**: `.gitignore` is rigorously configured to ignore `.env`, `keys.json`, `depotbox_session/`, and downloaded binaries. Never force-add these files.
> - **Secret Management**: Configure `DEPOTBOX_COOKIE` strictly on your private host or through deployment environment variables (e.g. Render/Railway Secrets).
> - **Instant Key Revocation**: If an API key is ever leaked or abused, revoke it immediately via `python cli.py revoke-key <KEY_ID>` without changing your DepotBox account password or session cookie.

---

## 📜 License & Credits

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

- **Developer:** [@KINGODIN1124](https://github.com/KINGODIN1124)
- **Engine Provider:** [DepotBox](https://depotbox.org)
