# ⚡ DepotBox Manifest & Lua API Gateway

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

A high-performance, asynchronous REST API Gateway and microservice designed to serve Steam game depot manifests (`.manifest`) and Lua configuration scripts (`.lua`). 

This project bridges your authenticated **DepotBox Premium Account** (`https://depotbox.org`) into an enterprise-grade REST API, enabling you to generate and distribute **secure API Keys** to bots, desktop clients, and developers without ever exposing your private session cookie on a public GitHub repository.

---

## 🌟 Key Architecture & Highlights

- 🔒 **Zero-Secret Public Repository**: Keeps your private DepotBox session cookie (`connect.sid`) safely isolated in environment variables. Public consumers interact strictly via tokenized API keys.
- 🔑 **Session-Derived API Keys**: Mints cryptographically signed, tamper-proof API keys derived from HMAC-SHA256 of your DepotBox session secret.
- ⚡ **Instant Caching Engine**: Caches generated ZIP archives and Lua files locally to provide ultra-fast responses and conserve DepotBox requests.
- 🛡️ **Resilient Multi-Source Fallbacks**: If DepotBox is temporarily inaccessible or missing a game, automatically synthesizes manifests via SteamCMD PICS and public GitHub mirrors.
- 🔌 **Universal Compatibility**:
  - Direct drop-in replacement for VesperDownloader API, Steam Manifest Manager, and custom manifest bots.
  - Interactive Swagger OpenAPI UI (`/docs`) and ReDoc (`/redoc`).

---

## 📋 Table of Contents

1. [Quickstart Setup](#-quickstart-setup)
2. [Generating API Keys from DepotBox Session](#-generating-api-keys)
3. [Running the API Server](#-running-the-api-server)
4. [REST API Reference & Endpoints](#-rest-api-reference)
5. [Integrating with Discord Bots](#-integrating-with-discord-bots)
6. [CLI Management Tool](#-cli-management-tool)
7. [Docker Deployment](#-docker-deployment)
8. [Security & Best Practices for Public Repositories](#-security-best-practices)

---

## 🚀 Quickstart Setup

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/depotbox-manifest-api.git
cd depotbox-manifest-api
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Obtain Your DepotBox Session Cookie
1. Open your browser and navigate to [https://depotbox.org/](https://depotbox.org/).
2. Log into your account (must have Premium membership to bypass CAPTCHA checks).
3. Open Developer Tools (`F12`), go to **Application** -> **Cookies** -> `https://depotbox.org`.
4. Copy the value of the `connect.sid` cookie.

### 4. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` and paste your cookie:
```ini
DEPOTBOX_COOKIE=s%3Ayour_actual_connect_sid_here
PORT=8000
RATE_LIMIT_PER_MINUTE=60
```

---

## 🔑 Generating API Keys

You can generate API keys directly using the built-in CLI:

```bash
# Generate a new API key tied to your session ID
python cli.py create-key --label "Discord Manifest Bot" --tier premium --days 365
```

**Output:**
```text
[+] API Key Generated Successfully!
--------------------------------------------------------------------
🔑 API Key:    dbx_eyJraWQiOiAiOTZhN2Y4...3f8a9e
🏷️  Label:      Discord Manifest Bot
⭐ Tier:       premium
🆔 Key ID:     96a7f8b1c2d3
📅 Expires In: 365 days
--------------------------------------------------------------------
```

---

## 🌐 Running the API Server

Start the API server with Uvicorn:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Once started, explore the interactive API documentation at:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 📡 REST API Reference

All protected endpoints accept your API Key via either:
- **Header:** `X-API-Key: <YOUR_API_KEY>`
- **Header:** `Authorization: Bearer <YOUR_API_KEY>`
- **Query Parameter:** `?key=<YOUR_API_KEY>`

### 1. Download Manifest Package (ZIP)
Retrieves the complete ZIP archive containing `{appid}.lua` and all `{depot_id}_{manifest_gid}.manifest` binary files.

```http
GET /api/v1/manifest/{appid}
```
**Example cURL:**
```bash
curl -H "X-API-Key: YOUR_API_KEY" http://localhost:8000/api/v1/manifest/730 -o 730.zip
```

### 2. Download Raw Lua Configuration
Extracts and streams the `{appid}.lua` configuration file.

```http
GET /api/v1/lua/{appid}
```
**Example cURL:**
```bash
curl -H "X-API-Key: YOUR_API_KEY" http://localhost:8000/api/v1/lua/730
```

### 3. Download Single Depot Manifest
Downloads an individual `.manifest` binary file for a specific depot.

```http
GET /api/v1/manifest/{appid}/{depot_id}
```
**Example cURL:**
```bash
curl -H "X-API-Key: YOUR_API_KEY" http://localhost:8000/api/v1/manifest/730/731 -o 731.manifest
```

### 4. Inspect Manifest Package Metadata
Returns JSON information about depots, total manifest count, and archive size.

```http
GET /api/v1/info/{appid}
```

### 5. Health & Session Check
Verifies server health and checks if the DepotBox session cookie is valid.

```http
GET /api/v1/health
```

---

## 🤖 Integrating with Discord Bots

To connect your Discord bot (such as `manifest-bot`) to your self-hosted DepotBox API:

1. In your bot's `.env` file, set:
```ini
MANIFEST_API_KEY=YOUR_GENERATED_DBX_API_KEY
MANIFEST_API_URL=http://your-server-ip:8000
```

2. In your bot code, fetch manifests directly using standard HTTP requests:
```python
import aiohttp

async def download_manifest(appid: int, api_key: str, api_url: str):
    headers = {"X-API-Key": api_key}
    url = f"{api_url}/api/v1/manifest/{appid}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                zip_data = await resp.read()
                return zip_data
            else:
                error = await resp.text()
                raise Exception(f"API Error {resp.status}: {error}")
```

---

## 🛠️ CLI Management Tool

The included `cli.py` tool provides easy administrative utilities:

| Command | Description |
| :--- | :--- |
| `python cli.py create-key --label "Bot" --days 365` | Mints a new signed API key |
| `python cli.py check-session` | Tests DepotBox session validity against depotbox.org |
| `python cli.py list-keys` | Displays all issued API keys and statuses |
| `python cli.py revoke-key <key_id>` | Revokes an existing API key |
| `python cli.py fetch <appid> --out ./output` | Downloads and tests a game manifest via CLI |

---

## 🐳 Docker Deployment

Deploy with Docker in one command:

```bash
docker-compose up -d --build
```
This mounts `./cache_storage` and `./keys.json` as persistent host volumes so cached game files and keys are preserved across restarts.

---

## 🛡️ Security & Best Practices for Public Repositories

> [!IMPORTANT]
> When hosting this project as a **Public GitHub Repository**:
> 1. **Never commit `.env`**: Ensure `.env` is listed in `.gitignore` (pre-configured).
> 2. **Never commit `depotbox_session` or `keys.json`**: These contain active credentials and issued keys.
> 3. **Protect your session ID**: The `DEPOTBOX_COOKIE` gives full access to your DepotBox account. Only configure it on your secure deployment server or via GitHub Secrets / environment variables on Render / Railway.
> 4. **Rotate keys**: If an API key is leaked, revoke it instantly using `python cli.py revoke-key <key_id>` without affecting other users or your DepotBox session.

---

## 📜 License
This project is licensed under the MIT License.
