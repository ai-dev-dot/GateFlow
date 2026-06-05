from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import async_session, engine
from app.models import Base
from app.models.agent_type import AgentType
from app.routers.agent_types import router as agent_types_router
from app.routers.anthropic_forward import router as anthropic_forward_router
from app.routers.api_keys import router as api_keys_router
from app.routers.audit import router as audit_router
from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.gateway import router as gateway_router
from app.routers.gateway_forward import router as gateway_forward_router
from app.routers.provider_keys import router as provider_keys_router
from app.routers.usage import router as usage_router
from app.routers.users import router as users_router
from app.services.auth_service import AuthService
from app.utils.http_client import close_http_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialize admin user
    async with async_session() as db:
        auth_service = AuthService(db)
        await auth_service.init_admin()

    # Seed default AgentType values
    async with async_session() as db:
        from sqlalchemy import select

        result = await db.execute(select(AgentType).limit(1))
        if not result.scalar_one_or_none():
            for name in ["Claude Code", "Codex", "Cursor", "Dify", "LangChain", "自定义"]:
                db.add(AgentType(name=name))
            await db.commit()

    yield

    # Cleanup on shutdown
    await close_http_client()


app = FastAPI(title="闸机 GateFlow", version="0.1.0", lifespan=lifespan)

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
app.include_router(anthropic_forward_router)
app.include_router(audit_router)
app.include_router(usage_router)
app.include_router(chat_router)
app.include_router(agent_types_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
