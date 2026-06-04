from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.api_keys import router as api_keys_router
from app.routers.provider_keys import router as provider_keys_router
from app.routers.gateway import router as gateway_router
from app.routers.gateway_forward import router as gateway_forward_router
from app.routers.audit import router as audit_router
from app.routers.usage import router as usage_router

app = FastAPI(title="闸机 GateFlow", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(api_keys_router)
app.include_router(provider_keys_router)
app.include_router(gateway_router)
app.include_router(gateway_forward_router)
app.include_router(audit_router)
app.include_router(usage_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
