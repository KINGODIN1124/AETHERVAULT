import os
import sys
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes_manifest import router as manifest_router
from app.api.routes_auth import router as auth_router
from app.config import PORT, HOST

app = FastAPI(
    title="DepotBox Manifest & Lua API Gateway",
    description=(
        "High-performance REST API gateway that serves Steam depot manifests and "
        "Lua configurations powered by a DepotBox Premium Session. "
        "Allows generating secure API keys from your DepotBox session so you can safely "
        "host a public service without exposing your session cookies."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for web applications / dashboard frontends
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
        "service": "DepotBox Manifest & Lua API Gateway",
        "status": "online",
        "documentation": "/docs",
        "endpoints": {
            "download_manifest_zip": "/api/v1/manifest/{appid}",
            "get_lua_config": "/api/v1/lua/{appid}",
            "inspect_info": "/api/v1/info/{appid}",
            "create_api_key": "/api/v1/auth/create-key",
            "health_check": "/api/v1/health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Starting DepotBox API Gateway on {HOST}:{PORT}...")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
