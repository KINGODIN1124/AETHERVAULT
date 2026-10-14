import os
import sys
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes_manifest import router as manifest_router
from app.api.routes_auth import router as auth_router
from app.config import PORT, HOST

app = FastAPI(
    title="AetherVault - Steam Manifest & Lua Distribution Gateway",
    description=(
        "Enterprise-grade REST API gateway for Steam depot manifests (.manifest) "
        "and Lua configuration scripts (.lua). Features cryptographic API key generation, "
        "in-memory caching, anti-scraping IP defense, and multi-source fallbacks."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for web apps & dashboard integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(manifest_router)
app.include_router(auth_router)

@app.get("/", tags=["Root"])
async def root_index():
    return {
        "service": "AetherVault Steam Manifest & Lua Gateway",
        "status": "online",
        "version": "2.0.0",
        "documentation": "/docs",
        "endpoints": {
            "public_trial_key": "/api/v1/auth/public-key",
            "download_manifest_zip": "/api/v1/manifest/{appid}",
            "get_lua_config": "/api/v1/lua/{appid}",
            "inspect_metadata": "/api/v1/info/{appid}",
            "health_check": "/api/v1/health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Starting AetherVault Gateway on {HOST}:{PORT}...")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
